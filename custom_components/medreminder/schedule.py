"""Pure schedule calculations for Medication Reminder.

All helpers work on timezone-aware datetimes and keep the wall-clock time of a
schedule stable across daylight-saving transitions.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

WEEKLY = "weekly"
INTERVAL = "interval"
MAX_LOOKAHEAD_DAYS = 366


def parse_time(value: Any) -> time:
    """Parse a strict HH:MM time."""
    parts = str(value).split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("Time must use HH:MM")
    hour, minute = (int(part) for part in parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Invalid time")
    return time(hour, minute)


def schedule_times(schedule: dict[str, Any]) -> list[str]:
    """Return every distinct clock time used by a schedule."""
    if schedule.get("type") == WEEKLY:
        return sorted(
            {value for values in schedule.get("days", {}).values() for value in values}
        )
    if schedule.get("type") == INTERVAL:
        return [str(schedule.get("time", ""))]
    return []


def occurrences_per_day(schedule: dict[str, Any]) -> float:
    """Return the average number of intakes a schedule produces per day."""
    schedule_type = schedule.get("type")
    if schedule_type == WEEKLY:
        total = sum(len(values) for values in schedule.get("days", {}).values())
        return total / 7
    if schedule_type == INTERVAL:
        every = int(schedule.get("every_days", 0) or 0)
        return 1 / every if every > 0 else 0.0
    return 0.0


def occurrences_between(
    schedule: dict[str, Any], start: datetime, end: datetime
) -> list[datetime]:
    """Return scheduled datetimes in the inclusive interval."""
    if end < start:
        return []
    schedule_type = schedule.get("type")
    if schedule_type == WEEKLY:
        return _weekly_occurrences(schedule, start, end)
    if schedule_type == INTERVAL:
        return _interval_occurrences(schedule, start, end)
    raise ValueError(f"Unsupported schedule type: {schedule_type}")


def next_occurrence(schedule: dict[str, Any], after: datetime) -> datetime | None:
    """Return the first scheduled datetime at or after a point in time."""
    schedule_type = schedule.get("type")
    if schedule_type == WEEKLY:
        # A weekly plan repeats after seven days, so one extra day covers
        # every daylight-saving edge case without scanning a whole year.
        window = _weekly_occurrences(schedule, after, after + timedelta(days=8))
        return window[0] if window else None
    if schedule_type == INTERVAL:
        every = _every_days(schedule)
        candidate = _interval_first_at_or_after(schedule, after)
        if candidate is None:
            return None
        limit = after + timedelta(days=MAX_LOOKAHEAD_DAYS + every)
        return candidate if candidate <= limit else None
    raise ValueError(f"Unsupported schedule type: {schedule_type}")


def _weekly_occurrences(
    schedule: dict[str, Any], start: datetime, end: datetime
) -> list[datetime]:
    days = schedule.get("days", {})
    if not days:
        return []
    result: list[datetime] = []
    current = start.date()
    last = end.date()
    while current <= last:
        for value in days.get(str(current.weekday()), []):
            candidate = datetime.combine(
                current, parse_time(value), tzinfo=start.tzinfo
            )
            if start <= candidate <= end:
                result.append(candidate)
        current += timedelta(days=1)
    return sorted(set(result))


def _every_days(schedule: dict[str, Any]) -> int:
    every = int(schedule.get("every_days", 0))
    if every < 1:
        raise ValueError("every_days must be at least 1")
    return every


def _interval_first_at_or_after(
    schedule: dict[str, Any], moment: datetime
) -> datetime | None:
    """Return the first interval occurrence at or after a point in time."""
    every = _every_days(schedule)
    anchor_date = date.fromisoformat(str(schedule["start_date"]))
    clock = parse_time(schedule["time"])
    anchor = datetime.combine(anchor_date, clock, tzinfo=moment.tzinfo)
    if moment <= anchor:
        return anchor
    # Jump close to the target date first, then step to stay wall-clock exact.
    jumps = max(0, (moment.date() - anchor_date).days // every)
    candidate = datetime.combine(
        anchor_date + timedelta(days=jumps * every), clock, tzinfo=moment.tzinfo
    )
    while candidate < moment:
        jumps += 1
        candidate = datetime.combine(
            anchor_date + timedelta(days=jumps * every), clock, tzinfo=moment.tzinfo
        )
    return candidate


def _interval_occurrences(
    schedule: dict[str, Any], start: datetime, end: datetime
) -> list[datetime]:
    every = _every_days(schedule)
    anchor_date = date.fromisoformat(str(schedule["start_date"]))
    clock = parse_time(schedule["time"])
    current = _interval_first_at_or_after(schedule, start)
    if current is None:
        return []
    result: list[datetime] = []
    step = (current.date() - anchor_date).days // every
    while current <= end:
        result.append(current)
        step += 1
        current = datetime.combine(
            anchor_date + timedelta(days=step * every), clock, tzinfo=start.tzinfo
        )
    return result
