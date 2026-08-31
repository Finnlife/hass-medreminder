"""Pure schedule calculations for Medication Reminder."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Iterable


def parse_time(value: str) -> time:
    """Parse a strict HH:MM time."""
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("Time must use HH:MM")
    hour, minute = (int(part) for part in parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Invalid time")
    return time(hour, minute)


def occurrences_between(
    schedule: dict[str, Any], start: datetime, end: datetime
) -> list[datetime]:
    """Return scheduled datetimes in the inclusive interval."""
    if end < start:
        return []
    schedule_type = schedule.get("type")
    if schedule_type == "weekly":
        return _weekly_occurrences(schedule, start, end)
    if schedule_type == "interval":
        return _interval_occurrences(schedule, start, end)
    raise ValueError(f"Unsupported schedule type: {schedule_type}")


def next_occurrence(schedule: dict[str, Any], after: datetime) -> datetime | None:
    """Return the first scheduled datetime at or after a point in time."""
    candidates = occurrences_between(schedule, after, after + timedelta(days=370))
    return candidates[0] if candidates else None


def _weekly_occurrences(
    schedule: dict[str, Any], start: datetime, end: datetime
) -> list[datetime]:
    days = schedule.get("days", {})
    result: list[datetime] = []
    current = start.date()
    while current <= end.date():
        values: Iterable[str] = days.get(str(current.weekday()), [])
        for value in values:
            candidate = datetime.combine(current, parse_time(value), tzinfo=start.tzinfo)
            if start <= candidate <= end:
                result.append(candidate)
        current += timedelta(days=1)
    return sorted(set(result))


def _interval_occurrences(
    schedule: dict[str, Any], start: datetime, end: datetime
) -> list[datetime]:
    every = int(schedule.get("every_days", 0))
    if every < 1:
        raise ValueError("every_days must be at least 1")
    anchor_date = date.fromisoformat(schedule["start_date"])
    anchor = datetime.combine(anchor_date, parse_time(schedule["time"]), tzinfo=start.tzinfo)
    if end < anchor:
        return []
    if start <= anchor:
        first = anchor
    else:
        delta_days = (start.date() - anchor_date).days
        jumps = max(0, delta_days // every)
        first = anchor + timedelta(days=jumps * every)
        while first < start:
            first += timedelta(days=every)
    result: list[datetime] = []
    current = first
    while current <= end:
        result.append(current)
        current += timedelta(days=every)
    return result

