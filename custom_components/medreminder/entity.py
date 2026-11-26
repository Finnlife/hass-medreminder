"""Shared entities for Medication Reminder."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import MedicationManager

# Home Assistant 2026.11 deprecated linking a device to its parent by identifier
# and raises when an entity is re-added that way, for example after its entity
# id was changed. Older versions do not know the registry-id variant yet.
VIA_DEVICE_ID_SUPPORTED = "via_device_id" in DeviceInfo.__annotations__

PACKAGE_UNIQUE_ID_MARKER = "_package_"
PACKAGE_UNIQUE_ID_SUFFIX = "_stock"


def package_unique_id(medication_id: str, package_id: str) -> str:
    """Return the stable unique id of one package stock sensor."""
    return (
        f"{DOMAIN}_{medication_id}"
        f"{PACKAGE_UNIQUE_ID_MARKER}{package_id}{PACKAGE_UNIQUE_ID_SUFFIX}"
    )


def package_id_from_unique_id(unique_id: str) -> str | None:
    """Return the package id encoded in a unique id, when it is a package sensor."""
    if PACKAGE_UNIQUE_ID_MARKER not in unique_id or not unique_id.endswith(
        PACKAGE_UNIQUE_ID_SUFFIX
    ):
        return None
    start = unique_id.index(PACKAGE_UNIQUE_ID_MARKER) + len(PACKAGE_UNIQUE_ID_MARKER)
    return unique_id[start : -len(PACKAGE_UNIQUE_ID_SUFFIX)] or None


class MedicationReminderEntity(Entity):
    """Base entity updated by the domain manager."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: MedicationManager, unique_id: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_device_info = service_device_info()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))


class MedicationEntity(MedicationReminderEntity):
    """Entity attached to one medication device."""

    def __init__(
        self, manager: MedicationManager, medication_id: str, suffix: str
    ) -> None:
        super().__init__(manager, f"{medication_id}_{suffix}")
        self.medication_id = medication_id

    @property
    def medication(self) -> dict[str, Any] | None:
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
        medication = self.medication or {"name": "Medication"}
        info = DeviceInfo(
            identifiers={(DOMAIN, self.medication_id)},
            name=medication["name"],
            manufacturer=medication.get("manufacturer") or None,
            model=" ".join(
                part
                for part in (medication.get("strength"), medication.get("form"))
                if part
            )
            or "Medication",
        )
        hub_device_id = getattr(self.manager, "hub_device_id", None)
        if VIA_DEVICE_ID_SUPPORTED and hub_device_id:
            info["via_device_id"] = hub_device_id
        else:
            info["via_device"] = (DOMAIN, DOMAIN)
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
