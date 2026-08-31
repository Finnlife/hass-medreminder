"""Binary sensor entities for Medication Reminder."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import MedicationEntity, MedicationReminderEntity, service_device_info
from .manager import MedicationManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up warning sensors."""
    manager: MedicationManager = hass.data[DOMAIN]["managers"][entry.entry_id]
    known: set[str] = set()

    @callback
    def add_medications() -> None:
        new = [item["id"] for item in manager.data["medications"] if item["id"] not in known]
        if new:
            known.update(new)
            async_add_entities(MedicationLowStockSensor(manager, item_id) for item_id in new)

    async_add_entities([OverdueIntakesSensor(manager)])
    add_medications()
    entry.async_on_unload(manager.async_add_listener(add_medications))


class MedicationLowStockSensor(MedicationEntity, BinarySensorEntity):
    """Whether one medication has reached its low-stock threshold."""

    _attr_name = "Niedriger Bestand"
    _attr_icon = "mdi:package-variant-minus"

    def __init__(self, manager: MedicationManager, medication_id: str) -> None:
        super().__init__(manager, medication_id, "low_stock")

    @property
    def is_on(self) -> bool | None:
        if not self.medication:
            return None
        return self.medication["stock"] <= self.medication["low_stock_threshold"]


class OverdueIntakesSensor(MedicationReminderEntity, BinarySensorEntity):
    """Whether at least one unresolved intake is currently due."""

    _attr_name = "Einnahme überfällig"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "overdue_intakes")
        self._attr_device_info = service_device_info()

    @property
    def is_on(self) -> bool:
        now = dt_util.now()
        return any(
            item["status"] in ("pending", "partial")
            and (value := dt_util.parse_datetime(item["scheduled_at"])) is not None
            and value <= now
            and (
                not item.get("snoozed_until")
                or (dt_util.parse_datetime(item["snoozed_until"]) or now) <= now
            )
            for item in self.manager.data["occurrences"]
        )

