"""WebSocket API for the Medication Reminder panel."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .manager import MedicationManager


def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register all panel commands once."""
    for command in (
        ws_get_state,
        ws_save_medication,
        ws_delete_medication,
        ws_adjust_stock,
        ws_save_regimen,
        ws_delete_regimen,
        ws_record_intake,
        ws_snooze,
        ws_skip,
    ):
        websocket_api.async_register_command(hass, command)


def _manager(hass: HomeAssistant) -> MedicationManager:
    managers = hass.data.get(DOMAIN, {}).get("managers", {})
    if not managers:
        raise ValueError("Medication Reminder is not configured")
    return next(iter(managers.values()))


async def _respond(connection, msg, operation: Callable[[], Awaitable[Any]]) -> None:
    try:
        result = await operation()
    except (ValueError, TypeError, KeyError) as err:
        connection.send_error(msg["id"], "invalid_request", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_state"})
@websocket_api.async_response
async def ws_get_state(hass, connection, msg) -> None:
    """Return the complete app state."""
    connection.send_result(msg["id"], _manager(hass).snapshot())


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/save_medication", vol.Required("medication"): dict}
)
@websocket_api.async_response
async def ws_save_medication(hass, connection, msg) -> None:
    await _respond(connection, msg, lambda: _manager(hass).async_save_medication(msg["medication"]))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/delete_medication", vol.Required("id"): str}
)
@websocket_api.async_response
async def ws_delete_medication(hass, connection, msg) -> None:
    await _respond(connection, msg, lambda: _manager(hass).async_delete_medication(msg["id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/adjust_stock",
        vol.Required("id"): str,
        vol.Required("delta"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_adjust_stock(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_adjust_stock(msg["id"], msg["delta"]),
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/save_regimen", vol.Required("regimen"): dict}
)
@websocket_api.async_response
async def ws_save_regimen(hass, connection, msg) -> None:
    await _respond(connection, msg, lambda: _manager(hass).async_save_regimen(msg["regimen"]))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/delete_regimen", vol.Required("id"): str}
)
@websocket_api.async_response
async def ws_delete_regimen(hass, connection, msg) -> None:
    await _respond(connection, msg, lambda: _manager(hass).async_delete_regimen(msg["id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/record_intake",
        vol.Required("id"): str,
        vol.Optional("doses"): {str: vol.Coerce(float)},
    }
)
@websocket_api.async_response
async def ws_record_intake(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_record_intake(
            msg["id"], msg.get("doses"), connection.user.id
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/snooze",
        vol.Required("id"): str,
        vol.Exclusive("minutes", "snooze_target"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=10080)
        ),
        vol.Exclusive("until", "snooze_target"): str,
    }
)
@websocket_api.async_response
async def ws_snooze(hass, connection, msg) -> None:
    until = (
        dt_util.now() + timedelta(minutes=msg["minutes"])
        if "minutes" in msg
        else dt_util.parse_datetime(msg.get("until", ""))
    )
    if until is None:
        connection.send_error(msg["id"], "invalid_request", "Invalid snooze time")
        return
    await _respond(connection, msg, lambda: _manager(hass).async_snooze(msg["id"], until))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/skip", vol.Required("id"): str}
)
@websocket_api.async_response
async def ws_skip(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_skip(msg["id"], connection.user.id),
    )
