"""Localization contract tests for frontend and Home Assistant metadata."""

import ast
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components/medication_reminder"
FRONTEND = INTEGRATION / "frontend"


def _frontend_catalog(name: str, source: str) -> dict[str, str]:
    match = re.search(
        rf"const {name} = Object\.freeze\((\{{.*?\}})\);",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Could not locate {name} frontend catalog")
    return json.loads(match.group(1))


def _leaf_paths(value, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return {prefix}
    return {
        path
        for key, child in value.items()
        for path in _leaf_paths(child, f"{prefix}.{key}" if prefix else key)
    }


class LocalizationTests(unittest.TestCase):
    """Ensure English and German remain complete and in sync."""

    def test_frontend_catalogs_have_identical_keys(self) -> None:
        source = (FRONTEND / "localize.js").read_text(encoding="utf-8")
        english = _frontend_catalog("EN", source)
        german = _frontend_catalog("DE", source)
        self.assertEqual(set(english), set(german))
        self.assertEqual(english["app.title"], "My medication schedule")

    def test_every_literal_frontend_translation_key_exists(self) -> None:
        catalog_source = (FRONTEND / "localize.js").read_text(encoding="utf-8")
        english = _frontend_catalog("EN", catalog_source)
        panel = (FRONTEND / "medication-reminder-panel.js").read_text(encoding="utf-8")
        used = set(re.findall(r'this\.t\("([a-z0-9_.]+)"', panel))
        self.assertTrue(used)
        self.assertEqual(set(), used - set(english))

    def test_home_assistant_translations_have_identical_shapes(self) -> None:
        translations = INTEGRATION / "translations"
        english = json.loads((translations / "en.json").read_text(encoding="utf-8"))
        german = json.loads((translations / "de.json").read_text(encoding="utf-8"))
        self.assertEqual(_leaf_paths(english), _leaf_paths(german))
        self.assertEqual(english["title"], "Medication Reminder")

    def test_runtime_notification_catalogs_have_identical_keys(self) -> None:
        source = (INTEGRATION / "localization.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_CATALOGS"
        )
        catalogs = ast.literal_eval(assignment.value)
        self.assertEqual(set(catalogs), {"en", "de"})
        self.assertEqual(set(catalogs["en"]), set(catalogs["de"]))
        self.assertEqual(catalogs["en"]["notification.title"], "Medication intake")

    def test_service_descriptions_are_translated_not_hardcoded(self) -> None:
        service_source = (INTEGRATION / "services.yaml").read_text(encoding="utf-8")
        self.assertNotRegex(
            service_source, re.compile(r"^\s+(name|description):", re.MULTILINE)
        )
        translations = json.loads(
            (INTEGRATION / "translations/en.json").read_text(encoding="utf-8")
        )
        for service in (
            "record_intake",
            "snooze",
            "add_package",
            "record_unplanned_intake",
            "postpone_interval",
            "delete_all_data",
        ):
            self.assertIn(f"{service}:", service_source)
            self.assertIn(service, translations["services"])

    def test_entity_translation_keys_are_declared(self) -> None:
        english = json.loads(
            (INTEGRATION / "translations/en.json").read_text(encoding="utf-8")
        )
        expected = {
            "sensor": set(english["entity"]["sensor"]),
            "binary_sensor": set(english["entity"]["binary_sensor"]),
        }
        for platform, keys in expected.items():
            source = (INTEGRATION / f"{platform}.py").read_text(encoding="utf-8")
            declared = set(
                re.findall(r'_attr_translation_key = "([a-z0-9_]+)"', source)
            )
            self.assertEqual(keys, declared)

    def test_custom_integration_has_explicit_english_translation(self) -> None:
        self.assertTrue((INTEGRATION / "translations/en.json").is_file())
        self.assertFalse((INTEGRATION / "strings.json").exists())


if __name__ == "__main__":
    unittest.main()
