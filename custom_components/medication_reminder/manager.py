"""Runtime manager for Medication Reminder."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, timedelta
import logging
import math
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .backup import build_backup_download, prepare_backup_import
from .const import (
    DOMAIN,
    EVENT_DUE,
    EVENT_LOW_STOCK,
    EVENT_POSTPONED,
    EVENT_SKIPPED,
    EVENT_TAKEN,
    MAX_HISTORY,
    PACKAGE_NICKNAMES,
)
from .history_export import build_history_export
from .migrations import ensure_current_data
from .localization import translate
from .models import (
    empty_data,
    new_id,
    normalize_medication,
    normalize_package,
    normalize_regimen,
    occurrence_for,
    public_data,
)
from .schedule import next_occurrence, occurrences_between
from .scan_codes import generate_scan_code, used_scan_codes
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
            self.hass, self._async_tick, timedelta(seconds=30)
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

    def snapshot(self) -> dict[str, Any]:
        """Return state plus calculated dashboard data."""
        result = public_data(self.data)
        for occurrence in result["occurrences"]:
            if occurrence["status"] not in ("pending", "partial"):
                continue
            for item in occurrence["items"]:
                remaining = round(item["planned_dose"] - item["taken_dose"], 3)
                item["package_plan"] = self.package_plan(
                    item["medication_id"], remaining, strict=False
                )
        result["server_time"] = dt_util.now().isoformat()
        upcoming: list[dict[str, str]] = []
        now = dt_util.now()
        for regimen in self.data["regimens"]:
            if not regimen.get("active", True):
                continue
            value = next_occurrence(regimen["schedule"], now)
            if value:
                upcoming.append(
                    {"regimen_id": regimen["id"], "scheduled_at": value.isoformat()}
                )
        result["upcoming"] = sorted(upcoming, key=lambda item: item["scheduled_at"])
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

    async def async_save_medication(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Create or update a medication."""
        async with self._lock:
            medication_id = str(raw.get("id", "")) or None
            existing = (
                self._find("medications", medication_id) if medication_id else None
            )
            normalized_raw = dict(raw)
            normalized_raw["stock_mode"] = "packages"
            normalized_raw["stock"] = (
                self._package_stock(existing["id"]) if existing else 0
            )
            medication = normalize_medication(normalized_raw, medication_id)
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
            if existing and existing["medication_id"] != medication_id:
                raise ValueError("A package cannot be moved to another medication")
            if not existing and medication.get("stock_mode", "manual") == "manual":
                self._convert_manual_stock_to_package(medication)
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
                or occurrence["status"] in ("taken", "skipped")
            ]
            await self._changed()

    async def async_record_intake(
        self,
        occurrence_id: str,
        doses: dict[str, float] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Record all or selected remaining doses exactly once."""
        async with self._lock:
            occurrence = self._require("occurrences", occurrence_id)
            if occurrence["status"] in ("taken", "skipped"):
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
            if occurrence["status"] not in ("pending", "partial"):
                raise ValueError("Only open intakes can be snoozed")
            occurrence["snoozed_until"] = until.isoformat()
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
            if dt_util.as_local(scheduled).date() > now.date():
                raise ValueError("Only due intakes can shift to tomorrow")
            target_date = now.date() + timedelta(days=1)
            shift_days = (target_date - dt_util.as_local(scheduled).date()).days
            start_date = date.fromisoformat(regimen["schedule"]["start_date"])
            regimen["schedule"]["start_date"] = (
                start_date + timedelta(days=shift_days)
            ).isoformat()
            occurrence["scheduled_at"] = (
                dt_util.as_local(scheduled) + timedelta(days=shift_days)
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
            if occurrence["status"] in ("taken", "skipped"):
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
                else float(doses.get(item["medication_id"], 0))
            )
            if not math.isfinite(requested) or requested < 0 or requested > remaining:
                raise ValueError("Taken dose exceeds the remaining planned dose")
            if requested == 0:
                continue
            medication = self._require("medications", item["medication_id"])
            before = float(medication["stock"])
            if requested > before:
                raise ValueError(f"Not enough stock for {medication['name']}")
            package_parts = (
                self._package_deductions(medication["id"], requested, strict=True)
                if medication.get("stock_mode") == "packages"
                else []
            )
            changes.append(
                {
                    "item": item,
                    "medication": medication,
                    "requested": requested,
                    "before": before,
                    "package_parts": package_parts,
                }
            )
        if not changes:
            raise ValueError("No dose was selected")

        taken_at = dt_util.as_local(recorded_at or dt_util.now()).isoformat()
        for change in changes:
            item = change["item"]
            medication = change["medication"]
            requested = change["requested"]
            parts = change["package_parts"]
            if parts:
                for package, amount in parts:
                    package["remaining_quantity"] = round(
                        package["remaining_quantity"] - amount, 3
                    )
                    item.setdefault("allocations", []).append(
                        self._package_snapshot(package, amount, taken_at)
                    )
                self._recalculate_package_stock(medication["id"])
            else:
                medication["stock"] = round(change["before"] - requested, 3)
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
                        "stock": medication["stock"],
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
                "unplanned": occurrence.get("unplanned", False),
                "complete": complete,
                "items": public_data(occurrence["items"]),
            },
        )

    def package_plan(
        self, medication_id: str, amount: float, *, strict: bool = True
    ) -> list[dict[str, Any]]:
        """Return the FEFO packages recommended for a dose without mutating stock."""
        medication = self._find("medications", medication_id)
        if not medication or medication.get("stock_mode") != "packages" or amount <= 0:
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
        if medication and medication.get("stock_mode") == "packages":
            medication["stock"] = self._package_stock(medication_id)

    def _recalculate_all_package_stock(self) -> None:
        for medication in self.data["medications"]:
            self._recalculate_package_stock(medication["id"])

    def _convert_manual_stock_to_package(self, medication: dict[str, Any]) -> None:
        current = float(medication.get("stock", 0))
        medication["stock_mode"] = "packages"
        if current <= 0:
            medication["stock"] = 0
            return
        package = normalize_package(
            {
                "nickname": "Legacy",
                "quantity": current,
                "remaining_quantity": current,
            },
            medication["id"],
        )
        package["created_at"] = dt_util.now().isoformat()
        package["scan_code"] = self._new_scan_code(f"packages:{package['id']}")
        self.data["packages"].append(package)

    def _next_package_nickname(self, medication_id: str) -> str:
        used = {
            package["nickname"].casefold()
            for package in self._packages_for(medication_id)
        }
        for nickname in PACKAGE_NICKNAMES:
            if nickname.casefold() not in used:
                return nickname
        index = len(used)
        return f"{PACKAGE_NICKNAMES[index % len(PACKAGE_NICKNAMES)]} {index + 1}"

    async def _async_tick(self, now: datetime) -> None:
        """Create due tickets and emit reminders."""
        async with self._lock:
            now = dt_util.as_local(now)
            previous_raw = self.data.get("last_generated_at")
            previous = _parse_optional_datetime(previous_raw) or now - timedelta(
                minutes=1
            )
            previous = max(dt_util.as_local(previous), now - timedelta(days=30))
            known = {
                (item["regimen_id"], item["scheduled_at"])
                for item in self.data["occurrences"]
            }
            created: list[dict[str, Any]] = []
            for regimen in self.data["regimens"]:
                if not regimen.get("active", True):
                    continue
                created_at = (
                    _parse_optional_datetime(regimen.get("created_at")) or previous
                )
                range_start = max(
                    previous - timedelta(minutes=1), dt_util.as_local(created_at)
                )
                for scheduled in occurrences_between(
                    regimen["schedule"], range_start, now
                ):
                    key = (regimen["id"], scheduled.isoformat())
                    if key not in known:
                        ticket = occurrence_for(regimen, scheduled)
                        ticket["scan_code"] = self._new_scan_code(
                            f"occurrences:{ticket['id']}"
                        )
                        self.data["occurrences"].append(ticket)
                        created.append(ticket)
                        known.add(key)
            self.data["last_generated_at"] = now.isoformat()

            changed = bool(created)
            for occurrence in self.data["occurrences"]:
                if occurrence["status"] not in ("pending", "partial"):
                    continue
                due = _parse_optional_datetime(occurrence.get("scheduled_at"))
                snoozed = _parse_optional_datetime(occurrence.get("snoozed_until"))
                if not due or due > now or (snoozed and snoozed > now):
                    continue
                regimen = self._find("regimens", occurrence["regimen_id"])
                if not regimen or not regimen.get("active", True):
                    continue
                last = _parse_optional_datetime(occurrence.get("last_reminded_at"))
                repeat = timedelta(minutes=int(regimen["repeat_minutes"]))
                if last and dt_util.as_local(last) + repeat > now:
                    continue
                await self._async_notify(regimen, occurrence)
                occurrence["last_reminded_at"] = now.isoformat()
                occurrence["snoozed_until"] = None
                occurrence["reminders_sent"] += 1
                changed = True
                self.hass.bus.async_fire(
                    EVENT_DUE,
                    {
                        "occurrence_id": occurrence["id"],
                        "regimen_id": regimen["id"],
                        "scheduled_at": occurrence["scheduled_at"],
                    },
                )
            if changed:
                await self._changed()

    async def _async_notify(
        self, regimen: dict[str, Any], occurrence: dict[str, Any]
    ) -> None:
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
                        "action": "URI",
                        "title": translate(self.hass, "notification.details"),
                        "uri": path,
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
                    "script", "turn_on", {"entity_id": entity_id}, blocking=False
                )
            except Exception:
                _LOGGER.exception(
                    "Could not run medication reminder script %s", entity_id
                )

    @callback
    def _handle_notification_action(self, event: Event) -> None:
        action = str(event.data.get("action", ""))
        if action.startswith("MED_TAKE_"):
            self.hass.async_create_task(
                self._async_run_notification_action(
                    self.async_record_intake(
                        action.removeprefix("MED_TAKE_"), user_id=None
                    )
                )
            )
        elif action.startswith("MED_SNOOZE30_"):
            self.hass.async_create_task(
                self._async_run_notification_action(
                    self.async_snooze(
                        action.removeprefix("MED_SNOOZE30_"),
                        dt_util.now() + timedelta(minutes=30),
                    )
                )
            )

    async def _async_run_notification_action(self, operation) -> None:
        """Run a mobile action without leaking stale-action exceptions."""
        try:
            await operation
        except (ValueError, TypeError, KeyError) as err:
            _LOGGER.warning("Ignored invalid medication notification action: %s", err)

    async def _changed(self) -> None:
        self._trim_history()
        await self._store.async_save(self.data)
        for listener in tuple(self._listeners):
            listener()

    def _trim_history(self) -> None:
        completed = sorted(
            (
                item
                for item in self.data["occurrences"]
                if item["status"] in ("taken", "skipped")
            ),
            key=lambda item: item["scheduled_at"],
            reverse=True,
        )
        keep_ids = {item["id"] for item in completed[:MAX_HISTORY]}
        self.data["occurrences"] = [
            item
            for item in self.data["occurrences"]
            if item["status"] not in ("taken", "skipped") or item["id"] in keep_ids
        ]

    def _find(self, collection: str, item_id: str | None) -> dict[str, Any] | None:
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


def _parse_optional_datetime(value: str | None) -> datetime | None:
    """Parse an optional stored timestamp safely."""
    return dt_util.parse_datetime(value) if value else None
