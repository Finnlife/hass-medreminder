"""Tests for offline QR-code generation."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).parents[1] / "custom_components" / "medication_reminder"
package = types.ModuleType("qr_test_package")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("qr_test_package", package)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"qr_test_package.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_load("scan_codes")
qr = _load("qr")


class QrTests(unittest.TestCase):
    """Protect the local scan-code contract."""

    def test_short_identifier_becomes_simple_version_one_svg(self) -> None:
        value = "med7K2QF"
        result = qr.qr_data_uri(value)
        self.assertTrue(result.startswith("data:image/svg+xml"))
        self.assertIn("%3Csvg", result)
        self.assertGreater(len(result), 500)
        self.assertEqual(1, qr.segno.make_qr(value, error="q").version)

    def test_non_medication_codes_are_rejected(self) -> None:
        for value in ("", "x" * 2049, "https://example.com", "medO0I1L"):
            with self.subTest(value=value[:30]), self.assertRaises(ValueError):
                qr.qr_data_uri(value)


if __name__ == "__main__":
    unittest.main()
