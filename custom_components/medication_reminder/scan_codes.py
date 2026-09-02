"""Stable compact identifiers for printed scan codes."""

from __future__ import annotations

import re
from hashlib import sha256
from typing import Any

SCAN_CODE_PREFIX = "med"
SCAN_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
SCAN_CODE_PATTERN = re.compile(r"^med[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{5}$")
SCAN_CODE_COLLECTIONS = ("medications", "packages", "occurrences")


def generate_scan_code(seed: str, used: set[str]) -> str:
    """Return a deterministic unused code with five unambiguous characters."""
    nonce = 0
    while True:
        digest = sha256(f"{seed}:{nonce}".encode()).digest()
        suffix = "".join(SCAN_CODE_ALPHABET[value % 32] for value in digest[:5])
        candidate = f"{SCAN_CODE_PREFIX}{suffix}"
        if candidate not in used:
            return candidate
        nonce += 1


def ensure_scan_codes(data: dict[str, Any]) -> None:
    """Add unique codes in place while preserving valid existing assignments."""
    used: set[str] = set()
    for collection in SCAN_CODE_COLLECTIONS:
        for item in data.get(collection, []):
            current = str(item.get("scan_code", ""))
            if not SCAN_CODE_PATTERN.fullmatch(current) or current in used:
                current = generate_scan_code(f"{collection}:{item['id']}", used)
                item["scan_code"] = current
            used.add(current)


def used_scan_codes(data: dict[str, Any]) -> set[str]:
    """Return all currently assigned valid codes."""
    return {
        str(item.get("scan_code"))
        for collection in SCAN_CODE_COLLECTIONS
        for item in data.get(collection, [])
        if SCAN_CODE_PATTERN.fullmatch(str(item.get("scan_code", "")))
    }
