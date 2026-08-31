"""Tests for the pure schedule calculator."""

from datetime import datetime
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "medication_reminder"
    / "schedule.py"
)
SPEC = importlib.util.spec_from_file_location("medication_schedule", MODULE_PATH)
schedule = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(schedule)


class ScheduleTests(unittest.TestCase):
    """Exercise weekly and interval boundary behavior."""

    def setUp(self) -> None:
        self.tz = ZoneInfo("Europe/Berlin")

    def test_weekdays_and_weekend_have_different_times(self) -> None:
        plan = {
            "type": "weekly",
            "days": {
                "0": ["13:00"], "1": ["13:00"], "2": ["13:00"],
                "3": ["13:00"], "4": ["13:00"], "5": ["11:00"], "6": ["11:00"],
            },
        }
        values = schedule.occurrences_between(
            plan,
            datetime(2026, 8, 31, 0, 0, tzinfo=self.tz),
            datetime(2026, 9, 6, 23, 59, tzinfo=self.tz),
        )
        self.assertEqual(7, len(values))
        self.assertEqual([13, 13, 13, 13, 13, 11, 11], [item.hour for item in values])

    def test_weekly_includes_exact_boundaries_once(self) -> None:
        point = datetime(2026, 8, 31, 13, 0, tzinfo=self.tz)
        self.assertEqual(
            [point],
            schedule.occurrences_between(
                {"type": "weekly", "days": {"0": ["13:00", "13:00"]}}, point, point
            ),
        )

    def test_interval_stays_anchored_to_start_date(self) -> None:
        plan = {"type": "interval", "every_days": 3, "start_date": "2026-08-30", "time": "08:15"}
        values = schedule.occurrences_between(
            plan,
            datetime(2026, 9, 1, 0, 0, tzinfo=self.tz),
            datetime(2026, 9, 10, 23, 59, tzinfo=self.tz),
        )
        self.assertEqual([2, 5, 8], [item.day for item in values])
        self.assertTrue(all(item.hour == 8 and item.minute == 15 for item in values))

    def test_next_occurrence_skips_past_time_today(self) -> None:
        value = schedule.next_occurrence(
            {"type": "weekly", "days": {"0": ["11:00"], "1": ["12:30"]}},
            datetime(2026, 8, 31, 13, 0, tzinfo=self.tz),
        )
        self.assertEqual(datetime(2026, 9, 1, 12, 30, tzinfo=self.tz), value)

    def test_invalid_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            schedule.parse_time("24:00")


if __name__ == "__main__":
    unittest.main()

