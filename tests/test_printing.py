"""Tests for the MQTT label printing helper."""

from datetime import datetime
import importlib
import sys
import types
import unittest


def _install_home_assistant_stubs() -> None:
    """Install the subset needed to import the printer without Home Assistant."""
    if "homeassistant.exceptions" in sys.modules:
        return
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    exceptions = types.ModuleType("homeassistant.exceptions")
    helpers = types.ModuleType("homeassistant.helpers")
    event = types.ModuleType("homeassistant.helpers.event")
    storage = types.ModuleType("homeassistant.helpers.storage")
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")

    class Store:
        def __init__(self, *_args, **_kwargs):
            self.saved = []

        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        async def async_load(self):
            return None

        async def async_save(self, data):
            self.saved.append(data)

    class HomeAssistantError(Exception):
        pass

    core.Event = object
    core.HomeAssistant = object
    core.callback = lambda function: function
    exceptions.HomeAssistantError = HomeAssistantError
    event.async_track_time_interval = lambda *_a, **_k: lambda: None
    storage.Store = Store
    dt.now = lambda: datetime.now().astimezone()
    dt.parse_datetime = lambda value: datetime.fromisoformat(value) if value else None
    dt.as_local = lambda value: value.astimezone()
    util.dt = dt
    sys.modules.update(
        {
            "homeassistant": ha,
            "homeassistant.core": core,
            "homeassistant.exceptions": exceptions,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.event": event,
            "homeassistant.helpers.storage": storage,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt,
        }
    )


def _import(name: str):
    from pathlib import Path

    root = Path(__file__).parents[1] / "custom_components" / "medreminder"
    package = types.ModuleType("custom_components.medreminder")
    package.__path__ = [str(root)]
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(root.parent)]
    sys.modules.setdefault("custom_components", custom_components)
    sys.modules.setdefault("custom_components.medreminder", package)
    return importlib.import_module(f"custom_components.medreminder.{name}")


_install_home_assistant_stubs()
printing = _import("printing")
const = _import("const")


class FakeConfigEntries:
    def __init__(self, mqtt: bool) -> None:
        self.mqtt = mqtt

    def async_entries(self, domain: str):
        return [object()] if domain == "mqtt" and self.mqtt else []


class FakeHass:
    def __init__(self, mqtt: bool = True) -> None:
        self.config_entries = FakeConfigEntries(mqtt)


def printer(hass: FakeHass | None = None, **options) -> printing.LabelPrinter:
    settings = {const.OPTION_PRINTING_ENABLED: True}
    settings.update(options)
    return printing.LabelPrinter(hass or FakeHass(), settings)


class ConfigurationTests(unittest.TestCase):
    """Reading the options the user set."""

    def test_printing_is_off_by_default(self) -> None:
        self.assertFalse(printing.LabelPrinter(FakeHass(), {}).enabled)

    def test_defaults_apply_to_empty_options(self) -> None:
        active = printer()
        self.assertEqual(const.DEFAULT_BASE_TOPIC, active.base_topic)
        self.assertEqual(const.DEFAULT_TEMPLATE, active.template)
        self.assertEqual(const.DEFAULT_COPIES, active.copies)

    def test_the_base_topic_loses_its_slashes(self) -> None:
        self.assertEqual(
            "print/labels",
            printer(**{const.OPTION_BASE_TOPIC: "/print/labels/"}).base_topic,
        )

    def test_a_blank_base_topic_falls_back(self) -> None:
        self.assertEqual(
            const.DEFAULT_BASE_TOPIC,
            printer(**{const.OPTION_BASE_TOPIC: "   "}).base_topic,
        )

    def test_copies_stay_inside_the_allowed_range(self) -> None:
        self.assertEqual(1, printer(**{const.OPTION_COPIES: 0}).copies)
        self.assertEqual(
            const.MAX_COPIES, printer(**{const.OPTION_COPIES: 500}).copies
        )
        self.assertEqual(
            const.DEFAULT_COPIES, printer(**{const.OPTION_COPIES: "three"}).copies
        )

    def test_printing_needs_mqtt_to_be_available(self) -> None:
        self.assertTrue(printer().available())
        self.assertFalse(printer(FakeHass(mqtt=False)).available())

    def test_a_disabled_printer_is_never_available(self) -> None:
        off = printing.LabelPrinter(FakeHass(), {const.OPTION_PRINTING_ENABLED: False})
        self.assertFalse(off.available())

    def test_the_status_describes_printing_for_the_panel(self) -> None:
        status = printer(**{const.OPTION_LABEL_SIZE: "standard"}).status()
        self.assertTrue(status["enabled"])
        self.assertTrue(status["mqtt_configured"])
        self.assertTrue(status["available"])
        self.assertEqual("qr_nickname", status["template"])
        self.assertEqual("standard", status["label"])

    def test_an_unset_label_size_is_reported_as_none(self) -> None:
        self.assertIsNone(printer().status()["label"])


class JobTests(unittest.TestCase):
    """Building the payload the print service expects."""

    def test_the_job_carries_the_code_and_the_name(self) -> None:
        job = printer().build_job("med23456", "Apollo")
        self.assertEqual("qr_nickname", job["template"])
        self.assertEqual({"code": "med23456", "name": "Apollo"}, job["data"])
        self.assertEqual(1, job["copies"])
        self.assertTrue(job["job_id"].startswith("medreminder_"))

    def test_a_missing_name_is_left_out(self) -> None:
        # Without a name the template centres the code, so an empty string
        # would only produce an empty strip beside it.
        self.assertEqual({"code": "med23456"}, printer().build_job("med23456", "")["data"])

    def test_whitespace_in_the_name_is_collapsed(self) -> None:
        job = printer().build_job("med23456", "  Vitamin   D3 \n")
        self.assertEqual("Vitamin D3", job["data"]["name"])

    def test_a_long_name_is_cut_to_what_fits(self) -> None:
        job = printer().build_job("med23456", "N" * 200)
        self.assertEqual(const.MAX_LABEL_NAME_LENGTH, len(job["data"]["name"]))

    def test_the_label_size_is_only_sent_when_set(self) -> None:
        self.assertNotIn("label", printer().build_job("med23456", "A"))
        self.assertEqual(
            "standard",
            printer(**{const.OPTION_LABEL_SIZE: "standard"}).build_job(
                "med23456", "A"
            )["label"],
        )

    def test_every_job_gets_its_own_id(self) -> None:
        active = printer()
        first = active.build_job("med23456", "A")["job_id"]
        second = active.build_job("med23456", "A")["job_id"]
        self.assertNotEqual(first, second)

    def test_only_a_scan_code_may_be_printed(self) -> None:
        for value in ("", "https://example.com", "med2345", "MED23456", "med2345!"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                printer().build_job(value, "A")


class GuardTests(unittest.IsolatedAsyncioTestCase):
    """Refusing to print when printing cannot work."""

    async def test_printing_while_switched_off_is_refused(self) -> None:
        off = printing.LabelPrinter(FakeHass(), {const.OPTION_PRINTING_ENABLED: False})
        with self.assertRaises(printing.PrintingNotConfigured):
            await off.async_print("med23456", "Apollo")

    async def test_printing_without_mqtt_is_refused(self) -> None:
        with self.assertRaises(printing.PrintingNotConfigured):
            await printer(FakeHass(mqtt=False)).async_print("med23456", "Apollo")


if __name__ == "__main__":
    unittest.main()
