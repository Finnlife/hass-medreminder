"""Keep the entity and device registries in sync with the stored data."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .entity import package_id_from_unique_id


@callback
def async_prune_registries(
    hass: HomeAssistant, entry_id: str, data: dict[str, Any]
) -> None:
    """Remove registry entries of medications and packages that no longer exist."""
    medication_ids = {item["id"] for item in data.get("medications", [])}
    package_ids = {item["id"] for item in data.get("packages", [])}

    entity_registry = er.async_get(hass)
    for entity in list(er.async_entries_for_config_entry(entity_registry, entry_id)):
        package_id = package_id_from_unique_id(entity.unique_id)
        if package_id is not None and package_id not in package_ids:
            entity_registry.async_remove(entity.entity_id)

    device_registry = dr.async_get(hass)
    for device in list(dr.async_entries_for_config_entry(device_registry, entry_id)):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN or identifier == DOMAIN:
                continue
            if identifier not in medication_ids:
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=entry_id
                )


@callback
def async_registry_signature(data: dict[str, Any]) -> tuple[frozenset, frozenset]:
    """Return a cheap signature of everything the registries mirror."""
    return (
        frozenset(item["id"] for item in data.get("medications", [])),
        frozenset(item["id"] for item in data.get("packages", [])),
    )
