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
from .qr import qr_data_uri
from .scan_codes import SCAN_CODE_PATTERN


def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register all panel commands once."""
    for command in (
        ws_get_state,
        ws_save_medication,
        ws_delete_medication,
        ws_save_package,
        ws_delete_package,
        ws_save_regimen,
        ws_delete_regimen,
        ws_record_intake,
        ws_record_unplanned_intake,
        ws_snooze,
        ws_postpone_interval,
        ws_generate_qr,
        ws_export_history,
        ws_skip,
        ws_delete_all_data,
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
    {
        vol.Required("type"): f"{DOMAIN}/save_medication",
        vol.Required("medication"): dict,
    }
)
@websocket_api.async_response
async def ws_save_medication(hass, connection, msg) -> None:
    await _respond(
        connection, msg, lambda: _manager(hass).async_save_medication(msg["medication"])
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete_medication",
        vol.Required("medication_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_medication(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_delete_medication(msg["medication_id"]),
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/save_package", vol.Required("package"): dict}
)
@websocket_api.async_response
async def ws_save_package(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_save_package(msg["package"]),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete_package",
        vol.Required("package_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_package(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_delete_package(msg["package_id"]),
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/save_regimen", vol.Required("regimen"): dict}
)
@websocket_api.async_response
async def ws_save_regimen(hass, connection, msg) -> None:
    await _respond(
        connection, msg, lambda: _manager(hass).async_save_regimen(msg["regimen"])
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete_regimen",
        vol.Required("regimen_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_regimen(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_delete_regimen(msg["regimen_id"]),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/record_intake",
        vol.Required("occurrence_id"): str,
        vol.Optional("doses"): {str: vol.Coerce(float)},
    }
)
@websocket_api.async_response
async def ws_record_intake(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_record_intake(
            msg["occurrence_id"], msg.get("doses"), connection.user.id
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/record_unplanned_intake",
        vol.Required("items"): list,
        vol.Optional("taken_at"): str,
    }
)
@websocket_api.async_response
async def ws_record_unplanned_intake(hass, connection, msg) -> None:
    taken_at = dt_util.parse_datetime(msg["taken_at"]) if msg.get("taken_at") else None
    if msg.get("taken_at") and taken_at is None:
        connection.send_error(msg["id"], "invalid_request", "Invalid intake time")
        return
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_record_unplanned_intake(
            msg["items"], connection.user.id, taken_at
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/snooze",
        vol.Required("occurrence_id"): str,
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
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_snooze(msg["occurrence_id"], until),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/postpone_interval",
        vol.Required("occurrence_id"): str,
    }
)
@websocket_api.async_response
async def ws_postpone_interval(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_postpone_interval(msg["occurrence_id"]),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/generate_qr",
        vol.Required("value"): vol.Match(SCAN_CODE_PATTERN.pattern),
    }
)
@websocket_api.async_response
async def ws_generate_qr(hass, connection, msg) -> None:
    """Generate an offline QR code for a panel scan link."""
    await _respond(
        connection,
        msg,
        lambda: _async_qr_result(msg["value"]),
    )


async def _async_qr_result(value: str) -> dict[str, str]:
    return {"value": value, "data_uri": qr_data_uri(value)}


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/export_history",
        vol.Required("start_date"): str,
        vol.Required("end_date"): str,
        vol.Required("format"): vol.In(("json", "csv")),
    }
)
@websocket_api.async_response
async def ws_export_history(hass, connection, msg) -> None:
    """Return a downloadable retained-history export."""
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_export_history(
            msg["start_date"], msg["end_date"], msg["format"]
        ),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/skip",
        vol.Required("occurrence_id"): str,
    }
)
@websocket_api.async_response
async def ws_skip(hass, connection, msg) -> None:
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_skip(msg["occurrence_id"], connection.user.id),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete_all_data",
        vol.Required("confirmation"): str,
    }
)
@websocket_api.async_response
async def ws_delete_all_data(hass, connection, msg) -> None:
    """Delete every persisted Medication Reminder record."""
    await _respond(
        connection,
        msg,
        lambda: _manager(hass).async_delete_all_data(msg["confirmation"]),
    )
