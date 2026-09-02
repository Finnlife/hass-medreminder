"""Full Medication Reminder backup export and import validation."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import date, datetime
from typing import Any

from .const import ALL_STATUSES, STORAGE_MINOR_VERSION, STORAGE_VERSION
from .migrations import migrate_storage

BACKUP_FORMAT = "medication_reminder_backup"
BACKUP_VERSION = 1
COLLECTIONS = ("medications", "packages", "regimens", "occurrences")
OCCURRENCE_STATUSES = ALL_STATUSES


def build_backup_download(
    data: dict[str, Any], exported_at: datetime
) -> dict[str, Any]:
    """Return a downloadable versioned JSON backup without mutating source data."""
    envelope = {
        "format": BACKUP_FORMAT,
        "backup_version": BACKUP_VERSION,
        "storage_version": STORAGE_VERSION,
        "storage_minor_version": STORAGE_MINOR_VERSION,
        "exported_at": exported_at.isoformat(),
        "data": deepcopy(data),
    }
    timestamp = exported_at.strftime("%Y-%m-%d_%H-%M-%S")
    return {
        "filename": f"medication-reminder-backup_{timestamp}.json",
        "mime_type": "application/json;charset=utf-8",
        "content": json.dumps(envelope, ensure_ascii=False, indent=2),
    }


def prepare_backup_import(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and migrate a backup before it may replace live data."""
    if not isinstance(payload, dict) or payload.get("format") != BACKUP_FORMAT:
        raise ValueError("Invalid Medication Reminder backup")
    backup_version = _integer(payload.get("backup_version"), "backup_version")
    if backup_version != BACKUP_VERSION:
        raise ValueError("Unsupported backup version")
    major = _integer(payload.get("storage_version"), "storage_version")
    minor = _integer(payload.get("storage_minor_version"), "storage_minor_version")
    raw_data = payload.get("data")
    if not isinstance(raw_data, dict):
        raise ValueError("Backup data must be an object")
    for collection in COLLECTIONS:
        if collection in raw_data and not isinstance(raw_data[collection], list):
            raise ValueError(f"Backup collection {collection} must be a list")
    try:
        migrated = migrate_storage(major, minor, raw_data)
    except NotImplementedError as err:
        raise ValueError(str(err)) from err
    _validate_data(migrated)
    return migrated


