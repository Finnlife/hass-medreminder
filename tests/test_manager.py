"""Focused invariant tests for stock mutation behavior."""

from datetime import datetime
import importlib
from pathlib import Path
import sys
import types
import unittest


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
        def __init__(self, *_args, **_kwargs): self.saved = []
        @classmethod
        def __class_getitem__(cls, _item): return cls
        async def async_load(self): return None
        async def async_save(self, data): self.saved.append(data)

    core.Event = object
    core.HomeAssistant = object
    core.callback = lambda function: function
    event.async_track_time_interval = lambda *_args, **_kwargs: lambda: None
    storage.Store = Store
    dt.now = lambda: datetime.now().astimezone()
    dt.parse_datetime = lambda value: datetime.fromisoformat(value) if value else None
    dt.as_local = lambda value: value.astimezone()
    util.dt = dt
    sys.modules.update({
        "homeassistant": ha,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.event": event,
        "homeassistant.helpers.storage": storage,
        "homeassistant.util": util,
        "homeassistant.util.dt": dt,
    })


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
    def __init__(self): self.events = []
    def async_fire(self, event, data): self.events.append((event, data))


class FakeHass:
    def __init__(self): self.bus = FakeBus()


class ManagerInvariantTests(unittest.IsolatedAsyncioTestCase):
    def manager_with_occurrence(self, second_stock: float):
        manager = manager_module.MedicationManager(FakeHass())
        manager.data = {
            "medications": [
                {"id": "a", "name": "A", "stock": 10.0, "low_stock_threshold": 2.0},
                {"id": "b", "name": "B", "stock": second_stock, "low_stock_threshold": 2.0},
            ],
            "regimens": [],
            "occurrences": [{
                "id": "ticket", "regimen_id": "plan", "scheduled_at": "2026-08-31T13:00:00+02:00",
                "status": "pending", "taken_at": None, "completed_by": None,
                "snoozed_until": None, "last_reminded_at": None, "reminders_sent": 0,
                "items": [
                    {"medication_id": "a", "planned_dose": 1.0, "taken_dose": 0.0},
                    {"medication_id": "b", "planned_dose": 1.0, "taken_dose": 0.0},
                ],
            }],
        }
        return manager

    async def test_multi_medication_booking_is_atomic(self) -> None:
        manager = self.manager_with_occurrence(second_stock=0.5)
        with self.assertRaises(ValueError):
            await manager.async_record_intake("ticket", {"a": 1, "b": 1})
        self.assertEqual([10.0, 0.5], [item["stock"] for item in manager.data["medications"]])
        self.assertEqual([0.0, 0.0], [item["taken_dose"] for item in manager.data["occurrences"][0]["items"]])

    async def test_completed_action_is_idempotent(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        await manager.async_record_intake("ticket")
        await manager.async_record_intake("ticket")
        self.assertEqual([9.0, 9.0], [item["stock"] for item in manager.data["medications"]])
        self.assertEqual("taken", manager.data["occurrences"][0]["status"])

    async def test_nan_stock_adjustment_is_rejected(self) -> None:
        manager = self.manager_with_occurrence(second_stock=10)
        with self.assertRaises(ValueError):
            await manager.async_adjust_stock("a", float("nan"))
        self.assertEqual(10.0, manager.data["medications"][0]["stock"])

    def test_nan_medication_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            models_module.normalize_medication({"name": "A", "stock": "nan"})


if __name__ == "__main__":
    unittest.main()
