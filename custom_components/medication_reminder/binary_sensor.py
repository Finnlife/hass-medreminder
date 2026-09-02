"""Binary sensor entities for Medication Reminder."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import MedicationEntity, MedicationReminderEntity
from .manager import MedicationManager

EXPIRY_WARNING_DAYS = 30


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up warning sensors."""
    manager: MedicationManager = hass.data[DOMAIN]["managers"][entry.entry_id]
    known: set[str] = set()

    @callback
    def add_medications() -> None:
        new: list[BinarySensorEntity] = []
        for medication in manager.data["medications"]:
            if medication["id"] in known:
                continue
            known.add(medication["id"])
            new.append(MedicationLowStockSensor(manager, medication["id"]))
            new.append(MedicationExpirySensor(manager, medication["id"]))
        if new:
            async_add_entities(new)

    async_add_entities([OverdueIntakesSensor(manager)])
    add_medications()
    entry.async_on_unload(manager.async_add_listener(add_medications))


class MedicationLowStockSensor(MedicationEntity, BinarySensorEntity):
    """Whether one medication has reached its low-stock threshold."""

    _attr_translation_key = "low_stock"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, manager: MedicationManager, medication_id: str) -> None:
        super().__init__(manager, medication_id, "low_stock")

    @property
    def is_on(self) -> bool | None:
        medication = self.medication
        if not medication:
            return None
        return medication["stock"] <= medication["low_stock_threshold"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        medication = self.medication
        if not medication:
            return {}
        return {
            "stock": medication["stock"],
            "low_stock_threshold": medication["low_stock_threshold"],
            "days_of_supply": self.manager.days_of_supply(self.medication_id),
        }


class MedicationExpirySensor(MedicationEntity, BinarySensorEntity):
    """Whether a usable package expires within the warning window."""

    _attr_translation_key = "expiring_package"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, manager: MedicationManager, medication_id: str) -> None:
        super().__init__(manager, medication_id, "expiring_package")

    def _expiring(self) -> list[dict[str, Any]]:
        limit = (dt_util.now() + timedelta(days=EXPIRY_WARNING_DAYS)).date().isoformat()
        return [
            package
            for package in self.manager.data.get("packages", [])
            if package["medication_id"] == self.medication_id
            and package["remaining_quantity"] > 0
            and package.get("expires_on")
            and package["expires_on"] <= limit
        ]

    @property
    def is_on(self) -> bool | None:
        if not self.medication:
            return None
        return bool(self._expiring())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = dt_util.now().date().isoformat()
        expiring = self._expiring()
        return {
            "warning_days": EXPIRY_WARNING_DAYS,
            "packages": [package["nickname"] for package in expiring],
            "expired": [
                package["nickname"]
                for package in expiring
                if package["expires_on"] < today
            ],
            "next_expiry": min(
                (package["expires_on"] for package in expiring), default=None
            ),
        }


class OverdueIntakesSensor(MedicationReminderEntity, BinarySensorEntity):
    """Whether at least one unresolved intake is currently due."""

    _attr_translation_key = "overdue_intakes"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "overdue_intakes")

    @property
    def is_on(self) -> bool:
        return bool(self.manager.due_occurrences())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        due = self.manager.due_occurrences()
        return {
            "count": len(due),
            "occurrence_ids": [item["id"] for item in due],
            "summaries": [self.manager.occurrence_label(item) for item in due],
            "oldest_due": due[0]["scheduled_at"] if due else None,
        }
