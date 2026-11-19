"""Validation and serialization helpers for Medication Reminder."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from .const import (
    DEFAULT_AUTO_MISS_MINUTES,
    DEFAULT_REMINDER_WINDOW_MINUTES,
    DEFAULT_REPEAT_MINUTES,
)
from .schedule import INTERVAL, WEEKLY, parse_time

MAX_NOTES_LENGTH = 2000
MAX_TEXT_LENGTH = 200
# Every time of day is one intake, and the calendar and the catch-up after a
# restart walk all of them, so a plan cannot ask for more than one an hour.
MAX_TIMES_PER_DAY = 24


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
    name = text_field(raw.get("name"), "name")
    if not name:
        raise ValueError("Name is required")
    unit = text_field(raw.get("unit", "pieces"), "unit") or "pieces"
    threshold = _non_negative_number(
        raw.get("low_stock_threshold", 0), "low_stock_threshold"
    )
    return {
        "id": existing_id or str(raw.get("id") or new_id()),
        "name": name,
        "manufacturer": text_field(raw.get("manufacturer"), "manufacturer"),
        "barcode": text_field(raw.get("barcode"), "barcode"),
        "form": text_field(raw.get("form"), "form"),
        "strength": text_field(raw.get("strength"), "strength"),
        "unit": unit,
        "stock": 0,
        "stock_mode": "packages",
        "low_stock_threshold": threshold,
        "notes": text_field(raw.get("notes"), "notes", MAX_NOTES_LENGTH),
    }


def normalize_package(
    raw: dict[str, Any], medication_id: str, existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validate and normalize one physical medication package."""
    nickname = text_field(raw.get("nickname"), "nickname")
    lot_number = text_field(raw.get("lot_number"), "lot_number")
    expires_on = text_field(raw.get("expires_on"), "expires_on")
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
        "external_code": text_field(raw.get("external_code"), "external_code"),
        "initial_quantity": round(initial, 3),
        "remaining_quantity": remaining,
        "created_at": existing.get("created_at") if existing else None,
    }


def normalize_regimen(
    raw: dict[str, Any], medication_ids: set[str], existing_id: str | None = None
) -> dict[str, Any]:
    """Validate and normalize an intake regimen."""
    name = text_field(raw.get("name"), "name")
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
    schedule = normalize_schedule(raw.get("schedule", {}))
    return {
        "id": existing_id or str(raw.get("id") or new_id()),
        "name": name,
        "items": items,
        "schedule": schedule,
        **normalize_reminder(raw),
        "active": bool(raw.get("active", True)),
        "instructions": text_field(
            raw.get("instructions"), "instructions", MAX_NOTES_LENGTH
        ),
    }


# A reminder runs later without the context of the user who configured it, so
# it may only ever reach a notify service or start a script. Anything else would
# let a non-admin user make the integration call admin-only services.
NOTIFY_TARGET_PATTERN = re.compile(r"^notify\.[a-z0-9_]+$")
SCRIPT_ENTITY_PATTERN = re.compile(r"^script\.[a-z0-9_]+$")


def validate_reminder_targets(targets: Any, scripts: Any) -> None:
    """Reject reminder targets other than notify services and script entities."""
    if not isinstance(targets, list) or any(
        not isinstance(target, str) or not NOTIFY_TARGET_PATTERN.fullmatch(target)
        for target in targets
    ):
        raise ValueError("Reminder targets must be notify services (notify.*)")
    if not isinstance(scripts, list) or any(
        not isinstance(script, str) or not SCRIPT_ENTITY_PATTERN.fullmatch(script)
        for script in scripts
    ):
        raise ValueError("Reminder scripts must be script entities (script.*)")


