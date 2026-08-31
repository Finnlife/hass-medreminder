"""Sensor entities for Medication Reminder."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import MedicationEntity, MedicationReminderEntity, service_device_info
from .manager import MedicationManager
from .schedule import next_occurrence


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up global and per-medication sensors."""
    manager: MedicationManager = hass.data[DOMAIN]["managers"][entry.entry_id]
    known: set[str] = set()

    @callback
    def add_medications() -> None:
        new = [item["id"] for item in manager.data["medications"] if item["id"] not in known]
        if new:
            known.update(new)
            async_add_entities(MedicationStockSensor(manager, item_id) for item_id in new)

    async_add_entities(
        [
            NextIntakeSensor(manager),
            PendingIntakesSensor(manager),
            LastIntakeSensor(manager),
        ]
    )
    add_medications()
    entry.async_on_unload(manager.async_add_listener(add_medications))


class MedicationStockSensor(MedicationEntity, SensorEntity):
    """Current stock for one medication."""

    _attr_name = "Bestand"
    _attr_icon = "mdi:counter"

    def __init__(self, manager: MedicationManager, medication_id: str) -> None:
        super().__init__(manager, medication_id, "stock")

    @property
    def native_value(self) -> float | None:
        return self.medication["stock"] if self.medication else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.medication["unit"] if self.medication else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.medication:
            return {}
        return {
            "medication_id": self.medication_id,
            "low_stock_threshold": self.medication["low_stock_threshold"],
            "manufacturer": self.medication.get("manufacturer"),
            "barcode": self.medication.get("barcode"),
            "strength": self.medication.get("strength"),
        }


class NextIntakeSensor(MedicationReminderEntity, SensorEntity):
    """Timestamp of the next scheduled intake."""

    _attr_name = "Nächste Einnahme"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "next_intake")
        self._attr_device_info = service_device_info()

    def _next(self) -> tuple[datetime, dict[str, Any]] | None:
        now = dt_util.now()
        candidates = [
            (value, regimen)
            for regimen in self.manager.data["regimens"]
            if regimen.get("active", True)
            if (value := next_occurrence(regimen["schedule"], now)) is not None
        ]
        return min(candidates, key=lambda item: item[0]) if candidates else None

    @property
    def native_value(self) -> datetime | None:
        value = self._next()
        return value[0] if value else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        value = self._next()
        if not value:
            return {}
        return {"regimen_id": value[1]["id"], "regimen_name": value[1]["name"]}


class PendingIntakesSensor(MedicationReminderEntity, SensorEntity):
    """Count of pending or partially completed intake tickets."""

    _attr_name = "Offene Einnahmen"
    _attr_icon = "mdi:clipboard-clock-outline"
    _attr_native_unit_of_measurement = "Einnahmen"

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "pending_intakes")
        self._attr_device_info = service_device_info()

    @property
    def native_value(self) -> int:
        return sum(
            item["status"] in ("pending", "partial")
            for item in self.manager.data["occurrences"]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "occurrence_ids": [
                item["id"]
                for item in self.manager.data["occurrences"]
                if item["status"] in ("pending", "partial")
            ]
        }


class LastIntakeSensor(MedicationReminderEntity, SensorEntity):
    """Timestamp of the latest completed intake."""

    _attr_name = "Letzte Einnahme"
    _attr_icon = "mdi:history"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "last_intake")
        self._attr_device_info = service_device_info()

    @property
    def native_value(self) -> datetime | None:
        values = [
            dt_util.parse_datetime(item["taken_at"])
            for item in self.manager.data["occurrences"]
            if item["status"] == "taken" and item.get("taken_at")
        ]
        return max(values) if values else None

