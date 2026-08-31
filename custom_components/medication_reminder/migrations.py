"""Versioned storage migrations for Medication Reminder."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .const import STORAGE_MINOR_VERSION, STORAGE_VERSION
from .scan_codes import ensure_scan_codes


def migrate_storage(
    old_major_version: int,
    old_minor_version: int,
    old_data: dict[str, Any],
) -> dict[str, Any]:
    """Return storage upgraded to the current schema without losing history."""
    if old_major_version != STORAGE_VERSION:
        raise NotImplementedError(
            f"Cannot migrate storage version {old_major_version}.{old_minor_version}"
        )
    if old_minor_version > STORAGE_MINOR_VERSION:
        raise NotImplementedError(
            f"Cannot downgrade storage version {old_major_version}.{old_minor_version}"
        )
    return ensure_current_data(old_data)


def ensure_current_data(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Expand a payload idempotently to the current storage shape."""
    data = deepcopy(raw or {})
    data.setdefault("medications", [])
    data.setdefault("packages", [])
    data.setdefault("regimens", [])
    data.setdefault("occurrences", [])
    data.setdefault("last_generated_at", None)
    for medication in data["medications"]:
        medication.setdefault("stock_mode", "manual")
    for occurrence in data["occurrences"]:
        occurrence.setdefault("unplanned", False)
        occurrence.setdefault("regimen_name", None)
        for item in occurrence.get("items", []):
            item.setdefault("allocations", [])
    ensure_scan_codes(data)
    return data
