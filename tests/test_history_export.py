"""Tests for date-ranged intake history exports."""

import csv
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).parents[1] / "custom_components" / "medication_reminder"
package = types.ModuleType("history_export_test_package")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("history_export_test_package", package)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"history_export_test_package.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_load("const")
history_export = _load("history_export")


class HistoryExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = {
            "medications": [{"id": "m", "name": "A, Special", "unit": "pieces"}],
            "regimens": [{"id": "r", "name": "Renamed schedule"}],
            "occurrences": [
                {
                    "id": "inside",
                    "regimen_id": "r",
                    "regimen_name": "Original schedule",
                    "unplanned": False,
                    "status": "taken",
                    "scheduled_at": "2026-08-31T13:00:00+02:00",
                    "taken_at": "2026-08-31T13:07:00+02:00",
                    "completed_by": "user",
                    "items": [
                        {
                            "medication_id": "m",
                            "planned_dose": 1,
                            "taken_dose": 1,
                            "taken_at": "2026-08-31T13:07:00+02:00",
                            "allocations": [
                                {
                                    "package_id": "p",
                                    "nickname": 'Box, "One"',
                                    "lot_number": "L1",
                                    "expires_on": "2027-01-01",
                                    "amount": 1,
                                    "taken_at": "2026-08-31T13:07:00+02:00",
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": "outside",
                    "status": "skipped",
                    "unplanned": False,
                    "scheduled_at": "2026-09-01T13:00:00+02:00",
                    "taken_at": "2026-09-01T13:01:00+02:00",
                    "items": [],
                },
                {
                    "id": "open",
                    "status": "pending",
                    "scheduled_at": "2026-08-31T15:00:00+02:00",
                    "items": [],
                },
            ],
        }

    def test_json_export_filters_inclusively_and_keeps_nested_details(self) -> None:
        result = history_export.build_history_export(
            self.data,
            "2026-08-31",
            "2026-08-31",
            "json",
            exported_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        payload = json.loads(result["content"])
        self.assertEqual(1, result["count"])
        self.assertEqual("inside", payload["occurrences"][0]["occurrence_id"])
        self.assertEqual(7, payload["occurrences"][0]["deviation_minutes"])
        self.assertEqual(
            'Box, "One"',
            payload["occurrences"][0]["items"][0]["allocations"][0]["nickname"],
        )
        self.assertEqual("Original schedule", payload["occurrences"][0]["regimen_name"])

    def test_csv_export_has_one_escaped_row_per_dose(self) -> None:
        result = history_export.build_history_export(
            self.data, "2026-08-31", "2026-08-31", "csv"
        )
        rows = list(csv.DictReader(io.StringIO(result["content"].lstrip("\ufeff"))))
        self.assertEqual(1, len(rows))
        self.assertEqual("A, Special", rows[0]["medication_name"])
        self.assertEqual("1", rows[0]["taken_dose"])
        self.assertEqual(
            'Box, "One"',
            json.loads(rows[0]["package_allocations"])[0]["nickname"],
        )

    def test_csv_escapes_spreadsheet_formulas(self) -> None:
        self.data["medications"][0]["name"] = "=DANGEROUS()"
        result = history_export.build_history_export(
            self.data, "2026-08-31", "2026-08-31", "csv"
        )
        row = next(csv.DictReader(io.StringIO(result["content"].lstrip("\ufeff"))))
        self.assertEqual("'=DANGEROUS()", row["medication_name"])

    def test_invalid_range_and_format_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Start date"):
            history_export.build_history_export(
                self.data, "2026-09-01", "2026-08-31", "json"
            )
        with self.assertRaisesRegex(ValueError, "format"):
            history_export.build_history_export(
                self.data, "2026-08-31", "2026-09-01", "xml"
            )


if __name__ == "__main__":
    unittest.main()
