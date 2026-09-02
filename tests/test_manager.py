"""Focused invariant tests for stock mutation behavior."""

from datetime import datetime, timedelta
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


def _install_home_assistant_stubs() -> None:
    """Install the tiny subset needed to import the manager without Home Assistant."""
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
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

    core.Event = object
    core.HomeAssistant = object
    core.callback = lambda function: function
    event.async_track_time_interval = lambda *_args, **_kwargs: lambda: None
    storage.Store = Store
    dt.now = lambda: datetime.now().astimezone()
    dt.parse_datetime = lambda value: datetime.fromisoformat(value) if value else None
    dt.as_local = lambda value: value.astimezone()
    util.dt = dt
    sys.modules.update(
        {
            "homeassistant": ha,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.event": event,
            "homeassistant.helpers.storage": storage,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt,
        }
    )


def _import_component_module(name: str):
    root = Path(__file__).parents[1] / "custom_components" / "medication_reminder"
    package = types.ModuleType("custom_components.medication_reminder")
    package.__path__ = [str(root)]
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(root.parent)]
    sys.modules.setdefault("custom_components", custom_components)
    sys.modules.setdefault("custom_components.medication_reminder", package)
    return importlib.import_module(f"custom_components.medication_reminder.{name}")


_install_home_assistant_stubs()
manager_module = _import_component_module("manager")
models_module = _import_component_module("models")


class FakeBus:
    def __init__(self):
        self.events = []

    def async_fire(self, event, data):
        self.events.append((event, data))


class FakeServices:
    def __init__(self):
        self.calls = []

    def has_service(self, _domain, _service):
        return True

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))


class FakeHass:
    def __init__(self, language="en"):
        self.bus = FakeBus()
        self.services = FakeServices()
        self.config = types.SimpleNamespace(language=language)


