"""Shared entities for Medication Reminder."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import MedicationManager


class MedicationReminderEntity(Entity):
    """Base entity updated by the domain manager."""

    _attr_has_entity_name = True

    def __init__(self, manager: MedicationManager, unique_id: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))


class MedicationEntity(MedicationReminderEntity):
    """Entity attached to one medication device."""

    def __init__(self, manager: MedicationManager, medication_id: str, suffix: str) -> None:
        super().__init__(manager, f"{medication_id}_{suffix}")
        self.medication_id = medication_id

    @property
    def medication(self):
        return next(
            (
                item
                for item in self.manager.data["medications"]
                if item["id"] == self.medication_id
            ),
            None,
        )

    @property
    def available(self) -> bool:
        return self.medication is not None

    @property
    def device_info(self) -> DeviceInfo:
        medication = self.medication or {"name": "Deleted medication"}
        info = DeviceInfo(
            identifiers={(DOMAIN, self.medication_id)},
            name=medication["name"],
            manufacturer=medication.get("manufacturer") or None,
            model=medication.get("form") or "Medication",
        )
        if medication.get("barcode"):
            info["serial_number"] = medication["barcode"]
        return info


def service_device_info() -> DeviceInfo:
    """Return the integration's service device descriptor."""
    return DeviceInfo(
        identifiers={(DOMAIN, DOMAIN)},
        name="Medication schedule",
        manufacturer="Medication Reminder",
        model="Local management",
        translation_key="medication_schedule",
        entry_type=DeviceEntryType.SERVICE,
    )
