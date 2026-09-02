"""Runtime manager for Medication Reminder."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .backup import build_backup_download, prepare_backup_import
from .const import (
    ADHERENCE_WINDOW_DAYS,
    CATCHUP_DAYS,
    CLOSED_STATUSES,
    DOMAIN,
    EVENT_DUE,
    EVENT_LOW_STOCK,
    EVENT_MISSED,
    EVENT_POSTPONED,
    EVENT_SKIPPED,
    EVENT_TAKEN,
    MAX_HISTORY,
    OPEN_STATUSES,
    PACKAGE_NICKNAMES,
    TICK_SECONDS,
)
from .history_export import build_history_export
from .localization import translate
from .migrations import ensure_current_data
from .models import (
    empty_data,
    new_id,
    normalize_medication,
    normalize_package,
    normalize_regimen,
    occurrence_for,
    public_data,
)
from .scan_codes import SCAN_CODE_COLLECTIONS, generate_scan_code, used_scan_codes
from .schedule import next_occurrence, occurrences_between, occurrences_per_day
from .storage import MedicationStore

_LOGGER = logging.getLogger(__name__)


class MedicationManager:
    """Own persistent state, reminders and domain invariants."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = MedicationStore(hass)
        self.data: dict[str, Any] = empty_data()
        self._lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._unsub_timer: Callable[[], None] | None = None
        self._unsub_actions: Callable[[], None] | None = None

    async def async_initialize(self) -> None:
        """Load storage and start listeners."""
        loaded = await self._store.async_load()
        self.data = ensure_current_data(loaded) if loaded else empty_data()
        self._recalculate_all_package_stock()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_tick, timedelta(seconds=TICK_SECONDS)
        )
        self._unsub_actions = self.hass.bus.async_listen(
            "mobile_app_notification_action", self._handle_notification_action
        )
        await self._async_tick(dt_util.now())

    async def async_close(self) -> None:
        """Stop listeners and flush state."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_actions:
            self._unsub_actions()
            self._unsub_actions = None
        await self._store.async_save(self.data)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to state changes."""
        self._listeners.add(listener)

        @callback
        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    # ------------------------------------------------------------------
    # Read models
    # ------------------------------------------------------------------

    def open_occurrences(self) -> list[dict[str, Any]]:
        """Return unresolved tickets ordered by their scheduled time."""
        return sorted(
            (
                occurrence
                for occurrence in self.data["occurrences"]
                if occurrence["status"] in OPEN_STATUSES
            ),
            key=lambda occurrence: occurrence["scheduled_at"],
        )

    def due_occurrences(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """Return open tickets that are due right now and not snoozed."""
        moment = now or dt_util.now()
        return [
            occurrence
            for occurrence in self.open_occurrences()
            if _is_due(occurrence, moment)
        ]

    def occurrence_label(self, occurrence: dict[str, Any]) -> str:
        """Return a human readable one-line summary of a ticket."""
        parts = []
        for item in occurrence["items"]:
            remaining = round(item["planned_dose"] - item["taken_dose"], 3)
            if remaining <= 0:
                continue
            medication = self._find("medications", item["medication_id"])
            name = medication["name"] if medication else "?"
            unit = medication["unit"] if medication else ""
            parts.append(f"{remaining:g} {unit} {name}".strip())
        title = occurrence.get("regimen_name") or translate(
            self.hass, "notification.unplanned"
        )
        return f"{title}: {', '.join(parts)}" if parts else title

    def upcoming(self, limit: int = 25) -> list[dict[str, Any]]:
        """Return the next scheduled intake per active regimen."""
        now = dt_util.now()
        result: list[dict[str, Any]] = []
        for regimen in self.data["regimens"]:
            if not regimen.get("active", True):
                continue
            value = next_occurrence(regimen["schedule"], now)
            if value is None:
                continue
            result.append(
                {
                    "regimen_id": regimen["id"],
                    "regimen_name": regimen["name"],
                    "scheduled_at": value.isoformat(),
                    "items": [
                        {
                            "medication_id": item["medication_id"],
                            "medication_name": self._medication_name(
                                item["medication_id"]
                            ),
                            "dose": item["dose"],
                        }
                        for item in regimen["items"]
                    ],
                }
            )
        return sorted(result, key=lambda item: item["scheduled_at"])[:limit]

    def planned_events(
        self, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        """Return planned intakes in a window, for the calendar entity."""
        events: list[dict[str, Any]] = []
        for regimen in self.data["regimens"]:
            if not regimen.get("active", True):
                continue
            for scheduled in occurrences_between(regimen["schedule"], start, end):
                events.append(
                    {
                        "regimen_id": regimen["id"],
                        "summary": regimen["name"],
                        "start": scheduled,
                        "description": ", ".join(
                            f"{item['dose']:g} × "
                            f"{self._medication_name(item['medication_id'])}"
                            for item in regimen["items"]
                        ),
                        "instructions": regimen.get("instructions", ""),
                    }
                )
        return sorted(events, key=lambda event: event["start"])

    def daily_consumption(self, medication_id: str) -> float:
        """Return the planned amount of one medication consumed per day."""
        total = 0.0
        for regimen in self.data["regimens"]:
            if not regimen.get("active", True):
                continue
            per_day = occurrences_per_day(regimen["schedule"])
            for item in regimen["items"]:
                if item["medication_id"] == medication_id:
                    total += float(item["dose"]) * per_day
        return round(total, 4)

    def days_of_supply(self, medication_id: str) -> float | None:
        """Return how many days the current stock lasts, or None when unplanned."""
        per_day = self.daily_consumption(medication_id)
        if per_day <= 0:
            return None
        medication = self._find("medications", medication_id)
        if not medication:
            return None
        return round(float(medication["stock"]) / per_day, 1)

    def adherence(self, days: int = ADHERENCE_WINDOW_DAYS) -> dict[str, Any]:
        """Return adherence statistics over the retained scheduled history."""
        since = dt_util.now() - timedelta(days=days)
        taken = partial = skipped = missed = 0
        for occurrence in self.data["occurrences"]:
            if occurrence.get("unplanned"):
                continue
            if occurrence["status"] not in CLOSED_STATUSES:
                continue
            scheduled = _parse_optional_datetime(occurrence.get("scheduled_at"))
            if scheduled is None or dt_util.as_local(scheduled) < since:
                continue
            if occurrence["status"] == "taken":
                if all(
                    item["taken_dose"] >= item["planned_dose"]
                    for item in occurrence["items"]
                ):
                    taken += 1
                else:
                    partial += 1
            elif occurrence["status"] == "skipped":
                skipped += 1
            else:
                missed += 1
        total = taken + partial + skipped + missed
        rate = round(100 * (taken + 0.5 * partial) / total, 1) if total else None
        return {
            "window_days": days,
            "total": total,
            "taken": taken,
            "partial": partial,
            "skipped": skipped,
            "missed": missed,
            "rate": rate,
        }

    def find_by_scan_code(self, code: str) -> tuple[str, dict[str, Any]] | None:
        """Resolve a printed scan code to its collection and record."""
        for collection in SCAN_CODE_COLLECTIONS:
            for item in self.data.get(collection, []):
                if str(item.get("scan_code", "")) == code:
                    return collection, item
        return None

    def snapshot(self) -> dict[str, Any]:
        """Return state plus calculated dashboard data."""
        result = public_data(self.data)
        for occurrence in result["occurrences"]:
            if occurrence["status"] not in OPEN_STATUSES:
                continue
            for item in occurrence["items"]:
                remaining = round(item["planned_dose"] - item["taken_dose"], 3)
                item["package_plan"] = self.package_plan(
                    item["medication_id"], remaining, strict=False
                )
        for medication in result["medications"]:
            medication["daily_consumption"] = self.daily_consumption(medication["id"])
            medication["days_of_supply"] = self.days_of_supply(medication["id"])
        result["server_time"] = dt_util.now().isoformat()
        result["upcoming"] = self.upcoming()
        result["adherence"] = self.adherence()
        result["notify_services"] = sorted(
            f"{domain}.{service}"
            for domain, services in self.hass.services.async_services().items()
            if domain == "notify"
            for service in services
        )
        result["scripts"] = sorted(
            state.entity_id for state in self.hass.states.async_all("script")
        )
        return result

    # ------------------------------------------------------------------
    # Import and export
    # ------------------------------------------------------------------

    async def async_export_history(
        self, start_date: str, end_date: str, export_format: str
    ) -> dict[str, Any]:
        """Export retained completed intake history in an inclusive date range."""
        async with self._lock:
            return build_history_export(
                self.data,
                start_date,
                end_date,
                export_format,
                exported_at=dt_util.now(),
            )

    async def async_export_backup(self) -> dict[str, Any]:
        """Export all persistent Medication Reminder data."""
        async with self._lock:
            return build_backup_download(self.data, dt_util.now())

    async def async_import_backup(self, payload: dict[str, Any]) -> dict[str, int]:
        """Atomically replace persistent data with a validated backup."""
        imported = prepare_backup_import(payload)
        async with self._lock:
            previous = self.data
            self.data = imported
            try:
                self._recalculate_all_package_stock()
                await self._changed()
            except Exception:
                self.data = previous
                raise
            return {
                "medications": len(self.data["medications"]),
                "packages": len(self.data["packages"]),
                "regimens": len(self.data["regimens"]),
                "occurrences": len(self.data["occurrences"]),
            }

    # ------------------------------------------------------------------
    # Master data
    # ------------------------------------------------------------------

    async def async_save_medication(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Create or update a medication."""
        async with self._lock:
            medication_id = str(raw.get("id", "")) or None
            existing = (
                self._find("medications", medication_id) if medication_id else None
            )
            if medication_id and existing is None:
                raise ValueError("Unknown medication")
            medication = normalize_medication(raw, medication_id)
            medication["scan_code"] = (
                existing.get("scan_code")
                if existing and existing.get("scan_code")
                else self._new_scan_code(f"medications:{medication['id']}")
            )
            medication["stock"] = self._package_stock(medication["id"])
            if existing:
                self.data["medications"][self.data["medications"].index(existing)] = (
                    medication
                )
            else:
                self.data["medications"].append(medication)
            await self._changed()
            return public_data(medication)

    async def async_delete_medication(self, medication_id: str) -> None:
        """Delete an unused medication."""
        async with self._lock:
            medication = self._require("medications", medication_id)
            if any(
                item["medication_id"] == medication_id
                for regimen in self.data["regimens"]
                for item in regimen["items"]
            ):
                raise ValueError("Medication is still used by an intake")
            if any(
                item["medication_id"] == medication_id
                for occurrence in self.data["occurrences"]
                if occurrence["status"] in OPEN_STATUSES
                for item in occurrence["items"]
            ):
                raise ValueError("Medication is still used by an open intake")
            self.data["medications"].remove(medication)
            self.data["packages"] = [
                package
                for package in self.data["packages"]
                if package["medication_id"] != medication_id
            ]
            await self._changed()

    async def async_save_package(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Create or update a physical package and recalculate stock."""
        async with self._lock:
            medication_id = str(raw.get("medication_id", ""))
            medication = self._require("medications", medication_id)
            package_id = str(raw.get("id", "")) or None
            existing = self._find("packages", package_id) if package_id else None
            if package_id and existing is None:
                raise ValueError("Unknown package")
            if existing and existing["medication_id"] != medication_id:
                raise ValueError("A package cannot be moved to another medication")
            normalized_raw = dict(raw)
            if not str(normalized_raw.get("nickname", "")).strip():
                normalized_raw["nickname"] = (
                    existing["nickname"]
                    if existing
                    else self._next_package_nickname(medication_id)
                )
            package = normalize_package(normalized_raw, medication_id, existing)
            package["scan_code"] = (
                existing.get("scan_code")
                if existing and existing.get("scan_code")
                else self._new_scan_code(f"packages:{package['id']}")
            )
            if any(
                other["medication_id"] == medication_id
                and other["id"] != package["id"]
                and other["nickname"].casefold() == package["nickname"].casefold()
                for other in self.data["packages"]
            ):
                raise ValueError("Package nickname must be unique per medication")
            package["created_at"] = (
                existing.get("created_at") if existing else dt_util.now().isoformat()
            )
            if existing:
                self.data["packages"][self.data["packages"].index(existing)] = package
            else:
                self.data["packages"].append(package)
            medication["stock_mode"] = "packages"
            self._recalculate_package_stock(medication_id)
            await self._changed()
            return public_data(package)

    async def async_delete_package(self, package_id: str) -> None:
        """Delete a package while keeping allocation snapshots in history."""
        async with self._lock:
            package = self._require("packages", package_id)
            medication_id = package["medication_id"]
            self.data["packages"].remove(package)
            self._recalculate_package_stock(medication_id)
            await self._changed()

    async def async_delete_all_data(self, confirmation: str) -> None:
        """Delete all Medication Reminder domain data but keep the integration."""
        if confirmation != "DELETE":
            raise ValueError("Invalid delete confirmation")
        async with self._lock:
            self.data = empty_data()
            await self._changed()

    async def async_save_regimen(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Create or update an intake regimen."""
        async with self._lock:
            regimen_id = str(raw.get("id", "")) or None
            existing = self._find("regimens", regimen_id) if regimen_id else None
            if regimen_id and existing is None:
                raise ValueError("Unknown regimen")
            regimen = normalize_regimen(
                raw,
                {item["id"] for item in self.data["medications"]},
                regimen_id,
            )
            regimen["created_at"] = (
                existing.get("created_at") if existing else dt_util.now().isoformat()
            )
            if existing:
                self.data["regimens"][self.data["regimens"].index(existing)] = regimen
                self._resync_open_occurrences(regimen)
            else:
                self.data["regimens"].append(regimen)
            await self._changed()
            return public_data(regimen)

    async def async_delete_regimen(self, regimen_id: str) -> None:
        """Delete a regimen and its unresolved tickets."""
        async with self._lock:
            regimen = self._require("regimens", regimen_id)
            self.data["regimens"].remove(regimen)
            self.data["occurrences"] = [
                occurrence
                for occurrence in self.data["occurrences"]
                if occurrence["regimen_id"] != regimen_id
                or occurrence["status"] in CLOSED_STATUSES
            ]
            await self._changed()

    def _resync_open_occurrences(self, regimen: dict[str, Any]) -> None:
        """Drop untouched future tickets that no longer match an edited plan."""
        now = dt_util.now()
        kept: list[dict[str, Any]] = []
        for occurrence in self.data["occurrences"]:
            if (
                occurrence["regimen_id"] != regimen["id"]
                or occurrence["status"] != "pending"
                or any(item["taken_dose"] for item in occurrence["items"])
            ):
                kept.append(occurrence)
                continue
            scheduled = _parse_optional_datetime(occurrence.get("scheduled_at"))
            if scheduled is None or dt_util.as_local(scheduled) <= now:
                occurrence["regimen_name"] = regimen["name"]
                kept.append(occurrence)
        self.data["occurrences"] = kept

    # ------------------------------------------------------------------
    # Intake
    # ------------------------------------------------------------------

    async def async_record_intake(
        self,
        occurrence_id: str,
        doses: dict[str, float] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Record all or selected remaining doses exactly once."""
        async with self._lock:
            occurrence = self._require("occurrences", occurrence_id)
            if occurrence["status"] in CLOSED_STATUSES:
                return public_data(occurrence)
            complete = self._record_intake_locked(occurrence, doses, user_id)
            await self._changed()
            self._fire_taken_event(occurrence, complete)
            return public_data(occurrence)

    async def async_record_unplanned_intake(
        self,
        items: list[dict[str, Any]],
        user_id: str | None = None,
        taken_at: datetime | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Record an unscheduled intake with the same stock guarantees."""
        async with self._lock:
            seen: set[str] = set()
            occurrence_items: list[dict[str, Any]] = []
            for raw in items:
                medication_id = str(raw.get("medication_id", ""))
                self._require("medications", medication_id)
                if medication_id in seen:
                    raise ValueError("Medication occurs more than once")
                seen.add(medication_id)
                dose = float(raw.get("dose", 0))
                if not math.isfinite(dose) or dose <= 0:
                    raise ValueError("dose must be greater than zero")
                occurrence_items.append(
                    {
                        "medication_id": medication_id,
                        "planned_dose": round(dose, 3),
                        "taken_dose": 0,
                        "allocations": [],
                    }
                )
            if not occurrence_items:
                raise ValueError("At least one medication is required")
            actual = dt_util.as_local(taken_at or dt_util.now())
            if actual > dt_util.now() + timedelta(minutes=1):
                raise ValueError("Intake time must not be in the future")
            occurrence = {
                "id": new_id(),
                "regimen_id": None,
                "regimen_name": None,
                "unplanned": True,
                "note": str(note or "").strip()[:500],
                "scheduled_at": actual.isoformat(),
                "status": "pending",
                "items": occurrence_items,
                "taken_at": None,
                "snoozed_until": None,
                "last_reminded_at": None,
                "reminders_sent": 0,
                "completed_by": None,
            }
            occurrence["scan_code"] = self._new_scan_code(
                f"occurrences:{occurrence['id']}"
            )
            complete = self._record_intake_locked(
                occurrence, None, user_id, recorded_at=actual
            )
            self.data["occurrences"].append(occurrence)
            await self._changed()
            self._fire_taken_event(occurrence, complete)
            return public_data(occurrence)

    async def async_snooze(self, occurrence_id: str, until: datetime) -> dict[str, Any]:
        """Snooze an unresolved occurrence until a future point."""
        if until <= dt_util.now():
            raise ValueError("Snooze time must be in the future")
        async with self._lock:
            occurrence = self._require("occurrences", occurrence_id)
            if occurrence["status"] not in OPEN_STATUSES:
                raise ValueError("Only open intakes can be snoozed")
            occurrence["snoozed_until"] = dt_util.as_local(until).isoformat()
            await self._changed()
            return public_data(occurrence)

    async def async_postpone_interval(self, occurrence_id: str) -> dict[str, Any]:
        """Move an interval occurrence to tomorrow and shift its entire cycle."""
        async with self._lock:
            occurrence = self._require("occurrences", occurrence_id)
            if occurrence["status"] != "pending":
                raise ValueError("Only untouched open intakes can shift their cycle")
            regimen = self._find("regimens", occurrence.get("regimen_id"))
            if not regimen or regimen["schedule"].get("type") != "interval":
                raise ValueError("Only interval schedules can shift their cycle")
            scheduled = _parse_optional_datetime(occurrence["scheduled_at"])
            if scheduled is None:
                raise ValueError("Invalid scheduled time")
            now = dt_util.now()
            local_scheduled = dt_util.as_local(scheduled)
            if local_scheduled.date() > now.date():
                raise ValueError("Only due intakes can shift to tomorrow")
            target_date = now.date() + timedelta(days=1)
            shift_days = (target_date - local_scheduled.date()).days
            start_date = date.fromisoformat(regimen["schedule"]["start_date"])
            regimen["schedule"]["start_date"] = (
                start_date + timedelta(days=shift_days)
            ).isoformat()
            occurrence["scheduled_at"] = (
                local_scheduled + timedelta(days=shift_days)
            ).isoformat()
            occurrence["snoozed_until"] = None
            occurrence["last_reminded_at"] = None
            occurrence["reminders_sent"] = 0
            await self._changed()
            self.hass.bus.async_fire(
                EVENT_POSTPONED,
                {
                    "occurrence_id": occurrence_id,
                    "regimen_id": regimen["id"],
                    "scheduled_at": occurrence["scheduled_at"],
                },
            )
            return public_data(occurrence)

    async def async_skip(
        self, occurrence_id: str, user_id: str | None = None
    ) -> dict[str, Any]:
        """Mark an occurrence skipped without changing stock."""
        async with self._lock:
            occurrence = self._require("occurrences", occurrence_id)
            if occurrence["status"] in CLOSED_STATUSES:
                return public_data(occurrence)
            occurrence["status"] = "skipped"
            occurrence["taken_at"] = dt_util.now().isoformat()
            occurrence["completed_by"] = user_id
            occurrence["snoozed_until"] = None
            await self._changed()
            self.hass.bus.async_fire(
                EVENT_SKIPPED,
                {
                    "occurrence_id": occurrence_id,
                    "regimen_id": occurrence["regimen_id"],
                },
            )
            return public_data(occurrence)

    def _record_intake_locked(
        self,
        occurrence: dict[str, Any],
        doses: dict[str, float] | None,
        user_id: str | None,
        recorded_at: datetime | None = None,
    ) -> bool:
        """Validate and apply one intake while the manager lock is held."""
        changes: list[dict[str, Any]] = []
        for item in occurrence["items"]:
            remaining = round(item["planned_dose"] - item["taken_dose"], 3)
            requested = (
                remaining
                if doses is None
                else _as_float(doses.get(item["medication_id"], 0))
            )
            if not math.isfinite(requested) or requested < 0 or requested > remaining:
                raise ValueError("Taken dose exceeds the remaining planned dose")
            if requested == 0:
                continue
            medication = self._require("medications", item["medication_id"])
            before = float(medication["stock"])
            if requested > before:
                raise ValueError(f"Not enough stock for {medication['name']}")
            changes.append(
                {
                    "item": item,
                    "medication": medication,
                    "requested": requested,
                    "before": before,
                    "package_parts": self._package_deductions(
                        medication["id"], requested, strict=True
                    ),
                }
            )
        if not changes:
            raise ValueError("No dose was selected")

        taken_at = dt_util.as_local(recorded_at or dt_util.now()).isoformat()
        for change in changes:
            item = change["item"]
            medication = change["medication"]
            requested = change["requested"]
            for package, amount in change["package_parts"]:
                package["remaining_quantity"] = round(
                    package["remaining_quantity"] - amount, 3
                )
                item.setdefault("allocations", []).append(
                    self._package_snapshot(package, amount, taken_at)
                )
            self._recalculate_package_stock(medication["id"])
            item["taken_dose"] = round(item["taken_dose"] + requested, 3)
            item["taken_at"] = taken_at
            if (
                change["before"]
                > medication["low_stock_threshold"]
                >= medication["stock"]
            ):
                self.hass.bus.async_fire(
                    EVENT_LOW_STOCK,
                    {
                        "medication_id": medication["id"],
                        "medication_name": medication["name"],
                        "stock": medication["stock"],
                        "unit": medication["unit"],
                        "low_stock_threshold": medication["low_stock_threshold"],
                    },
                )
        complete = all(
            item["taken_dose"] >= item["planned_dose"] for item in occurrence["items"]
        )
        occurrence["status"] = "taken" if complete else "partial"
        occurrence["taken_at"] = taken_at if complete else None
        occurrence["completed_by"] = user_id if complete else None
        occurrence["snoozed_until"] = None
        return complete

    def _fire_taken_event(self, occurrence: dict[str, Any], complete: bool) -> None:
        """Emit the shared taken event for scheduled and unplanned intake."""
        self.hass.bus.async_fire(
            EVENT_TAKEN,
            {
                "occurrence_id": occurrence["id"],
                "regimen_id": occurrence.get("regimen_id"),
                "regimen_name": occurrence.get("regimen_name"),
                "unplanned": occurrence.get("unplanned", False),
                "complete": complete,
                "items": public_data(occurrence["items"]),
            },
        )

    # ------------------------------------------------------------------
    # Stock and packages
    # ------------------------------------------------------------------

    def package_plan(
        self, medication_id: str, amount: float, *, strict: bool = True
    ) -> list[dict[str, Any]]:
        """Return the FEFO packages recommended for a dose without mutating stock."""
        if amount <= 0 or not self._find("medications", medication_id):
            return []
        return [
            self._package_snapshot(package, part, None)
            for package, part in self._package_deductions(
                medication_id, amount, strict=strict
            )
        ]

    def _package_deductions(
        self, medication_id: str, amount: float, *, strict: bool
    ) -> list[tuple[dict[str, Any], float]]:
        packages = sorted(
            (
                package
                for package in self._packages_for(medication_id)
                if package["remaining_quantity"] > 0
            ),
            key=lambda package: (
                package.get("expires_on") or "9999-12-31",
                package.get("created_at") or "",
                package["id"],
            ),
        )
        remaining = round(float(amount), 3)
        result: list[tuple[dict[str, Any], float]] = []
        for package in packages:
            if remaining <= 0:
                break
            part = min(remaining, float(package["remaining_quantity"]))
            if part > 0:
                result.append((package, round(part, 3)))
                remaining = round(remaining - part, 3)
        if strict and remaining > 0:
            medication = self._require("medications", medication_id)
            raise ValueError(f"Not enough stock for {medication['name']}")
        return result

    @staticmethod
    def _package_snapshot(
        package: dict[str, Any], amount: float, taken_at: str | None
    ) -> dict[str, Any]:
        return {
            "package_id": package["id"],
            "nickname": package["nickname"],
            "lot_number": package.get("lot_number", ""),
            "expires_on": package.get("expires_on"),
            "amount": round(amount, 3),
            "taken_at": taken_at,
        }

    def _packages_for(self, medication_id: str) -> list[dict[str, Any]]:
        return [
            package
            for package in self.data.get("packages", [])
            if package["medication_id"] == medication_id
        ]

    def _package_stock(self, medication_id: str) -> float:
        return round(
            sum(
                float(package["remaining_quantity"])
                for package in self._packages_for(medication_id)
            ),
            3,
        )

    def _recalculate_package_stock(self, medication_id: str) -> None:
        medication = self._find("medications", medication_id)
        if medication:
            medication["stock_mode"] = "packages"
            medication["stock"] = self._package_stock(medication_id)

    def _recalculate_all_package_stock(self) -> None:
        for medication in self.data["medications"]:
            self._recalculate_package_stock(medication["id"])

    def _next_package_nickname(self, medication_id: str) -> str:
        used = {
            package["nickname"].casefold()
            for package in self._packages_for(medication_id)
        }
        for nickname in PACKAGE_NICKNAMES:
            if nickname.casefold() not in used:
                return nickname
        index = len(used)
        while True:
            base = PACKAGE_NICKNAMES[index % len(PACKAGE_NICKNAMES)]
            candidate = f"{base} {index + 1}"
            if candidate.casefold() not in used:
                return candidate
            index += 1

    # ------------------------------------------------------------------
    # Scheduling loop
    # ------------------------------------------------------------------

    async def _async_tick(self, now: datetime) -> None:
        """Create due tickets, send reminders and expire abandoned intakes."""
        async with self._lock:
            now = dt_util.as_local(now)
            changed = self._generate_tickets(now)
            changed = await self._process_open_occurrences(now) or changed
            self.data["last_generated_at"] = now.isoformat()
            if changed:
                await self._changed()
            else:
                # Time-dependent entities must refresh even without data changes.
                self._notify_listeners()

    def _generate_tickets(self, now: datetime) -> bool:
        previous = _parse_optional_datetime(self.data.get("last_generated_at"))
        previous = (
            dt_util.as_local(previous) if previous else now - timedelta(minutes=1)
        )
        previous = max(previous, now - timedelta(days=CATCHUP_DAYS))
        known = {
            (occurrence["regimen_id"], occurrence["scheduled_at"])
            for occurrence in self.data["occurrences"]
        }
        created = False
        for regimen in self.data["regimens"]:
            if not regimen.get("active", True):
                continue
            created_at = _parse_optional_datetime(regimen.get("created_at"))
            range_start = previous - timedelta(minutes=1)
            if created_at is not None:
                range_start = max(range_start, dt_util.as_local(created_at))
            for scheduled in occurrences_between(regimen["schedule"], range_start, now):
                key = (regimen["id"], scheduled.isoformat())
                if key in known:
                    continue
                ticket = occurrence_for(regimen, scheduled)
                ticket["scan_code"] = self._new_scan_code(
                    f"occurrences:{ticket['id']}"
                )
                self.data["occurrences"].append(ticket)
                known.add(key)
                created = True
        return created

    async def _process_open_occurrences(self, now: datetime) -> bool:
        changed = False
        for occurrence in self.data["occurrences"]:
            if occurrence["status"] not in OPEN_STATUSES:
                continue
            due = _parse_optional_datetime(occurrence.get("scheduled_at"))
            if due is None:
                continue
            due = dt_util.as_local(due)
            if due > now:
                continue
            regimen = self._find("regimens", occurrence.get("regimen_id"))
            if regimen is None:
                continue
            auto_miss = int(regimen.get("auto_miss_after_minutes", 0) or 0)
            if auto_miss and now >= due + timedelta(minutes=auto_miss):
                occurrence["status"] = "missed"
                occurrence["taken_at"] = None
                occurrence["snoozed_until"] = None
                changed = True
                self.hass.bus.async_fire(
                    EVENT_MISSED,
                    {
                        "occurrence_id": occurrence["id"],
                        "regimen_id": regimen["id"],
                        "regimen_name": regimen["name"],
                        "scheduled_at": occurrence["scheduled_at"],
                    },
                )
                continue
            if not regimen.get("active", True):
                continue
            snoozed = _parse_optional_datetime(occurrence.get("snoozed_until"))
            snoozed = dt_util.as_local(snoozed) if snoozed else None
            if snoozed and snoozed > now:
                continue
            window = int(regimen.get("reminder_window_minutes", 0) or 0)
            if snoozed is None and window and now > due + timedelta(minutes=window):
                continue
            last = _parse_optional_datetime(occurrence.get("last_reminded_at"))
            repeat = timedelta(minutes=int(regimen["repeat_minutes"]))
            # An expired snooze is an explicit user request and always fires.
            if snoozed is None and last and dt_util.as_local(last) + repeat > now:
                continue
            await self._async_notify(regimen, occurrence)
            occurrence["last_reminded_at"] = now.isoformat()
            occurrence["snoozed_until"] = None
            occurrence["reminders_sent"] = int(occurrence.get("reminders_sent", 0)) + 1
            changed = True
            self.hass.bus.async_fire(
                EVENT_DUE,
                {
                    "occurrence_id": occurrence["id"],
                    "regimen_id": regimen["id"],
                    "regimen_name": regimen["name"],
                    "scheduled_at": occurrence["scheduled_at"],
                    "reminders_sent": occurrence["reminders_sent"],
                },
            )
        return changed

    async def _async_notify(
        self, regimen: dict[str, Any], occurrence: dict[str, Any]
    ) -> None:
        if not regimen["notify_services"] and not regimen["scripts"]:
            return
        medications = {item["id"]: item for item in self.data["medications"]}
        lines: list[str] = []
        for item in occurrence["items"]:
            remaining = round(item["planned_dose"] - item["taken_dose"], 3)
            if remaining <= 0:
                continue
            medication = medications.get(item["medication_id"])
            name = (
                medication["name"]
                if medication
                else translate(self.hass, "notification.unknown_medication")
            )
            line = f"{remaining:g} × {name}"
            plan = self.package_plan(item["medication_id"], remaining, strict=False)
            if plan:
                package_labels = []
                for package in plan:
                    metadata = []
                    if package["lot_number"]:
                        metadata.append(
                            translate(
                                self.hass,
                                "notification.lot",
                                lot=package["lot_number"],
                            )
                        )
                    if package["expires_on"]:
                        metadata.append(
                            translate(
                                self.hass,
                                "notification.expires",
                                date=package["expires_on"],
                            )
                        )
                    suffix = f" [{', '.join(metadata)}]" if metadata else ""
                    unit = medication["unit"] if medication else ""
                    package_labels.append(
                        f"{package['nickname']} ({package['amount']:g} {unit}){suffix}"
                    )
                line += " " + translate(
                    self.hass,
                    "notification.from_packages",
                    packages=", ".join(package_labels),
                )
            lines.append(line)
        occurrence_id = occurrence["id"]
        path = f"/{DOMAIN}?occurrence={occurrence_id}"
        service_data = {
            "title": translate(self.hass, "notification.title"),
            "message": f"{regimen['name']}: " + ", ".join(lines),
            "data": {
                "tag": f"{DOMAIN}_{occurrence_id}",
                "url": path,
                "clickAction": path,
                "actions": [
                    {
                        "action": f"MED_TAKE_{occurrence_id}",
                        "title": translate(self.hass, "notification.take_all"),
                    },
                    {
                        "action": f"MED_SNOOZE30_{occurrence_id}",
                        "title": translate(self.hass, "notification.snooze_30"),
                    },
                    {
                        "action": f"MED_SKIP_{occurrence_id}",
                        "title": translate(self.hass, "notification.skip"),
                    },
                ],
            },
        }
        for target in regimen["notify_services"]:
            domain, separator, service = target.partition(".")
            if not separator or not self.hass.services.has_service(domain, service):
                _LOGGER.warning("Notification service %s is unavailable", target)
                continue
            try:
                await self.hass.services.async_call(
                    domain, service, service_data, blocking=False
                )
            except Exception:  # Home Assistant logs provider-specific details.
                _LOGGER.exception("Could not send medication reminder via %s", target)
        for entity_id in regimen["scripts"]:
            try:
                await self.hass.services.async_call(
                    "script",
                    "turn_on",
                    {"entity_id": entity_id},
                    blocking=False,
                )
            except Exception:
                _LOGGER.exception(
                    "Could not run medication reminder script %s", entity_id
                )

    @callback
    def _handle_notification_action(self, event: Event) -> None:
        action = str(event.data.get("action", ""))
        operation = None
        if action.startswith("MED_TAKE_"):
            operation = self.async_record_intake(
                action.removeprefix("MED_TAKE_"), user_id=None
            )
        elif action.startswith("MED_SNOOZE30_"):
            operation = self.async_snooze(
                action.removeprefix("MED_SNOOZE30_"),
                dt_util.now() + timedelta(minutes=30),
            )
        elif action.startswith("MED_SKIP_"):
            operation = self.async_skip(action.removeprefix("MED_SKIP_"))
        if operation is not None:
            self.hass.async_create_task(
                self._async_run_notification_action(operation)
            )

    async def _async_run_notification_action(self, operation) -> None:
        """Run a mobile action without leaking stale-action exceptions."""
        try:
            await operation
        except (ValueError, TypeError, KeyError) as err:
            _LOGGER.warning("Ignored invalid medication notification action: %s", err)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _changed(self) -> None:
        self._trim_history()
        await self._store.async_save(self.data)
        self._notify_listeners()

    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:  # A broken listener must not stop the others.
                _LOGGER.exception("Medication Reminder listener failed")

    def _trim_history(self) -> None:
        completed = sorted(
            (
                item
                for item in self.data["occurrences"]
                if item["status"] in CLOSED_STATUSES
            ),
            key=lambda item: item.get("taken_at") or item["scheduled_at"],
            reverse=True,
        )
        keep_ids = {item["id"] for item in completed[:MAX_HISTORY]}
        self.data["occurrences"] = [
            item
            for item in self.data["occurrences"]
            if item["status"] not in CLOSED_STATUSES or item["id"] in keep_ids
        ]

    def _medication_name(self, medication_id: str) -> str:
        medication = self._find("medications", medication_id)
        return medication["name"] if medication else "?"

    def _find(self, collection: str, item_id: str | None) -> dict[str, Any] | None:
        if not item_id:
            return None
        return next(
            (item for item in self.data[collection] if item["id"] == item_id), None
        )

    def _require(self, collection: str, item_id: str) -> dict[str, Any]:
        item = self._find(collection, item_id)
        if item is None:
            raise ValueError(f"Unknown {collection.rstrip('s')}")
        return item

    def _new_scan_code(self, seed: str) -> str:
        """Allocate a compact code without changing any existing assignment."""
        return generate_scan_code(seed, used_scan_codes(self.data))


def _is_due(occurrence: dict[str, Any], now: datetime) -> bool:
    """Return whether an open occurrence is due and not currently snoozed."""
    scheduled = _parse_optional_datetime(occurrence.get("scheduled_at"))
    if scheduled is None or dt_util.as_local(scheduled) > now:
        return False
    snoozed = _parse_optional_datetime(occurrence.get("snoozed_until"))
    return snoozed is None or dt_util.as_local(snoozed) <= now


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as err:
        raise ValueError("Taken dose must be a number") from err


def _parse_optional_datetime(value: str | None) -> datetime | None:
    """Parse an optional stored timestamp safely."""
    return dt_util.parse_datetime(value) if value else None
