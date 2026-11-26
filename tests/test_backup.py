"""Tests for full backup export, validation, and migration."""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).parents[1] / "custom_components" / "medreminder"
package = types.ModuleType("backup_test_package")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("backup_test_package", package)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        f"backup_test_package.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_load("const")
_load("scan_codes")
_load("migrations")
backup = _load("backup")


class BackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = {
            "medications": [
                {
                    "id": "m",
                    "name": "Medicine",
                    "manufacturer": "",
                    "barcode": "",
                    "form": "",
                    "strength": "",
                    "notes": "",
                    "unit": "pieces",
                    "stock": 4,
                    "stock_mode": "packages",
                    "low_stock_threshold": 1,
                    "scan_code": "med23456",
                }
            ],
            "packages": [
                {
                    "id": "p",
                    "medication_id": "m",
                    "nickname": "Apollo",
                    "lot_number": "LOT1",
                    "expires_on": "2027-01-01",
                    "external_code": "123",
                    "initial_quantity": 5,
                    "remaining_quantity": 4,
                    "created_at": "2026-01-01T12:00:00+00:00",
                    "scan_code": "med23457",
                }
            ],
            "regimens": [
                {
                    "id": "r",
                    "name": "Lunch",
                    "items": [{"medication_id": "m", "dose": 1}],
                    "schedule": {"type": "weekly", "days": {"0": ["13:00"]}},
                    "notify_services": ["notify.phone"],
                    "scripts": ["script.reminder"],
                    "repeat_minutes": 30,
                    "reminder_window_minutes": 180,
                    "auto_miss_after_minutes": 0,
                    "active": True,
                    "instructions": "With water",
                }
            ],
            "occurrences": [
                {
                    "id": "o",
                    "regimen_id": "r",
                    "regimen_name": "Lunch",
                    "unplanned": False,
                    "ad_hoc": False,
                    "reason": "",
                    "reference": "",
                    "scheduled_at": "2026-08-31T13:00:00+02:00",
                    "status": "taken",
                    "items": [
                        {
                            "medication_id": "m",
                            "planned_dose": 1,
                            "taken_dose": 1,
                            "taken_at": "2026-08-31T13:03:00+02:00",
                            "allocations": [
                                {
                                    "package_id": "p",
                                    "nickname": "Apollo",
                                    "lot_number": "LOT1",
                                    "expires_on": "2027-01-01",
                                    "amount": 1,
                                    "taken_at": "2026-08-31T13:03:00+02:00",
                                }
                            ],
                        }
                    ],
                    "taken_at": "2026-08-31T13:03:00+02:00",
                    "snoozed_until": None,
                    "last_reminded_at": "2026-08-31T13:00:00+02:00",
                    "reminders_sent": 1,
                    "completed_by": "user",
                    "scan_code": "med23458",
                }
            ],
            "last_generated_at": "2026-08-31T13:05:00+02:00",
        }

    def test_full_backup_round_trip_preserves_all_domain_data(self) -> None:
        original = json.loads(json.dumps(self.data))
        download = backup.build_backup_download(
            self.data, datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        )
        envelope = json.loads(download["content"])
        restored = backup.prepare_backup_import(envelope)
        self.assertEqual(original, restored)
        self.assertEqual(original, self.data)
        self.assertEqual("application/json;charset=utf-8", download["mime_type"])
        self.assertTrue(download["filename"].startswith("medreminder-backup_"))
        self.assertTrue(download["filename"].endswith(".json"))
        self.assertEqual("medreminder_backup", envelope["format"])

    def test_a_backup_from_before_the_domain_rename_still_restores(self) -> None:
        download = backup.build_backup_download(self.data, datetime.now(timezone.utc))
        envelope = json.loads(download["content"])
        envelope["format"] = "medication_reminder_backup"
        self.assertEqual(self.data, backup.prepare_backup_import(envelope))
        envelope["format"] = "some_other_backup"
        with self.assertRaises(ValueError):
            backup.prepare_backup_import(envelope)

    def test_old_manual_stock_is_migrated_during_import(self) -> None:
        envelope = {
            "format": backup.BACKUP_FORMAT,
            "backup_version": 1,
            "storage_version": 1,
            "storage_minor_version": 1,
            "data": {
                "medications": [
                    {
                        "id": "m",
                        "name": "Old medicine",
                        "unit": "pieces",
                        "stock": 7,
                        "low_stock_threshold": 1,
                    }
                ]
            },
        }
        restored = backup.prepare_backup_import(envelope)
        self.assertEqual("packages", restored["medications"][0]["stock_mode"])
        self.assertEqual(7, restored["medications"][0]["stock"])
        self.assertEqual("Legacy", restored["packages"][0]["nickname"])

    def test_invalid_or_future_backup_is_rejected(self) -> None:
        download = backup.build_backup_download(self.data, datetime.now(timezone.utc))
        envelope = json.loads(download["content"])
        envelope["data"]["packages"][0]["medication_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown medication"):
            backup.prepare_backup_import(envelope)

        envelope = json.loads(download["content"])
        envelope["storage_minor_version"] = 999
        with self.assertRaisesRegex(ValueError, "downgrade"):
            backup.prepare_backup_import(envelope)

        envelope = json.loads(download["content"])
        envelope["data"]["medications"][0]["id"] = 123
        with self.assertRaisesRegex(ValueError, "IDs"):
            backup.prepare_backup_import(envelope)

    def test_backup_with_a_non_notify_reminder_target_is_rejected(self) -> None:
        download = backup.build_backup_download(self.data, datetime.now(timezone.utc))
        envelope = json.loads(download["content"])
        envelope["data"]["regimens"][0]["notify_services"] = ["homeassistant.restart"]
        with self.assertRaisesRegex(ValueError, "notify services"):
            backup.prepare_backup_import(envelope)

        envelope = json.loads(download["content"])
        envelope["data"]["regimens"][0]["scripts"] = ["all"]
        with self.assertRaisesRegex(ValueError, "script entities"):
            backup.prepare_backup_import(envelope)


    def test_an_id_that_could_break_out_of_markup_is_rejected(self) -> None:
        download = backup.build_backup_download(self.data, datetime.now(timezone.utc))
        envelope = json.loads(download["content"])
        envelope["data"]["occurrences"][0]["id"] = '"><img src=x onerror=alert(1)>'
        with self.assertRaisesRegex(ValueError, "IDs"):
            backup.prepare_backup_import(envelope)

    def test_imported_fields_follow_the_rules_of_a_normal_save(self) -> None:
        download = backup.build_backup_download(self.data, datetime.now(timezone.utc))
        envelope = json.loads(download["content"])
        envelope["data"]["medications"][0]["name"] = {"not": "text"}
        with self.assertRaisesRegex(ValueError, "must be text"):
            backup.prepare_backup_import(envelope)

        envelope = json.loads(download["content"])
        envelope["data"]["regimens"][0]["reminder_window_minutes"] = "<b>"
        with self.assertRaises(ValueError):
            backup.prepare_backup_import(envelope)

        envelope = json.loads(download["content"])
        envelope["data"]["regimens"][0]["schedule"]["days"]["0"] = [
            f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 30)
        ]
        with self.assertRaisesRegex(ValueError, "at most 24"):
            backup.prepare_backup_import(envelope)

    def test_a_one_off_reminder_cannot_fire_every_tick(self) -> None:
        download = backup.build_backup_download(self.data, datetime.now(timezone.utc))
        envelope = json.loads(download["content"])
        occurrence = envelope["data"]["occurrences"][0]
        occurrence["reminder"] = {"repeat_minutes": 0, "reminder_window_minutes": 0}
        with self.assertRaisesRegex(ValueError, "repeat_minutes"):
            backup.prepare_backup_import(envelope)

    def test_an_open_one_off_intake_can_be_restored(self) -> None:
        # It belongs to no plan, so it has no schedule to reference.
        download = backup.build_backup_download(self.data, datetime.now(timezone.utc))
        envelope = json.loads(download["content"])
        occurrence = envelope["data"]["occurrences"][0]
        occurrence.update(
            {
                "regimen_id": None,
                "ad_hoc": True,
                "status": "pending",
                "taken_at": None,
                "reason": "Sport",
                "reminder": {"notify_services": ["notify.phone"]},
            }
        )
        for item in occurrence["items"]:
            item.update({"taken_dose": 0, "allocations": [], "taken_at": None})
        restored = backup.prepare_backup_import(envelope)
        self.assertEqual("Sport", restored["occurrences"][0]["reason"])
        self.assertEqual(
            ["notify.phone"], restored["occurrences"][0]["reminder"]["notify_services"]
        )


if __name__ == "__main__":
    unittest.main()
