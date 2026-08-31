"""Medication Reminder integration."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PANEL_STATIC_URL, PANEL_URL, PLATFORMS
from .manager import MedicationManager
from .websocket import async_register_websocket_api


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medication Reminder from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {"managers": {}})
    manager = MedicationManager(hass)
    await manager.async_initialize()
    domain_data["managers"][entry.entry_id] = manager

    if not domain_data.get("api_registered"):
        async_register_websocket_api(hass)
        _register_services(hass)
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    PANEL_STATIC_URL,
                    str(Path(__file__).parent / "frontend"),
                    cache_headers=False,
                )
            ]
        )
        domain_data["api_registered"] = True

    if not frontend.async_panel_exists(hass, PANEL_URL):
        await panel_custom.async_register_panel(
            hass=hass,
            webcomponent_name="medication-reminder-panel",
            frontend_url_path=PANEL_URL,
            module_url=f"{PANEL_STATIC_URL}/medication-reminder-panel.js?v=0.3.3",
            sidebar_title="Medications",
            sidebar_icon="mdi:pill-multiple",
            require_admin=False,
            config={},
            config_panel_domain=DOMAIN,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    manager: MedicationManager = hass.data[DOMAIN]["managers"].pop(entry.entry_id)
    await manager.async_close()
    if not hass.data[DOMAIN]["managers"]:
        frontend.async_remove_panel(hass, PANEL_URL)
    return True


def _active_manager(hass: HomeAssistant) -> MedicationManager:
    return next(iter(hass.data[DOMAIN]["managers"].values()))


def _register_services(hass: HomeAssistant) -> None:
    async def record(call: ServiceCall) -> None:
        doses = call.data.get("doses")
        await _active_manager(hass).async_record_intake(
            call.data["occurrence_id"], doses, call.context.user_id
        )

    async def snooze(call: ServiceCall) -> None:
        await _active_manager(hass).async_snooze(
            call.data["occurrence_id"],
            dt_util.now() + timedelta(minutes=call.data["minutes"]),
        )

    async def adjust_stock(call: ServiceCall) -> None:
        await _active_manager(hass).async_adjust_stock(
            call.data["medication_id"], call.data["delta"]
        )

    async def add_package(call: ServiceCall) -> None:
        await _active_manager(hass).async_save_package(dict(call.data))

    async def record_unplanned(call: ServiceCall) -> None:
        await _active_manager(hass).async_record_unplanned_intake(
            call.data["items"], call.context.user_id
        )

    async def postpone_interval(call: ServiceCall) -> None:
        await _active_manager(hass).async_postpone_interval(call.data["occurrence_id"])

    async def delete_all_data(call: ServiceCall) -> None:
        await _active_manager(hass).async_delete_all_data(call.data["confirmation"])

    hass.services.async_register(
        DOMAIN,
        "record_intake",
        record,
        schema=vol.Schema(
            {
                vol.Required("occurrence_id"): cv.string,
                vol.Optional("doses"): {cv.string: vol.Coerce(float)},
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "add_package",
        add_package,
        schema=vol.Schema(
            {
                vol.Required("medication_id"): cv.string,
                vol.Required("quantity"): vol.All(
                    vol.Coerce(float), vol.Range(min=0.001)
                ),
                vol.Optional("nickname", default=""): cv.string,
                vol.Optional("lot_number", default=""): cv.string,
                vol.Optional("expires_on", default=""): cv.string,
                vol.Optional("external_code", default=""): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "record_unplanned_intake",
        record_unplanned,
        schema=vol.Schema(
            {
                vol.Required("items"): [
                    {
                        vol.Required("medication_id"): cv.string,
                        vol.Required("dose"): vol.All(
                            vol.Coerce(float), vol.Range(min=0.001)
                        ),
                    }
                ]
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "postpone_interval",
        postpone_interval,
        schema=vol.Schema({vol.Required("occurrence_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "snooze",
        snooze,
        schema=vol.Schema(
            {
                vol.Required("occurrence_id"): cv.string,
                vol.Required("minutes", default=30): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=10080)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "adjust_stock",
        adjust_stock,
        schema=vol.Schema(
            {
                vol.Required("medication_id"): cv.string,
                vol.Required("delta"): vol.Coerce(float),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "delete_all_data",
        delete_all_data,
        schema=vol.Schema({vol.Required("confirmation"): cv.string}),
    )
