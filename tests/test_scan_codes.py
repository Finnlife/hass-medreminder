"""Tests for stable compact scan identifiers."""

import importlib.util
from pathlib import Path
import re
import unittest


PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "medication_reminder"
    / "scan_codes.py"
)
spec = importlib.util.spec_from_file_location(
    "medication_reminder_scan_codes_test", PATH
)
scan_codes = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(scan_codes)


class ScanCodeTests(unittest.TestCase):
    """Protect format, uniqueness, and migration idempotence."""

    def test_codes_are_short_deterministic_and_unambiguous(self) -> None:
        first = scan_codes.generate_scan_code("medications:abc", set())
        second = scan_codes.generate_scan_code("medications:abc", set())
        self.assertEqual(first, second)
        self.assertRegex(first, re.compile(r"^med[23456789A-HJ-NP-Z]{5}$"))
        self.assertEqual(8, len(first))

    def test_existing_codes_are_preserved_and_collisions_reassigned(self) -> None:
        data = {
            "medications": [{"id": "a", "scan_code": "medABCDE"}],
            "packages": [{"id": "b", "scan_code": "medABCDE"}],
            "occurrences": [{"id": "c"}],
        }
        scan_codes.ensure_scan_codes(data)
        values = [
            item["scan_code"]
            for collection in scan_codes.SCAN_CODE_COLLECTIONS
            for item in data[collection]
        ]
        self.assertEqual("medABCDE", values[0])
        self.assertEqual(3, len(set(values)))
        before = list(values)
        scan_codes.ensure_scan_codes(data)
        self.assertEqual(
            before,
            [
                item["scan_code"]
                for collection in scan_codes.SCAN_CODE_COLLECTIONS
                for item in data[collection]
            ],
        )


if __name__ == "__main__":
    unittest.main()
