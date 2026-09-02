"""Sensor entities for Medication Reminder."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import (
    MedicationEntity,
    MedicationReminderEntity,
    package_unique_id,
)
from .manager import MedicationManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up global, per-medication and per-package sensors."""
    manager: MedicationManager = hass.data[DOMAIN]["managers"][entry.entry_id]
    known_medications: set[str] = set()
    known_packages: set[str] = set()

    @callback
    def add_dynamic_entities() -> None:
        new: list[SensorEntity] = []
        for medication in manager.data["medications"]:
            if medication["id"] in known_medications:
                continue
            known_medications.add(medication["id"])
            new.append(MedicationStockSensor(manager, medication["id"]))
            new.append(MedicationSupplySensor(manager, medication["id"]))
        for package in manager.data.get("packages", []):
            if package["id"] in known_packages:
                continue
            known_packages.add(package["id"])
            new.append(
                MedicationPackageStockSensor(
                    manager, package["medication_id"], package["id"]
                )
            )
        if new:
            async_add_entities(new)

    async_add_entities(
        [
            NextIntakeSensor(manager),
            PendingIntakesSensor(manager),
            OverdueIntakesCountSensor(manager),
            LastIntakeSensor(manager),
            AdherenceSensor(manager),
        ]
    )
    add_dynamic_entities()
    entry.async_on_unload(manager.async_add_listener(add_dynamic_entities))


class MedicationStockSensor(MedicationEntity, SensorEntity):
    """Current stock for one medication."""

    _attr_translation_key = "stock"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

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
        medication = self.medication
        if not medication:
            return {}
        packages = [
            package
            for package in self.manager.data.get("packages", [])
            if package["medication_id"] == self.medication_id
        ]
        open_packages = [
            package for package in packages if package["remaining_quantity"] > 0
        ]
        next_expiry = sorted(
            package["expires_on"] for package in open_packages if package["expires_on"]
        )
        return {
            "medication_id": self.medication_id,
            "low_stock_threshold": medication["low_stock_threshold"],
            "manufacturer": medication.get("manufacturer"),
            "barcode": medication.get("barcode"),
            "strength": medication.get("strength"),
            "form": medication.get("form"),
            "notes": medication.get("notes"),
            "scan_code": medication.get("scan_code"),
            "package_count": len(open_packages),
            "next_expiry": next_expiry[0] if next_expiry else None,
            "daily_consumption": self.manager.daily_consumption(self.medication_id),
        }


class MedicationSupplySensor(MedicationEntity, SensorEntity):
    """Estimated days the current stock still covers the active plans."""

    _attr_translation_key = "days_of_supply"
    _attr_icon = "mdi:calendar-range"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "d"
    _attr_suggested_display_precision = 1

    def __init__(self, manager: MedicationManager, medication_id: str) -> None:
        super().__init__(manager, medication_id, "days_of_supply")

    @property
    def native_value(self) -> float | None:
        return self.manager.days_of_supply(self.medication_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "medication_id": self.medication_id,
            "daily_consumption": self.manager.daily_consumption(self.medication_id),
        }


class MedicationPackageStockSensor(MedicationEntity, SensorEntity):
    """Remaining stock and metadata for one physical package."""

    _attr_icon = "mdi:package-variant-closed"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self, manager: MedicationManager, medication_id: str, package_id: str
    ) -> None:
        super().__init__(manager, medication_id, f"package_{package_id}_stock")
        self._attr_unique_id = package_unique_id(medication_id, package_id)
        self.package_id = package_id

    @property
    def package(self) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in self.manager.data.get("packages", [])
                if item["id"] == self.package_id
            ),
            None,
        )

    @property
    def available(self) -> bool:
        return self.medication is not None and self.package is not None

    @property
    def name(self) -> str | None:
        package = self.package
        return f"Package {package['nickname']}" if package else None

    @property
    def native_value(self) -> float | None:
        return self.package["remaining_quantity"] if self.package else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.medication["unit"] if self.medication else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        package = self.package
        if not package:
            return {}
        return {
            "package_id": self.package_id,
            "medication_id": self.medication_id,
            "nickname": package.get("nickname"),
            "lot_number": package.get("lot_number"),
            "expires_on": package.get("expires_on"),
            "initial_quantity": package["initial_quantity"],
            "external_code": package.get("external_code"),
            "scan_code": package.get("scan_code"),
        }


class NextIntakeSensor(MedicationReminderEntity, SensorEntity):
    """Timestamp of the next scheduled intake."""

    _attr_translation_key = "next_intake"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "next_intake")

    def _next(self) -> dict[str, Any] | None:
        upcoming = self.manager.upcoming(limit=1)
        return upcoming[0] if upcoming else None

    @property
    def native_value(self) -> datetime | None:
        value = self._next()
        return dt_util.parse_datetime(value["scheduled_at"]) if value else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        value = self._next()
        if not value:
            return {}
        return {
            "regimen_id": value["regimen_id"],
            "regimen_name": value["regimen_name"],
            "medications": [item["medication_name"] for item in value["items"]],
            "doses": {
                item["medication_name"]: item["dose"] for item in value["items"]
            },
        }


class PendingIntakesSensor(MedicationReminderEntity, SensorEntity):
    """Count of pending or partially completed intake tickets."""

    _attr_translation_key = "pending_intakes"
    _attr_icon = "mdi:clipboard-clock-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "pending_intakes")

    @property
    def native_value(self) -> int:
        return len(self.manager.open_occurrences())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        open_items = self.manager.open_occurrences()
        return {
            "occurrence_ids": [item["id"] for item in open_items],
            "summaries": [self.manager.occurrence_label(item) for item in open_items],
            "next_due": open_items[0]["scheduled_at"] if open_items else None,
        }


class OverdueIntakesCountSensor(MedicationReminderEntity, SensorEntity):
    """Count of intakes that are due and not snoozed."""

    _attr_translation_key = "overdue_count"
    _attr_icon = "mdi:alert-circle-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "overdue_count")

    @property
    def native_value(self) -> int:
        return len(self.manager.due_occurrences())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        due = self.manager.due_occurrences()
        return {
            "occurrence_ids": [item["id"] for item in due],
            "summaries": [self.manager.occurrence_label(item) for item in due],
        }


class LastIntakeSensor(MedicationReminderEntity, SensorEntity):
    """Timestamp of the latest completed intake."""

    _attr_translation_key = "last_intake"
    _attr_icon = "mdi:history"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "last_intake")

    def _latest(self) -> dict[str, Any] | None:
        completed = [
            item
            for item in self.manager.data["occurrences"]
            if item["status"] == "taken" and item.get("taken_at")
        ]
        return max(completed, key=lambda item: item["taken_at"]) if completed else None

    @property
    def native_value(self) -> datetime | None:
        latest = self._latest()
        return dt_util.parse_datetime(latest["taken_at"]) if latest else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latest = self._latest()
        if not latest:
            return {}
        return {
            "regimen_name": latest.get("regimen_name"),
            "unplanned": latest.get("unplanned", False),
            "summary": self.manager.occurrence_label(latest),
        }


class AdherenceSensor(MedicationReminderEntity, SensorEntity):
    """Share of scheduled intakes that were actually taken."""

    _attr_translation_key = "adherence"
    _attr_icon = "mdi:chart-donut"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 0
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "adherence")

    @property
    def native_value(self) -> float | None:
        return self.manager.adherence()["rate"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.manager.adherence()
