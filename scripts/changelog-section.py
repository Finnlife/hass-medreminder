"""Extract the changelog section of one version.

The release workflow uses this for the release notes, so an update in HACS says
what changed. It exits with an error when the version has no section, which is
what stops a release from going out undescribed.

Usage: python scripts/changelog-section.py 0.7.6 [--output notes.md]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

CHANGELOG = pathlib.Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def section_for(text: str, version: str) -> str:
    """Return the body of the `## <version>` heading, without the heading."""
    pattern = re.compile(
        rf"^## {re.escape(version)}\s*$(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise SystemExit(
            f"CHANGELOG.md has no section for {version}.\n"
            f"Add a '## {version}' heading describing the change before releasing."
        )
    body = match.group(1).strip()
    if not body:
        raise SystemExit(f"The section for {version} in CHANGELOG.md is empty.")
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--output")
    arguments = parser.parse_args()

    body = section_for(CHANGELOG.read_text(encoding="utf-8"), arguments.version)
    if arguments.output:
        pathlib.Path(arguments.output).write_text(body + "\n", encoding="utf-8")
        print(f"wrote the notes for {arguments.version} to {arguments.output}")
    else:
        sys.stdout.write(body + "\n")


if __name__ == "__main__":
    main()
