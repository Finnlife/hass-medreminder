"""Tests for persistent storage migrations."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).parents[1] / "custom_components" / "medication_reminder"
package = types.ModuleType("migration_test_package")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("migration_test_package", package)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"migration_test_package.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_load("const")
migrations = _load("migrations")


class MigrationTests(unittest.TestCase):
    def test_v1_data_is_expanded_without_losing_history(self) -> None:
        old = {
            "medications": [{"id": "m", "name": "Medicine", "stock": 8}],
            "regimens": [],
            "occurrences": [
                {
                    "id": "o",
                    "regimen_id": "r",
                    "status": "taken",
                    "items": [
                        {"medication_id": "m", "planned_dose": 1, "taken_dose": 1}
                    ],
                }
            ],
        }
        migrated = migrations.migrate_storage(1, 1, old)
        self.assertEqual(8, migrated["medications"][0]["stock"])
        self.assertEqual("manual", migrated["medications"][0]["stock_mode"])
        self.assertEqual([], migrated["packages"])
        self.assertEqual([], migrated["occurrences"][0]["items"][0]["allocations"])
        self.assertNotIn("packages", old)

    def test_current_shape_migration_is_idempotent(self) -> None:
        once = migrations.migrate_storage(1, 1, {"medications": []})
        twice = migrations.migrate_storage(1, 2, once)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
