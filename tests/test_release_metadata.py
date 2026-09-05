"""Checks that keep a release describable and consistent.

The release workflow enforces the same rules, but failing here means a missing
changelog entry shows up while running the tests rather than after the tag has
already been pushed.
"""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "medication_reminder"
CHANGELOG = ROOT / "CHANGELOG.md"


def _manifest_version() -> str:
    return json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))[
        "version"
    ]


def _changelog_versions() -> list[str]:
    return re.findall(
        r"^## (\d+\.\d+\.\d+)\s*$",
        CHANGELOG.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )


class ReleaseMetadataTests(unittest.TestCase):
    """Every released version has to say what changed."""

    def test_the_changelog_describes_the_current_version(self) -> None:
        version = _manifest_version()
        versions = _changelog_versions()
        self.assertIn(
            version,
            versions,
            f"CHANGELOG.md has no '## {version}' section. Describe the change "
            "before releasing it.",
        )

    def test_the_newest_changelog_section_is_the_current_version(self) -> None:
        self.assertEqual(_manifest_version(), _changelog_versions()[0])

    def test_the_current_section_is_not_empty(self) -> None:
        version = _manifest_version()
        match = re.search(
            rf"^## {re.escape(version)}\s*$(.*?)(?=^## |\Z)",
            CHANGELOG.read_text(encoding="utf-8"),
            flags=re.MULTILINE | re.DOTALL,
        )
        assert match is not None
        self.assertTrue(match.group(1).strip(), f"The {version} section is empty.")

    def test_every_changelog_version_appears_once(self) -> None:
        versions = _changelog_versions()
        self.assertEqual(len(versions), len(set(versions)))

    def test_the_frontend_cache_key_follows_the_manifest(self) -> None:
        # A stale cache key makes browsers keep serving the previous panel and
        # card after an update.
        source = (COMPONENT / "const.py").read_text(encoding="utf-8")
        match = re.search(r'FRONTEND_CACHE_KEY: Final = "([^"]+)"', source)
        assert match is not None, "FRONTEND_CACHE_KEY is missing from const.py"
        self.assertEqual(_manifest_version(), match.group(1))


if __name__ == "__main__":
    unittest.main()
