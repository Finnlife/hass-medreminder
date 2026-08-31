"""Tests for offline QR-code generation."""

import importlib.util
from pathlib import Path
import unittest


QR_PATH = (
    Path(__file__).parents[1] / "custom_components" / "medication_reminder" / "qr.py"
)
spec = importlib.util.spec_from_file_location("medication_reminder_qr_test", QR_PATH)
qr = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(qr)


class QrTests(unittest.TestCase):
    """Protect the local scan-code contract."""

    def test_scan_link_becomes_embedded_svg(self) -> None:
        value = "https://example.test/medication_reminder?scan=package:abc"
        result = qr.qr_data_uri(value)
        self.assertTrue(result.startswith("data:image/svg+xml"))
        self.assertIn("%3Csvg", result)
        self.assertGreater(len(result), 500)

    def test_empty_and_oversized_values_are_rejected(self) -> None:
        for value in ("", "x" * 2049):
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                qr.qr_data_uri(value)


if __name__ == "__main__":
    unittest.main()
