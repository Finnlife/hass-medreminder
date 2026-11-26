"""Tests for moving an install over from the domain used before the rename."""

from __future__ import annotations

import enum
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1] / "custom_components" / "medreminder"
PACKAGE = "medreminder_legacy_test"


class _Store:
    def __init__(self, *_args, **_kwargs):
        pass

    def __class_getitem__(cls, _item):
        return cls


class _DeviceRegistry:
    def async_update_device(self, device_id, *, new_config_entry_id=None):
        """Stand-in with the 2026.11 signature."""


def _load_legacy():
    """Import legacy.py against small stand-ins for the Home Assistant modules."""

    class ConfigEntryState(enum.Enum):
        LOADED = "loaded"
        NOT_LOADED = "not_loaded"
        SETUP_IN_PROGRESS = "setup_in_progress"
        SETUP_RETRY = "setup_retry"

    stubs = {
        "homeassistant": types.ModuleType("homeassistant"),
        "homeassistant.config_entries": types.SimpleNamespace(
            ConfigEntry=object, ConfigEntryState=ConfigEntryState
        ),
        "homeassistant.const": types.SimpleNamespace(ATTR_RESTORED="restored"),
        "homeassistant.core": types.SimpleNamespace(
            HomeAssistant=object, callback=lambda func: func
        ),
        "homeassistant.helpers": types.ModuleType("homeassistant.helpers"),
        "homeassistant.helpers.device_registry": types.SimpleNamespace(
            DeviceRegistry=_DeviceRegistry
        ),
        "homeassistant.helpers.storage": types.SimpleNamespace(Store=_Store),
        "homeassistant.helpers.entity": types.SimpleNamespace(
            entity_sources=lambda hass: hass.loaded
        ),
        "homeassistant.helpers.entity_registry": types.ModuleType("er"),
        "homeassistant.helpers.issue_registry": types.ModuleType("ir"),
        "homeassistant.util": types.ModuleType("homeassistant.util"),
    }
    helpers = stubs["homeassistant.helpers"]
    helpers.device_registry = stubs["homeassistant.helpers.device_registry"]
    helpers.storage = stubs["homeassistant.helpers.storage"]
    helpers.entity = stubs["homeassistant.helpers.entity"]
    helpers.entity_registry = stubs["homeassistant.helpers.entity_registry"]
    helpers.issue_registry = stubs["homeassistant.helpers.issue_registry"]
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT)]
    stubs[PACKAGE] = package
    with mock.patch.dict(sys.modules, stubs):
        for name in ("const", "scan_codes", "migrations", "storage", "legacy"):
            spec = importlib.util.spec_from_file_location(
                f"{PACKAGE}.{name}", ROOT / f"{name}.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
    return module


legacy = _load_legacy()


def _own_document() -> dict:
    return {
        "version": 1,
        "minor_version": 7,
        "key": "medication_reminder.data",
        "data": {
            "medications": [{"id": "m", "name": "Magnesium"}],
            "packages": [],
            "regimens": [],
            "occurrences": [],
        },
    }


class IdentifierTests(unittest.TestCase):
    def test_unique_ids_move_to_the_new_prefix(self) -> None:
        self.assertEqual(
            "medreminder_m1_stock", legacy.new_unique_id("medication_reminder_m1_stock")
        )
        self.assertEqual(
            "medreminder_m1_package_p1_stock",
            legacy.new_unique_id("medication_reminder_m1_package_p1_stock"),
        )
        self.assertEqual("other", legacy.new_unique_id("other"))

    def test_device_identifiers_move_to_the_new_domain(self) -> None:
        self.assertEqual(
            ("medreminder", "medreminder"),
            legacy.new_identifier(("medication_reminder", "medication_reminder")),
        )
        self.assertEqual(
            ("medreminder", "m1"), legacy.new_identifier(("medication_reminder", "m1"))
        )
        self.assertEqual(("mqtt", "x"), legacy.new_identifier(("mqtt", "x")))


class OwnershipTests(unittest.TestCase):
    def test_only_the_hub_of_an_earlier_version_counts(self) -> None:
        hub = _device(("medication_reminder", "medication_reminder"))
        self.assertTrue(legacy.is_own_hub(hub))
        for device in (
            _device(("medication_reminder", "01FOREIGN")),
            _device(("medication_reminder", "medication_reminder"), manufacturer="X"),
            _device(("medication_reminder", "medication_reminder"), model="Other"),
            _device(("medreminder", "medreminder")),
        ):
            with self.subTest(device=device):
                self.assertFalse(legacy.is_own_hub(device))

    def test_only_our_data_shape_is_taken_over(self) -> None:
        self.assertTrue(legacy.is_own_data(_own_document()["data"]))
        for data in (None, [], {"doses": []}, {"medications": [], "packages": {}}):
            with self.subTest(data=data):
                self.assertFalse(legacy.is_own_data(data))

    def test_devices_move_in_one_step_on_current_home_assistant(self) -> None:
        self.assertTrue(legacy.MOVE_DEVICE_WITH_NEW_ENTRY)

    def test_only_our_old_folder_raises_the_repair_issue(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            self.assertFalse(legacy._is_own_legacy_folder(path))
            manifest = path / "manifest.json"
            manifest.write_text(
                json.dumps({"documentation": "https://github.com/magikh0e/x"}),
                encoding="utf-8",
            )
            self.assertFalse(legacy._is_own_legacy_folder(path))
            manifest.write_text(
                json.dumps(
                    {"documentation": "https://github.com/Finnlife/hass-medreminder"}
                ),
                encoding="utf-8",
            )
            self.assertTrue(legacy._is_own_legacy_folder(path))


class _States:
    def __init__(self, states: dict) -> None:
        self.states = states

    def get(self, entity_id):
        return self.states.get(entity_id)

    def async_remove(self, entity_id) -> None:
        self.states.pop(entity_id)


def _state(**attributes):
    return types.SimpleNamespace(state="unavailable", attributes=attributes)


class _EntityRegistry:
    """Mimics Home Assistant before 2026.6: entities with a state cannot move."""

    def __init__(self, hass, entries) -> None:
        self.hass = hass
        self.entries = entries
        self.moved = []

    def async_get_entity_id(self, *_args):
        return None

    def async_update_entity_platform(self, entity_id, platform, **kwargs) -> None:
        if self.hass.states.get(entity_id) is not None:
            raise ValueError("Only entities that haven't been loaded can be migrated")
        self.moved.append((entity_id, platform, kwargs["new_unique_id"]))


def _entity(entity_id: str):
    return types.SimpleNamespace(
        entity_id=entity_id,
        domain=entity_id.split(".")[0],
        platform="medication_reminder",
        unique_id=f"medication_reminder_{entity_id.split('.')[1]}",
    )


class RegistryMoveTests(unittest.TestCase):
    def _move(self, states: dict, loaded: dict | None = None):
        hass = types.SimpleNamespace(states=_States(states), loaded=loaded or {})
        entries = [_entity("sensor.stock"), _entity("calendar.plan")]
        registry = _EntityRegistry(hass, entries)
        er = types.SimpleNamespace(
            async_get=lambda _hass: registry,
            async_entries_for_config_entry=lambda reg, _id: reg.entries,
        )
        dr = types.SimpleNamespace(
            async_get=lambda _hass: None,
            async_entries_for_config_entry=lambda _reg, _id: [],
        )
        with mock.patch.object(legacy, "er", er), mock.patch.object(legacy, "dr", dr):
            legacy._move_registry_entries(hass, "old", "new")
        return hass, registry

    def test_placeholder_states_of_unloaded_entities_are_dropped(self) -> None:
        hass, registry = self._move(
            {
                "sensor.stock": _state(restored=True),
                "calendar.plan": _state(restored=True),
            }
        )
        self.assertEqual({}, hass.states.states)
        self.assertEqual(
            [
                ("sensor.stock", "medreminder", "medreminder_stock"),
                ("calendar.plan", "medreminder", "medreminder_plan"),
            ],
            registry.moved,
        )

    def test_a_real_state_is_kept_and_the_move_refused(self) -> None:
        with self.assertRaises(ValueError):
            self._move({"sensor.stock": _state()})

    def test_a_loaded_entity_keeps_its_state(self) -> None:
        with self.assertRaises(ValueError):
            self._move(
                {"sensor.stock": _state(restored=True)},
                loaded={"sensor.stock": {}},
            )


class EntrySettingsTests(unittest.TestCase):
    def _take_over(self, old, new):
        updates = []
        hass = types.SimpleNamespace(
            config_entries=types.SimpleNamespace(
                async_update_entry=lambda entry, **changes: updates.append(changes)
            )
        )
        legacy._take_over_entry_settings(hass, old, new)
        return updates

    def test_printing_options_and_title_move_over(self) -> None:
        old = types.SimpleNamespace(
            title="Grandma", options={"printing_enabled": True, "copies": 3}
        )
        new = types.SimpleNamespace(title="Medication schedule", options={})
        self.assertEqual(
            [
                {
                    "options": {"printing_enabled": True, "copies": 3},
                    "title": "Grandma",
                }
            ],
            self._take_over(old, new),
        )

    def test_settings_of_the_new_entry_win(self) -> None:
        old = types.SimpleNamespace(title="Medication schedule", options={"copies": 3})
        new = types.SimpleNamespace(title="Medication schedule", options={"copies": 1})
        self.assertEqual([], self._take_over(old, new))


def _device(identifier, manufacturer="Medication Reminder", model="Local management"):
    return types.SimpleNamespace(
        identifiers={identifier}, manufacturer=manufacturer, model=model
    )


class _ConfigEntries:
    def __init__(self, entries) -> None:
        self.entries = entries
        self.removed = []
        self.unloaded = []
        self.updates = []

    def async_entries(self, domain):
        return [entry for entry in self.entries if entry.domain == domain]

    async def async_unload(self, entry_id) -> None:
        self.unloaded.append(entry_id)

    async def async_remove(self, entry_id) -> None:
        self.removed.append(entry_id)

    def async_update_entry(self, entry, **changes) -> None:
        self.updates.append((entry.entry_id, changes))


class TakeOverTests(unittest.IsolatedAsyncioTestCase):
    """Only entries the user confirmed and that carry our hub are moved."""

    def setUp(self) -> None:
        state = types.SimpleNamespace(LOADED="loaded")
        self.ours = types.SimpleNamespace(
            entry_id="ours",
            domain="medication_reminder",
            data={},
            state=state.LOADED,
            title="Medication schedule",
            options={},
        )
        # The other integration, with an empty entry as the worst case.
        self.other = types.SimpleNamespace(
            entry_id="other",
            domain="medication_reminder",
            data={},
            state=state.LOADED,
            title="Alex",
            options={},
        )
        devices = {
            "ours": [_device(("medication_reminder", "medication_reminder"))],
            "other": [_device(("medication_reminder", "other"), "Other", "Patient")],
        }
        self.config_entries = _ConfigEntries([self.ours, self.other])
        self.hass = types.SimpleNamespace(config_entries=self.config_entries)
        self.moved = []
        dr = types.SimpleNamespace(
            async_get=lambda _hass: devices,
            async_entries_for_config_entry=lambda reg, entry_id: reg.get(entry_id, []),
        )
        self.patches = [
            mock.patch.object(legacy, "dr", dr),
            mock.patch.object(
                legacy,
                "ConfigEntryState",
                types.SimpleNamespace(LOADED=state.LOADED),
            ),
            mock.patch.object(legacy, "_BUSY_STATES", ()),
            mock.patch.object(
                legacy, "async_copy_legacy_storage", mock.AsyncMock(return_value=True)
            ),
            mock.patch.object(
                legacy,
                "_move_registry_entries",
                lambda _hass, old, new: self.moved.append((old, new)),
            ),
            mock.patch.object(legacy, "_take_over_entry_settings", lambda *args: None),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def _new_entry(self, data):
        return types.SimpleNamespace(entry_id="new", data=data)

    async def test_nothing_moves_without_confirmation(self) -> None:
        await legacy.async_migrate_legacy_install(self.hass, self._new_entry({}))
        self.assertEqual([], self.moved)
        self.assertEqual([], self.config_entries.removed)
        self.assertEqual([], self.config_entries.unloaded)
        legacy.async_copy_legacy_storage.assert_not_awaited()

    def test_only_entries_with_our_hub_are_offered(self) -> None:
        self.assertEqual([self.ours], legacy.async_own_legacy_entries(self.hass))

    async def test_a_confirmed_entry_without_our_hub_is_left_alone(self) -> None:
        entry = self._new_entry({legacy.CONF_TAKE_OVER: ["other"]})
        await legacy.async_migrate_legacy_install(self.hass, entry)
        self.assertEqual([], self.moved)
        self.assertEqual([], self.config_entries.removed)
        self.assertEqual([], self.config_entries.unloaded)
        legacy.async_copy_legacy_storage.assert_not_awaited()
        self.assertEqual([("new", {"data": {}})], self.config_entries.updates)

    async def test_the_confirmed_install_moves_over_once(self) -> None:
        entry = self._new_entry({legacy.CONF_TAKE_OVER: ["ours"]})
        await legacy.async_migrate_legacy_install(self.hass, entry)
        self.assertEqual([("ours", "new")], self.moved)
        self.assertEqual(["ours"], self.config_entries.unloaded)
        self.assertEqual(["ours"], self.config_entries.removed)
        # The confirmation is used up, so nothing moves on the next start.
        self.assertEqual([("new", {"data": {}})], self.config_entries.updates)


if __name__ == "__main__":
    unittest.main()