def _validate_data(data: dict[str, Any]) -> None:
    for collection in COLLECTIONS:
        if not isinstance(data.get(collection), list):
            raise ValueError(f"Backup collection {collection} must be a list")

    medication_ids = _unique_ids(data["medications"], "medication")
    _unique_ids(data["packages"], "package")
    regimen_ids = _unique_ids(data["regimens"], "regimen")
    _unique_ids(data["occurrences"], "occurrence")

    for medication in data["medications"]:
        if not str(medication.get("name", "")).strip():
            raise ValueError("Medication name is required")
        _non_negative(medication.get("low_stock_threshold", 0), "warning threshold")
        if not str(medication.get("unit", "")).strip():
            raise ValueError("Medication stock unit is required")

    package_names: set[tuple[str, str]] = set()
    for package in data["packages"]:
        medication_id = _reference(package.get("medication_id"), "package medication")
        if medication_id not in medication_ids:
            raise ValueError("Package references an unknown medication")
        nickname = str(package.get("nickname", "")).strip()
        if not nickname:
            raise ValueError("Package nickname is required")
        name_key = (medication_id, nickname.casefold())
        if name_key in package_names:
            raise ValueError("Package nickname must be unique per medication")
        package_names.add(name_key)
        initial = _non_negative(
            package.get("initial_quantity"), "package initial quantity"
        )
        remaining = _non_negative(
            package.get("remaining_quantity"), "package remaining quantity"
        )
        if initial < remaining:
            raise ValueError("Package remaining quantity exceeds initial quantity")
        _optional_date(package.get("expires_on"), "package expiry date")

    for regimen in data["regimens"]:
        if not str(regimen.get("name", "")).strip():
            raise ValueError("Intake schedule name is required")
        items = regimen.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("Intake schedule requires medication items")
        seen: set[str] = set()
        for item in items:
            medication_id = _reference(item.get("medication_id"), "schedule medication")
            if medication_id not in medication_ids:
                raise ValueError("Intake schedule references an unknown medication")
            if medication_id in seen:
                raise ValueError("Medication occurs more than once in a schedule")
            seen.add(medication_id)
            _positive(item.get("dose"), "scheduled dose")
        _validate_schedule(regimen.get("schedule"))
        repeat = _integer(regimen.get("repeat_minutes", 30), "repeat_minutes")
        if not 5 <= repeat <= 1440:
            raise ValueError("repeat_minutes must be between 5 and 1440")
        _string_list(regimen.get("notify_services", []), "notification services")
        _string_list(regimen.get("scripts", []), "scripts")

    for occurrence in data["occurrences"]:
        status = occurrence.get("status")
        if status not in OCCURRENCE_STATUSES:
            raise ValueError("Occurrence has an unsupported status")
        _timestamp(occurrence.get("scheduled_at"), "occurrence scheduled time")
        _optional_timestamp(occurrence.get("taken_at"), "occurrence taken time")
        reminder = occurrence.get("reminder")
        if reminder is not None and not isinstance(reminder, dict):
            raise ValueError("Intake reminder settings must be an object")
        _optional_timestamp(occurrence.get("snoozed_until"), "occurrence snooze time")
        regimen_id = occurrence.get("regimen_id")
        if (
            status in ("pending", "partial")
            and _reference(regimen_id, "occurrence schedule") not in regimen_ids
        ):
            raise ValueError("Open occurrence references an unknown schedule")
        items = occurrence.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("Occurrence requires medication items")
        for item in items:
            medication_id = _reference(
                item.get("medication_id"), "occurrence medication"
            )
            if status in ("pending", "partial") and medication_id not in medication_ids:
                raise ValueError("Open occurrence references an unknown medication")
            planned = _positive(item.get("planned_dose"), "planned dose")
            taken = _non_negative(item.get("taken_dose", 0), "taken dose")
            if taken > planned:
                raise ValueError("Taken dose exceeds planned dose")
            allocations = item.get("allocations", [])
            if not isinstance(allocations, list):
                raise ValueError("Occurrence allocations must be a list")
            for allocation in allocations:
                _positive(allocation.get("amount"), "package allocation amount")
                _optional_timestamp(
                    allocation.get("taken_at"), "package allocation time"
                )
    _optional_timestamp(data.get("last_generated_at"), "last generated time")


def _unique_ids(items: list[dict[str, Any]], label: str) -> set[str]:
    result: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"Backup {label} must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip() or item_id in result:
            raise ValueError(f"Backup {label} IDs must be non-empty and unique")
        result.add(item_id)
    return result


def _reference(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} reference must be a non-empty string")
    return value


def _validate_schedule(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise ValueError("Intake schedule must be an object")
    if raw.get("type") == "weekly":
        days = raw.get("days")
        if not isinstance(days, dict) or not days:
            raise ValueError("Weekly schedule requires weekdays")
        for day, values in days.items():
            if str(day) not in {str(value) for value in range(7)}:
                raise ValueError("Weekly schedule contains an invalid weekday")
            if not isinstance(values, list) or not values:
                raise ValueError("Weekly schedule requires times")
            for value in values:
                _time(value)
        return
    if raw.get("type") == "interval":
        every_days = _integer(raw.get("every_days"), "every_days")
        if not 1 <= every_days <= 365:
            raise ValueError("every_days must be between 1 and 365")
        _optional_date(raw.get("start_date"), "interval start date", required=True)
        _time(raw.get("time"))
        return
    raise ValueError("Unsupported schedule type")


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{field} must be an integer") from err
    if str(number) != str(value):
        raise ValueError(f"{field} must be an integer")
    return number


def _non_negative(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{field} must be a number") from err
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must not be negative")
    return number


def _positive(value: Any, field: str) -> float:
    number = _non_negative(value, field)
    if number <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return number


def _optional_date(value: Any, field: str, *, required: bool = False) -> None:
    if value in (None, "") and not required:
        return
    try:
        date.fromisoformat(str(value))
    except ValueError as err:
        raise ValueError(f"{field} is invalid") from err


def _timestamp(value: Any, field: str) -> None:
    if value in (None, ""):
        raise ValueError(f"{field} is required")
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError(f"{field} is invalid") from err


def _optional_timestamp(value: Any, field: str) -> None:
    if value not in (None, ""):
        _timestamp(value, field)


def _string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")


def _time(value: Any) -> None:
    try:
        datetime.strptime(str(value), "%H:%M")
    except ValueError as err:
        raise ValueError("Schedule time must use HH:MM") from err
