"""Serialize retained intake history for user downloads."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from typing import Any

from .const import CLOSED_STATUSES

CSV_FIELDS = (
    "occurrence_id",
    "status",
    "intake_type",
    "reason",
    "regimen_id",
    "regimen_name",
    "scheduled_at",
    "taken_at",
    "deviation_minutes",
    "completed_by",
    "medication_id",
    "medication_name",
    "unit",
    "planned_dose",
    "taken_dose",
    "dose_taken_at",
    "package_allocations",
)


def build_history_export(
    data: dict[str, Any],
    start_date: str,
    end_date: str,
    export_format: str,
    *,
    exported_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a JSON or CSV download for completed history in an inclusive range."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("Start date must not be after end date")
    if export_format not in ("json", "csv"):
        raise ValueError("Unsupported export format")

    medications = {str(item["id"]): item for item in data.get("medications", [])}
    regimens = {str(item["id"]): item for item in data.get("regimens", [])}
    occurrences = [
        occurrence
        for occurrence in data.get("occurrences", [])
        if occurrence.get("status") in CLOSED_STATUSES
        and _in_date_range(occurrence, start, end)
    ]
    occurrences.sort(key=lambda item: str(item.get("scheduled_at", "")))
    records = [
        _export_occurrence(occurrence, medications, regimens)
        for occurrence in occurrences
    ]
    generated = exported_at or datetime.now(timezone.utc)
    filename = f"medication-intakes_{start_date}_to_{end_date}.{export_format}"
    if export_format == "json":
        payload = {
            "schema_version": 1,
            "exported_at": generated.isoformat(),
            "range": {
                "from": start_date,
                "to": end_date,
                "inclusive": True,
                "date_basis": "taken_at_or_scheduled_at",
            },
            "occurrence_count": len(records),
            "occurrences": records,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        mime_type = "application/json;charset=utf-8"
    else:
        content = _to_csv(records)
        mime_type = "text/csv;charset=utf-8"
    return {
        "filename": filename,
        "mime_type": mime_type,
        "content": content,
        "count": len(records),
    }


def _in_date_range(occurrence: dict[str, Any], start: date, end: date) -> bool:
    raw = occurrence.get("taken_at") or occurrence.get("scheduled_at")
    if not raw:
        return False
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return start <= value <= end


def _export_occurrence(
    occurrence: dict[str, Any],
    medications: dict[str, dict[str, Any]],
    regimens: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    regimen_id = occurrence.get("regimen_id")
    regimen = regimens.get(str(regimen_id)) if regimen_id else None
    regimen_name = occurrence.get("regimen_name") or (
        regimen.get("name") if regimen else None
    )
    scheduled_at = occurrence.get("scheduled_at")
    taken_at = occurrence.get("taken_at")
    deviation = None
    if not occurrence.get("unplanned") and occurrence.get("status") == "taken":
        deviation = _difference_minutes(scheduled_at, taken_at)
    return {
        "occurrence_id": occurrence.get("id"),
        "status": occurrence.get("status"),
        "intake_type": _intake_type(occurrence),
        "reason": occurrence.get("reason", ""),
        "regimen_id": regimen_id,
        "regimen_name": regimen_name,
        "scheduled_at": scheduled_at,
        "taken_at": taken_at,
        "deviation_minutes": deviation,
        "completed_by": occurrence.get("completed_by"),
        "items": [
            _export_item(item, medications) for item in occurrence.get("items", [])
        ],
    }


def _intake_type(occurrence: dict[str, Any]) -> str:
    """Classify an occurrence for the export."""
    if occurrence.get("unplanned"):
        return "unplanned"
    return "ad_hoc" if occurrence.get("ad_hoc") else "scheduled"


def _difference_minutes(start: Any, end: Any) -> int | None:
    if not start or not end:
        return None
    try:
        start_value = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_value = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return round((end_value - start_value).total_seconds() / 60)
    except (TypeError, ValueError):
        return None


def _export_item(
    item: dict[str, Any], medications: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    medication_id = str(item.get("medication_id", ""))
    medication = medications.get(medication_id)
    return {
        "medication_id": medication_id,
        "medication_name": medication.get("name") if medication else None,
        "unit": medication.get("unit") if medication else None,
        "planned_dose": item.get("planned_dose"),
        "taken_dose": item.get("taken_dose"),
        "taken_at": item.get("taken_at"),
        "allocations": [
            {
                "package_id": allocation.get("package_id"),
                "nickname": allocation.get("nickname"),
                "lot_number": allocation.get("lot_number"),
                "expires_on": allocation.get("expires_on"),
                "amount": allocation.get("amount"),
                "taken_at": allocation.get("taken_at"),
            }
            for allocation in item.get("allocations", [])
        ],
    }


def _to_csv(records: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    output.write("\ufeff")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    for record in records:
        items = record["items"] or [{}]
        for item in items:
            row = {
                **{key: record.get(key) for key in CSV_FIELDS},
                "medication_id": item.get("medication_id"),
                "medication_name": item.get("medication_name"),
                "unit": item.get("unit"),
                "planned_dose": item.get("planned_dose"),
                "taken_dose": item.get("taken_dose"),
                "dose_taken_at": item.get("taken_at"),
                "package_allocations": json.dumps(
                    item.get("allocations", []), ensure_ascii=False
                ),
            }
            writer.writerow({key: _csv_safe(value) for key, value in row.items()})
    return output.getvalue()


def _csv_safe(value: Any) -> Any:
    """Prevent spreadsheet applications from evaluating user text as formulas."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value
