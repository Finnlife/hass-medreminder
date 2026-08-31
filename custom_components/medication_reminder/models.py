"""Validation and serialization helpers for Medication Reminder."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import math
from typing import Any
from uuid import uuid4

from .schedule import occurrences_between, parse_time


def new_id() -> str:
    """Return a compact random identifier."""
    return uuid4().hex


def empty_data() -> dict[str, Any]:
    """Return a fresh storage payload."""
    return {
        "medications": [],
        "packages": [],
        "regimens": [],
        "occurrences": [],
        "last_generated_at": None,
    }


def normalize_medication(
    raw: dict[str, Any], existing_id: str | None = None
) -> dict[str, Any]:
    """Validate and normalize a medication."""
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("Name is required")
    unit = str(raw.get("unit", "pieces")).strip() or "pieces"
    stock = _non_negative_number(raw.get("stock", 0), "stock")
    threshold = _non_negative_number(
        raw.get("low_stock_threshold", 0), "low_stock_threshold"
    )
    stock_mode = str(raw.get("stock_mode", "manual"))
    if stock_mode not in ("manual", "packages"):
        raise ValueError("Unsupported stock mode")
    return {
        "id": existing_id or str(raw.get("id") or new_id()),
        "name": name,
        "manufacturer": str(raw.get("manufacturer", "")).strip(),
        "barcode": str(raw.get("barcode", "")).strip(),
        "form": str(raw.get("form", "")).strip(),
        "strength": str(raw.get("strength", "")).strip(),
        "unit": unit,
        "stock": stock,
        "stock_mode": stock_mode,
        "low_stock_threshold": threshold,
        "notes": str(raw.get("notes", "")).strip(),
    }


def normalize_package(
    raw: dict[str, Any], medication_id: str, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validate and normalize one physical medication package."""
    nickname = str(raw.get("nickname", "")).strip()
    lot_number = str(raw.get("lot_number", "")).strip()
    expires_on = str(raw.get("expires_on", "")).strip()
    if expires_on:
        date.fromisoformat(expires_on)
    remaining = _non_negative_number(
        raw.get("remaining_quantity", raw.get("quantity", 0)), "remaining_quantity"
    )
    if existing is None and remaining <= 0:
        raise ValueError("Package quantity must be greater than zero")
    initial = (
        max(float(existing["initial_quantity"]), remaining)
        if existing
        else _positive_number(raw.get("quantity", remaining), "quantity")
    )
    return {
        "id": existing["id"] if existing else str(raw.get("id") or new_id()),
        "medication_id": medication_id,
        "nickname": nickname,
        "lot_number": lot_number,
        "expires_on": expires_on or None,
        "external_code": str(raw.get("external_code", "")).strip(),
        "initial_quantity": round(initial, 3),
        "remaining_quantity": remaining,
        "created_at": existing.get("created_at") if existing else None,
    }


def normalize_regimen(
    raw: dict[str, Any], medication_ids: set[str], existing_id: str | None = None
) -> dict[str, Any]:
    """Validate and normalize an intake regimen."""
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("Name is required")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw.get("items", []):
        medication_id = str(item.get("medication_id", ""))
        if medication_id not in medication_ids:
            raise ValueError("Unknown medication")
        if medication_id in seen:
            raise ValueError("Medication occurs more than once")
        seen.add(medication_id)
        items.append(
            {
                "medication_id": medication_id,
                "dose": _positive_number(item.get("dose"), "dose"),
            }
        )
    if not items:
        raise ValueError("At least one medication is required")
    schedule = _normalize_schedule(raw.get("schedule", {}))
    targets = sorted(
        {
            str(value).strip()
            for value in raw.get("notify_services", [])
            if str(value).strip()
        }
    )
    scripts = sorted(
        {str(value).strip() for value in raw.get("scripts", []) if str(value).strip()}
    )
    repeat_minutes = int(raw.get("repeat_minutes", 30))
    if not 5 <= repeat_minutes <= 1440:
        raise ValueError("repeat_minutes must be between 5 and 1440")
    return {
        "id": existing_id or str(raw.get("id") or new_id()),
        "name": name,
        "items": items,
        "schedule": schedule,
        "notify_services": targets,
        "scripts": scripts,
        "repeat_minutes": repeat_minutes,
        "active": bool(raw.get("active", True)),
        "instructions": str(raw.get("instructions", "")).strip(),
    }


def occurrence_for(regimen: dict[str, Any], scheduled_at: datetime) -> dict[str, Any]:
    """Create a persistent occurrence ticket."""
    return {
        "id": new_id(),
        "regimen_id": regimen["id"],
        "regimen_name": regimen["name"],
        "unplanned": False,
        "scheduled_at": scheduled_at.isoformat(),
        "status": "pending",
        "items": [
            {
                "medication_id": item["medication_id"],
                "planned_dose": item["dose"],
                "taken_dose": 0,
                "allocations": [],
            }
            for item in regimen["items"]
        ],
        "taken_at": None,
        "snoozed_until": None,
        "last_reminded_at": None,
        "reminders_sent": 0,
        "completed_by": None,
    }


def public_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return a detached payload safe for websocket consumers."""
    return deepcopy(data)


def _normalize_schedule(raw: dict[str, Any]) -> dict[str, Any]:
    schedule_type = raw.get("type")
    if schedule_type == "weekly":
        days: dict[str, list[str]] = {}
        for day in range(7):
            values = raw.get("days", {}).get(str(day), [])
            normalized = sorted({str(value) for value in values})
            for value in normalized:
                parse_time(value)
            if normalized:
                days[str(day)] = normalized
        if not days:
            raise ValueError("At least one weekday is required")
        schedule = {"type": "weekly", "days": days}
    elif schedule_type == "interval":
        every_days = int(raw.get("every_days", 0))
        if every_days < 1 or every_days > 365:
            raise ValueError("every_days must be between 1 and 365")
        start_date = str(raw.get("start_date", ""))
        datetime.fromisoformat(start_date)
        value = str(raw.get("time", ""))
        parse_time(value)
        schedule = {
            "type": "interval",
            "every_days": every_days,
            "start_date": start_date,
            "time": value,
        }
    else:
        raise ValueError("Unsupported schedule type")
    # Exercise the calculator during validation to reject malformed edge cases.
    now = datetime.now().astimezone()
    occurrences_between(schedule, now, now)
    return schedule


def _non_negative_number(value: Any, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must not be negative")
    return round(number, 3)


def _positive_number(value: Any, field: str) -> float:
    number = _non_negative_number(value, field)
    if number <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return number
