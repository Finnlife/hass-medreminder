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
    known_packages: set[str] = set()

    @callback
    def add_medications() -> None:
        new = [
            item["id"]
            for item in manager.data["medications"]
            if item["id"] not in known
        ]
        if new:
            known.update(new)
            async_add_entities(
                MedicationStockSensor(manager, item_id) for item_id in new
            )

    @callback
    def add_packages() -> None:
        new = [
            item
            for item in manager.data.get("packages", [])
            if item["id"] not in known_packages
        ]
        if new:
            known_packages.update(item["id"] for item in new)
            async_add_entities(
                MedicationPackageStockSensor(manager, item["medication_id"], item["id"])
                for item in new
            )

    async_add_entities(
        [
            NextIntakeSensor(manager),
            PendingIntakesSensor(manager),
            LastIntakeSensor(manager),
        ]
    )
    add_medications()
    add_packages()

    @callback
    def add_dynamic_entities() -> None:
        add_medications()
        add_packages()

    entry.async_on_unload(manager.async_add_listener(add_dynamic_entities))


class MedicationStockSensor(MedicationEntity, SensorEntity):
    """Current stock for one medication."""

    _attr_translation_key = "stock"
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
            "stock_mode": self.medication.get("stock_mode", "manual"),
            "scan_code": self.medication.get("scan_code"),
            "package_count": len(
                [
                    package
                    for package in self.manager.data.get("packages", [])
                    if package["medication_id"] == self.medication_id
                    and package["remaining_quantity"] > 0
                ]
            ),
        }


class MedicationPackageStockSensor(MedicationEntity, SensorEntity):
    """Remaining stock and metadata for one physical package."""

    _attr_icon = "mdi:package-variant-closed"

    def __init__(
        self, manager: MedicationManager, medication_id: str, package_id: str
    ) -> None:
        super().__init__(manager, medication_id, f"package_{package_id}_stock")
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
        return self.package["nickname"] if self.package else None

    @property
    def native_value(self) -> float | None:
        return self.package["remaining_quantity"] if self.package else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.medication["unit"] if self.medication else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.package:
            return {}
        return {
            "package_id": self.package_id,
            "medication_id": self.medication_id,
            "lot_number": self.package.get("lot_number"),
            "expires_on": self.package.get("expires_on"),
            "initial_quantity": self.package["initial_quantity"],
            "external_code": self.package.get("external_code"),
            "scan_code": self.package.get("scan_code"),
        }


class NextIntakeSensor(MedicationReminderEntity, SensorEntity):
    """Timestamp of the next scheduled intake."""

    _attr_translation_key = "next_intake"
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

    _attr_translation_key = "pending_intakes"
    _attr_icon = "mdi:clipboard-clock-outline"

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
            ],
            "scan_codes": {
                item["id"]: item.get("scan_code")
                for item in self.manager.data["occurrences"]
                if item["status"] in ("pending", "partial")
            },
        }


class LastIntakeSensor(MedicationReminderEntity, SensorEntity):
    """Timestamp of the latest completed intake."""

    _attr_translation_key = "last_intake"
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