class ManagerInvariantTests(unittest.IsolatedAsyncioTestCase):
    def manager_with_occurrence(self, second_stock: float):
        manager = manager_module.MedicationManager(FakeHass())
        manager.data = {
            "medications": [
                {
                    "id": "a",
                    "name": "A",
                    "unit": "pieces",
                    "stock": 10.0,
                    "stock_mode": "packages",
                    "low_stock_threshold": 2.0,
                },
                {
                    "id": "b",
                    "name": "B",
                    "unit": "pieces",
                    "stock": second_stock,
                    "stock_mode": "packages",
                    "low_stock_threshold": 2.0,
                },
            ],
            "regimens": [],
            # Stock always originates from physical packages.
            "packages": [
                {
                    "id": "base_a",
                    "medication_id": "a",
                    "nickname": "Base A",
                    "lot_number": "",
                    "expires_on": None,
                    "external_code": "",
                    "initial_quantity": 10.0,
                    "remaining_quantity": 10.0,
                    "created_at": "2026-01-01T00:00:00+02:00",
                },
                {
                    "id": "base_b",
                    "medication_id": "b",
                    "nickname": "Base B",
                    "lot_number": "",
                    "expires_on": None,
                    "external_code": "",
                    "initial_quantity": max(second_stock, 0.001),
                    "remaining_quantity": second_stock,
                    "created_at": "2026-01-01T00:00:00+02:00",
                },
            ],
            "occurrences": [
                {
                    "id": "ticket",
                    "regimen_id": "plan",
                    "scheduled_at": "2026-08-31T13:00:00+02:00",
                    "status": "pending",
                    "taken_at": None,
                    "completed_by": None,
                    "snoozed_until": None,
                    "last_reminded_at": None,
                    "reminders_sent": 0,
                    "items": [
                        {"medication_id": "a", "planned_dose": 1.0, "taken_dose": 0.0},
                        {"medication_id": "b", "planned_dose": 1.0, "taken_dose": 0.0},
                    ],
                }
            ],
        }
        return manager

    async def test_package_booking_is_atomic_across_medications(self) -> None:
        manager = self.manager_with_occurrence(second_stock=0.5)
        for medication in manager.data["medications"]:
            medication["stock_mode"] = "packages"
        manager.data["packages"] = [
            {
                "id": "pa",
                "medication_id": "a",
                "nickname": "Apollo",
                "lot_number": "A1",
                "expires_on": "2027-01-01",
                "initial_quantity": 10.0,
                "remaining_quantity": 10.0,
                "created_at": "2026-01-01T00:00:00+00:00",
                "external_code": "",
            },
            {
                "id": "pb",
                "medication_id": "b",
                "nickname": "Bumblebee",
                "lot_number": "B1",
                "expires_on": "2027-01-01",
                "initial_quantity": 0.5,
                "remaining_quantity": 0.5,
                "created_at": "2026-01-01T00:00:00+00:00",
                "external_code": "",
            },
        ]
        with self.assertRaises(ValueError):
            await manager.async_record_intake("ticket", {"a": 1, "b": 1})
        self.assertEqual(
            [10.0, 0.5],
            [item["remaining_quantity"] for item in manager.data["packages"]],
        )
        self.assertEqual(
            [0.0, 0.0],
            [item["taken_dose"] for item in manager.data["occurrences"][0]["items"]],
        )

    async def test_new_package_adds_to_derived_stock(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        created = await manager.async_save_package(
            {
                "medication_id": "a",
                "quantity": 5,
                "nickname": "",
                "lot_number": "NEW",
                "expires_on": "2027-01-01",
            }
        )
        packages = [
            item for item in manager.data["packages"] if item["medication_id"] == "a"
        ]
        self.assertEqual("Apollo", created["nickname"])
        self.assertRegex(created["scan_code"], r"^med[A-Z2-9]{5}$")
        self.assertEqual({"Base A", "Apollo"}, {item["nickname"] for item in packages})
        self.assertEqual(15.0, manager.data["medications"][0]["stock"])
        self.assertEqual("packages", manager.data["medications"][0]["stock_mode"])

    async def test_delete_all_data_requires_confirmation_and_clears_store(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        with self.assertRaises(ValueError):
            await manager.async_delete_all_data("delete")
        self.assertEqual(2, len(manager.data["medications"]))

        await manager.async_delete_all_data("DELETE")
        self.assertEqual(models_module.empty_data(), manager.data)
        self.assertEqual(models_module.empty_data(), manager._store.saved[-1])

    async def test_full_backup_can_restore_replaced_data(self) -> None:
        manager = manager_module.MedicationManager(FakeHass())
        medication = await manager.async_save_medication(
            {"name": "Backup medicine", "unit": "pieces", "low_stock_threshold": 1}
        )
        await manager.async_save_package(
            {"medication_id": medication["id"], "quantity": 5, "nickname": "Apollo"}
        )
        download = await manager.async_export_backup()
        await manager.async_delete_all_data("DELETE")
        self.assertEqual([], manager.data["medications"])

        counts = await manager.async_import_backup(json.loads(download["content"]))
        self.assertEqual(1, counts["medications"])
        self.assertEqual(1, counts["packages"])
        self.assertEqual("Backup medicine", manager.data["medications"][0]["name"])
        self.assertEqual(5, manager.data["medications"][0]["stock"])

    async def test_failed_backup_save_restores_previous_live_data(self) -> None:
        manager = manager_module.MedicationManager(FakeHass())
        await manager.async_save_medication(
            {"name": "Live medicine", "unit": "pieces", "low_stock_threshold": 1}
        )
        download = await manager.async_export_backup()
        payload = json.loads(download["content"])
        payload["data"]["medications"][0]["name"] = "Imported medicine"
        previous = manager.data

        with (
            patch.object(
                manager, "_changed", AsyncMock(side_effect=RuntimeError("save failed"))
            ),
            self.assertRaisesRegex(RuntimeError, "save failed"),
        ):
            await manager.async_import_backup(payload)

        self.assertIs(previous, manager.data)
        self.assertEqual("Live medicine", manager.data["medications"][0]["name"])

    async def test_multi_medication_booking_is_atomic(self) -> None:
        manager = self.manager_with_occurrence(second_stock=0.5)
        with self.assertRaises(ValueError):
            await manager.async_record_intake("ticket", {"a": 1, "b": 1})
        self.assertEqual(
            [10.0, 0.5], [item["stock"] for item in manager.data["medications"]]
        )
        self.assertEqual(
            [0.0, 0.0],
            [item["taken_dose"] for item in manager.data["occurrences"][0]["items"]],
        )

    async def test_completed_action_is_idempotent(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        await manager.async_record_intake("ticket")
        await manager.async_record_intake("ticket")
        self.assertEqual(
            [9.0, 9.0], [item["stock"] for item in manager.data["medications"]]
        )
        self.assertEqual("taken", manager.data["occurrences"][0]["status"])

    async def test_saved_medication_stock_is_always_derived_from_packages(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        manager.data["packages"] = [
            {
                "id": "box",
                "medication_id": "a",
                "nickname": "Apollo",
                "remaining_quantity": 4.5,
            }
        ]
        updated = await manager.async_save_medication(
            {"id": "a", "name": "A", "stock": 999, "low_stock_threshold": 2}
        )
        created = await manager.async_save_medication(
            {"name": "C", "stock": 999, "low_stock_threshold": 1}
        )
        self.assertEqual(4.5, updated["stock"])
        self.assertEqual(0, created["stock"])
        self.assertEqual("packages", updated["stock_mode"])
        self.assertEqual("packages", created["stock_mode"])

    def test_normalizer_ignores_supplied_stock(self) -> None:
        medication = models_module.normalize_medication({"name": "A", "stock": "nan"})
        self.assertEqual(0, medication["stock"])
        self.assertEqual("packages", medication["stock_mode"])

    async def test_notification_payload_uses_configured_language(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        manager.hass.config.language = "de-DE"
        regimen = {
            "name": "Mittagsplan",
            "notify_services": ["notify.phone"],
            "scripts": [],
        }
        await manager._async_notify(regimen, manager.data["occurrences"][0])
        payload = manager.hass.services.calls[0][2]
        self.assertEqual("Medikamenteneinnahme", payload["title"])
        self.assertEqual("Alles genommen", payload["data"]["actions"][0]["title"])

    async def test_notification_payload_defaults_to_english(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        manager.hass.config.language = "fr"
        regimen = {
            "name": "Lunch schedule",
            "notify_services": ["notify.phone"],
            "scripts": [],
        }
        await manager._async_notify(regimen, manager.data["occurrences"][0])
        payload = manager.hass.services.calls[0][2]
        self.assertEqual("Medication intake", payload["title"])
        self.assertEqual("Mark all taken", payload["data"]["actions"][0]["title"])

    async def test_package_stock_uses_earliest_expiry_across_packages(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        manager.data["medications"] = [
            {
                "id": "a",
                "name": "A",
                "stock": 2.0,
                "stock_mode": "packages",
                "low_stock_threshold": 0,
            }
        ]
        manager.data["packages"] = [
            {
                "id": "late",
                "medication_id": "a",
                "nickname": "Nova",
                "lot_number": "L2",
                "expires_on": "2027-06-01",
                "initial_quantity": 1.5,
                "remaining_quantity": 1.5,
                "created_at": "2026-01-02T00:00:00+00:00",
                "external_code": "",
            },
            {
                "id": "early",
                "medication_id": "a",
                "nickname": "Sunny",
                "lot_number": "L1",
                "expires_on": "2026-12-01",
                "initial_quantity": 0.5,
                "remaining_quantity": 0.5,
                "created_at": "2026-01-01T00:00:00+00:00",
                "external_code": "",
            },
        ]
        manager.data["occurrences"][0]["items"] = [
            {
                "medication_id": "a",
                "planned_dose": 1.0,
                "taken_dose": 0.0,
                "allocations": [],
            }
        ]
        await manager.async_record_intake("ticket")
        item = manager.data["occurrences"][0]["items"][0]
        self.assertEqual(
            [("early", 0.5), ("late", 0.5)],
            [(part["package_id"], part["amount"]) for part in item["allocations"]],
        )
        self.assertEqual(
            [1.0, 0.0], [p["remaining_quantity"] for p in manager.data["packages"]]
        )
        self.assertEqual(1.0, manager.data["medications"][0]["stock"])

    async def test_unplanned_intake_uses_same_package_allocation(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        result = await manager.async_record_unplanned_intake(
            [{"medication_id": "a", "dose": 2.5}], user_id="user"
        )
        self.assertTrue(result["unplanned"])
        self.assertEqual("taken", result["status"])
        self.assertEqual(7.5, manager.data["medications"][0]["stock"])
        self.assertEqual(
            [("base_a", 2.5)],
            [
                (part["package_id"], part["amount"])
                for part in result["items"][0]["allocations"]
            ],
        )

    async def test_postpone_interval_moves_anchor_and_current_ticket(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        manager.data["regimens"] = [
            {
                "id": "plan",
                "name": "Every three days",
                "active": True,
                "schedule": {
                    "type": "interval",
                    "every_days": 3,
                    "start_date": "2026-08-31",
                    "time": "13:00",
                },
            }
        ]
        fixed = datetime.fromisoformat("2026-08-31T14:00:00+02:00")
        with patch.object(manager_module.dt_util, "now", return_value=fixed):
            result = await manager.async_postpone_interval("ticket")
        self.assertTrue(result["scheduled_at"].startswith("2026-09-01T13:00:00"))
        self.assertEqual(
            "2026-09-01", manager.data["regimens"][0]["schedule"]["start_date"]
        )


class ReminderLoopTests(unittest.IsolatedAsyncioTestCase):
    """Cover reminder throttling, snoozing and the missed-intake timeout."""

    def build(self, **regimen_overrides):
        manager = manager_module.MedicationManager(FakeHass())
        now = datetime.now().astimezone()
        regimen = {
            "id": "plan",
            "name": "Morning",
            "active": True,
            "items": [{"medication_id": "a", "dose": 1.0}],
            "schedule": {"type": "weekly", "days": {}},
            "notify_services": ["notify.phone"],
            "scripts": [],
            "repeat_minutes": 30,
            "reminder_window_minutes": 0,
            "auto_miss_after_minutes": 0,
            "created_at": (now - timedelta(days=1)).isoformat(),
        }
        regimen.update(regimen_overrides)
        manager.data = {
            "medications": [
                {
                    "id": "a",
                    "name": "A",
                    "unit": "pieces",
                    "stock": 10.0,
                    "stock_mode": "packages",
                    "low_stock_threshold": 2.0,
                }
            ],
            "packages": [],
            "regimens": [regimen],
            "occurrences": [],
            "last_generated_at": (now - timedelta(minutes=1)).isoformat(),
        }
        return manager, now

    @staticmethod
    def ticket(now, minutes_ago, **overrides):
        occurrence = {
            "id": "ticket",
            "regimen_id": "plan",
            "regimen_name": "Morning",
            "unplanned": False,
            "scheduled_at": (now - timedelta(minutes=minutes_ago)).isoformat(),
            "status": "pending",
            "items": [
                {
                    "medication_id": "a",
                    "planned_dose": 1.0,
                    "taken_dose": 0.0,
                    "allocations": [],
                }
            ],
            "taken_at": None,
            "snoozed_until": None,
            "last_reminded_at": None,
            "reminders_sent": 0,
            "completed_by": None,
        }
        occurrence.update(overrides)
        return occurrence

    async def test_reminder_window_stops_notification_spam(self) -> None:
        manager, now = self.build(reminder_window_minutes=60)
        manager.data["occurrences"] = [self.ticket(now, 180)]
        await manager._async_tick(now)
        self.assertEqual([], manager.hass.services.calls)
        self.assertEqual(0, manager.data["occurrences"][0]["reminders_sent"])

    async def test_reminder_is_sent_inside_the_window(self) -> None:
        manager, now = self.build(reminder_window_minutes=60)
        manager.data["occurrences"] = [self.ticket(now, 5)]
        await manager._async_tick(now)
        self.assertEqual(1, len(manager.hass.services.calls))
        self.assertEqual(1, manager.data["occurrences"][0]["reminders_sent"])

    async def test_expired_snooze_reminds_before_the_repeat_interval(self) -> None:
        manager, now = self.build(repeat_minutes=240)
        manager.data["occurrences"] = [
            self.ticket(
                now,
                60,
                last_reminded_at=(now - timedelta(minutes=10)).isoformat(),
                snoozed_until=(now - timedelta(minutes=1)).isoformat(),
                reminders_sent=1,
            )
        ]
        await manager._async_tick(now)
        self.assertEqual(1, len(manager.hass.services.calls))
        self.assertIsNone(manager.data["occurrences"][0]["snoozed_until"])
        self.assertEqual(2, manager.data["occurrences"][0]["reminders_sent"])

    async def test_repeat_interval_throttles_without_snooze(self) -> None:
        manager, now = self.build(repeat_minutes=240)
        manager.data["occurrences"] = [
            self.ticket(
                now, 60, last_reminded_at=(now - timedelta(minutes=10)).isoformat()
            )
        ]
        await manager._async_tick(now)
        self.assertEqual([], manager.hass.services.calls)

    async def test_auto_miss_closes_abandoned_intakes(self) -> None:
        manager, now = self.build(auto_miss_after_minutes=60)
        manager.data["occurrences"] = [self.ticket(now, 120)]
        await manager._async_tick(now)
        occurrence = manager.data["occurrences"][0]
        self.assertEqual("missed", occurrence["status"])
        self.assertEqual([], manager.hass.services.calls)
        self.assertEqual(10.0, manager.data["medications"][0]["stock"])
        self.assertIn(
            "medication_reminder_missed",
            [event for event, _data in manager.hass.bus.events],
        )

    async def test_auto_miss_leaves_future_intakes_untouched(self) -> None:
        manager, now = self.build(auto_miss_after_minutes=60)
        manager.data["occurrences"] = [self.ticket(now, -30)]
        await manager._async_tick(now)
        self.assertEqual("pending", manager.data["occurrences"][0]["status"])

    async def test_editing_a_plan_drops_untouched_future_tickets(self) -> None:
        manager, now = self.build()
        manager.data["occurrences"] = [
            self.ticket(now, 60, id="past"),
            self.ticket(now, -60, id="future"),
            self.ticket(
                now,
                -120,
                id="future_touched",
                status="partial",
                items=[
                    {
                        "medication_id": "a",
                        "planned_dose": 2.0,
                        "taken_dose": 1.0,
                        "allocations": [],
                    }
                ],
            ),
        ]
        await manager.async_save_regimen(
            {
                "id": "plan",
                "name": "Evening",
                "items": [{"medication_id": "a", "dose": 1}],
                "schedule": {"type": "weekly", "days": {"0": ["20:00"]}},
            }
        )
        self.assertEqual(
            ["past", "future_touched"],
            [item["id"] for item in manager.data["occurrences"]],
        )
        self.assertEqual("Evening", manager.data["occurrences"][0]["regimen_name"])


class DashboardMetricTests(unittest.IsolatedAsyncioTestCase):
    """Cover the derived values that dashboards and entities rely on."""

    def build(self):
        manager = manager_module.MedicationManager(FakeHass())
        manager.data = {
            "medications": [
                {
                    "id": "a",
                    "name": "A",
                    "unit": "pieces",
                    "stock": 20.0,
                    "stock_mode": "packages",
                    "low_stock_threshold": 2.0,
                }
            ],
            "packages": [],
            "regimens": [
                {
                    "id": "plan",
                    "name": "Twice daily",
                    "active": True,
                    "items": [{"medication_id": "a", "dose": 1.0}],
                    "schedule": {
                        "type": "weekly",
                        "days": {str(day): ["08:00", "20:00"] for day in range(7)},
                    },
                    "notify_services": [],
                    "scripts": [],
                    "repeat_minutes": 30,
                    "reminder_window_minutes": 180,
                    "auto_miss_after_minutes": 0,
                }
            ],
            "occurrences": [],
            "last_generated_at": None,
        }
        return manager

    @staticmethod
    def history_entry(identifier, status, taken, planned=1.0):
        moment = (datetime.now().astimezone() - timedelta(days=1)).isoformat()
        return {
            "id": identifier,
            "regimen_id": "plan",
            "regimen_name": "Twice daily",
            "unplanned": False,
            "scheduled_at": moment,
            "status": status,
            "taken_at": moment,
            "items": [
                {
                    "medication_id": "a",
                    "planned_dose": planned,
                    "taken_dose": taken,
                    "allocations": [],
                }
            ],
        }

    def test_days_of_supply_uses_the_planned_daily_amount(self) -> None:
        manager = self.build()
        self.assertEqual(2.0, manager.daily_consumption("a"))
        self.assertEqual(10.0, manager.days_of_supply("a"))

    def test_days_of_supply_is_unknown_without_an_active_plan(self) -> None:
        manager = self.build()
        manager.data["regimens"][0]["active"] = False
        self.assertEqual(0.0, manager.daily_consumption("a"))
        self.assertIsNone(manager.days_of_supply("a"))

    def test_adherence_counts_partial_intakes_as_half(self) -> None:
        manager = self.build()
        manager.data["occurrences"] = [
            self.history_entry("1", "taken", 1.0),
            self.history_entry("2", "taken", 0.5),
            self.history_entry("3", "skipped", 0.0),
            self.history_entry("4", "missed", 0.0),
        ]
        adherence = manager.adherence()
        self.assertEqual(4, adherence["total"])
        self.assertEqual(1, adherence["taken"])
        self.assertEqual(1, adherence["partial"])
        self.assertEqual(1, adherence["skipped"])
        self.assertEqual(1, adherence["missed"])
        self.assertEqual(37.5, adherence["rate"])

    def test_adherence_ignores_unplanned_intakes(self) -> None:
        manager = self.build()
        entry = self.history_entry("u", "taken", 1.0)
        entry["unplanned"] = True
        manager.data["occurrences"] = [entry]
        self.assertEqual(0, manager.adherence()["total"])
        self.assertIsNone(manager.adherence()["rate"])


if __name__ == "__main__":
    unittest.main()
