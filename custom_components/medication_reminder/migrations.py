"""Versioned storage migrations for Medication Reminder."""

from __future__ import annotations

from copy import deepcopy
import math
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
    _migrate_stock_to_packages(data)
    for occurrence in data["occurrences"]:
        occurrence.setdefault("unplanned", False)
        occurrence.setdefault("regimen_name", None)
        for item in occurrence.get("items", []):
            item.setdefault("allocations", [])
    ensure_scan_codes(data)
    return data


def _migrate_stock_to_packages(data: dict[str, Any]) -> None:
    """Make packages the sole stock source while preserving legacy stock."""
    packages = data["packages"]
    used_ids = {str(package.get("id", "")) for package in packages}
    for medication in data["medications"]:
        medication_id = str(medication["id"])
        if medication.get("stock_mode") != "packages":
            try:
                legacy_stock = float(medication.get("stock", 0))
            except (TypeError, ValueError):
                legacy_stock = 0
            if math.isfinite(legacy_stock) and legacy_stock > 0:
                package_id = f"legacy_{medication_id}"
                suffix = 2
                while package_id in used_ids:
                    package_id = f"legacy_{medication_id}_{suffix}"
                    suffix += 1
                used_ids.add(package_id)
                nicknames = {
                    str(package.get("nickname", "")).casefold()
                    for package in packages
                    if str(package.get("medication_id", "")) == medication_id
                }
                nickname = "Legacy"
                suffix = 2
                while nickname.casefold() in nicknames:
                    nickname = f"Legacy {suffix}"
                    suffix += 1
                packages.append(
                    {
                        "id": package_id,
                        "medication_id": medication_id,
                        "nickname": nickname,
                        "lot_number": "",
                        "expires_on": None,
                        "external_code": "",
                        "initial_quantity": round(legacy_stock, 3),
                        "remaining_quantity": round(legacy_stock, 3),
                        "created_at": None,
                    }
                )
        medication["stock_mode"] = "packages"
        medication["stock"] = round(
            sum(
                float(package.get("remaining_quantity", 0))
                for package in packages
                if str(package.get("medication_id", "")) == medication_id
            ),
            3,
        )