def normalize_reminder(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate the reminder settings shared by plans and one-off intakes."""
    targets = sorted(
        {
            str(value).strip()
            for value in raw.get("notify_services") or []
            if str(value).strip()
        }
    )
    scripts = sorted(
        {
            str(value).strip()
            for value in raw.get("scripts") or []
            if str(value).strip()
        }
    )
    validate_reminder_targets(targets, scripts)
    repeat_minutes = _bounded_int(
        raw.get("repeat_minutes", DEFAULT_REPEAT_MINUTES), "repeat_minutes", 5, 1440
    )
    reminder_window = _bounded_int(
        raw.get("reminder_window_minutes", DEFAULT_REMINDER_WINDOW_MINUTES),
        "reminder_window_minutes",
        0,
        10080,
    )
    auto_miss = _bounded_int(
        raw.get("auto_miss_after_minutes", DEFAULT_AUTO_MISS_MINUTES),
        "auto_miss_after_minutes",
        0,
        43200,
    )
    if 0 < auto_miss < repeat_minutes:
        raise ValueError("auto_miss_after_minutes must not be below repeat_minutes")
    return {
        "notify_services": targets,
        "scripts": scripts,
        "repeat_minutes": repeat_minutes,
        "reminder_window_minutes": reminder_window,
        "auto_miss_after_minutes": auto_miss,
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


def ad_hoc_occurrence(
    title: str,
    scheduled_at: datetime,
    items: list[dict[str, Any]],
    reminder: dict[str, Any],
    reason: str = "",
    reference: str = "",
) -> dict[str, Any]:
    """Create a one-off intake ticket that carries its own reminder settings."""
    return {
        "id": new_id(),
        "regimen_id": None,
        "regimen_name": text_field(title, "title") or "Intake",
        "unplanned": False,
        "ad_hoc": True,
        "reason": text_field(reason, "reason", MAX_NOTES_LENGTH),
        "reference": text_field(reference, "reference"),
        "reminder": reminder,
        "scheduled_at": scheduled_at.isoformat(),
        "status": "pending",
        "items": [
            {
                "medication_id": item["medication_id"],
                "planned_dose": _positive_number(item["dose"], "dose"),
                "taken_dose": 0,
                "allocations": [],
            }
            for item in items
        ],
        "taken_at": None,
        "snoozed_until": None,
        "last_reminded_at": None,
        "reminders_sent": 0,
        "completed_by": None,
    }


def public_data(data: Any) -> Any:
    """Return a detached payload safe for websocket consumers."""
    return deepcopy(data)


def normalize_schedule(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate a schedule definition and return its canonical form."""
    schedule_type = raw.get("type")
    if schedule_type == WEEKLY:
        days: dict[str, list[str]] = {}
        raw_days = raw.get("days") or {}
        if not isinstance(raw_days, dict):
            raise ValueError("Unsupported schedule type")
        for day in range(7):
            values = raw_days.get(str(day), raw_days.get(day, []))
            if not isinstance(values, list):
                raise ValueError("Schedule times must be a list")
            normalized = sorted({_time_text(value) for value in values})
            if len(normalized) > MAX_TIMES_PER_DAY:
                raise ValueError(
                    f"A day can hold at most {MAX_TIMES_PER_DAY} intake times"
                )
            if normalized:
                days[str(day)] = normalized
        if not days:
            raise ValueError("At least one weekday is required")
        return {"type": WEEKLY, "days": days}
    if schedule_type == INTERVAL:
        every_days = _bounded_int(raw.get("every_days", 0), "every_days", 1, 365)
        start_date = str(raw.get("start_date", "")).strip()
        # Reject datetime strings so the stored anchor is always a plain date.
        date.fromisoformat(start_date)
        return {
            "type": INTERVAL,
            "every_days": every_days,
            "start_date": start_date,
            "time": _time_text(raw.get("time", "")),
        }
    raise ValueError("Unsupported schedule type")


def _time_text(value: Any) -> str:
    parsed = parse_time(value)
    return f"{parsed.hour:02d}:{parsed.minute:02d}"


def text_field(value: Any, field: str, limit: int = MAX_TEXT_LENGTH) -> str:
    """Return a stripped text value, rejecting anything that is not plain text."""
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set, bool)):
        raise ValueError(f"{field} must be text")
    text = str(value).strip()
    if len(text) > limit:
        raise ValueError(f"{field} is too long")
    return text


def _bounded_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{field} must be a whole number") from err
    if not minimum <= number <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return number


def _non_negative_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{field} must be a number") from err
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must not be negative")
    return round(number, 3)


def _positive_number(value: Any, field: str) -> float:
    number = _non_negative_number(value, field)
    if number <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return number


def resolve_intake_time(data: dict[str, Any], now: datetime) -> datetime:
    """Turn the mutually exclusive time options of a one-off intake into a datetime.

    `scheduled_at` is absolute, `in_minutes` is relative to now, and `time` means
    the next occurrence of that clock time unless `date` pins it to a day.
    """
    scheduled_at = data.get("scheduled_at")
    if isinstance(scheduled_at, datetime):
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=now.tzinfo)
        return scheduled_at
    if data.get("in_minutes") is not None:
        return now + timedelta(minutes=int(data["in_minutes"]))
    clock = data.get("time")
    if isinstance(clock, str):
        clock = parse_time(clock)
    if isinstance(clock, time):
        day = data.get("date")
        if isinstance(day, str):
            day = date.fromisoformat(day)
        moment = datetime.combine(day or now.date(), clock, tzinfo=now.tzinfo)
        if day is None and moment <= now:
            moment = datetime.combine(
                now.date() + timedelta(days=1), clock, tzinfo=now.tzinfo
            )
        return moment
    return now
