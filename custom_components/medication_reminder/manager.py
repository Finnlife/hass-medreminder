"""Runtime manager for Medication Reminder."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import math
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_DUE,
    EVENT_LOW_STOCK,
    EVENT_SKIPPED,
    EVENT_TAKEN,
    MAX_HISTORY,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .localization import translate
from .models import (
    empty_data,
    normalize_medication,
    normalize_regimen,
    occurrence_for,
    public_data,
)
from .schedule import next_occurrence, occurrences_between

_LOGGER = logging.getLogger(__name__)


class MedicationManager:
    """Own persistent state, reminders and domain invariants."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = empty_data()
        self._lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._unsub_timer: Callable[[], None] | None = None
        self._unsub_actions: Callable[[], None] | None = None

    async def async_initialize(self) -> None:
        """Load storage and start listeners."""
        loaded = await self._store.async_load()
        if loaded:
            self.data = loaded
        self.data.setdefault("medications", [])
        self.data.setdefault("regimens", [])
        self.data.setdefault("occurrences", [])
        self.data.setdefault("last_generated_at", None)
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
        result["server_time"] = dt_util.now().isoformat()
        upcoming: list[dict[str, str]] = []
        now = dt_util.now()
        for regimen in self.data["regimens"]:
            if not regimen.get("active", True):
                continue
            value = next_occurrence(regimen["schedule"], now)
            if value:
                upcoming.append({"regimen_id": regimen["id"], "scheduled_at": value.isoformat()})
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

    async def async_save_medication(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Create or update a medication."""
        async with self._lock:
            medication_id = str(raw.get("id", "")) or None
            existing = self._find("medications", medication_id) if medication_id else None
            medication = normalize_medication(raw, medication_id)
            if existing:
                self.data["medications"][self.data["medications"].index(existing)] = medication
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
            await self._changed()

    async def async_adjust_stock(self, medication_id: str, delta: float) -> dict[str, Any]:
        """Adjust stock while preventing a negative result."""
        async with self._lock:
            medication = self._require("medications", medication_id)
            new_stock = round(float(medication["stock"]) + float(delta), 3)
            if not math.isfinite(new_stock) or new_stock < 0:
                raise ValueError("Stock cannot become negative")
            medication["stock"] = new_stock
            await self._changed()
            return public_data(medication)

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
            now = dt_util.now().isoformat()
            changes: list[tuple[dict[str, Any], dict[str, Any], float, float]] = []
            for item in occurrence["items"]:
                remaining = round(item["planned_dose"] - item["taken_dose"], 3)
                requested = remaining if doses is None else float(doses.get(item["medication_id"], 0))
                if not math.isfinite(requested) or requested < 0 or requested > remaining:
                    raise ValueError("Taken dose exceeds the remaining planned dose")
                if requested == 0:
                    continue
                medication = self._require("medications", item["medication_id"])
                before = float(medication["stock"])
                if requested > before:
                    raise ValueError(f"Not enough stock for {medication['name']}")
                changes.append((item, medication, requested, before))
            if not changes:
                raise ValueError("No dose was selected")

            # Apply only after every requested dose has passed validation. This keeps
            # multi-medication intakes atomic when one stock is insufficient.
            for item, medication, requested, before in changes:
                medication["stock"] = round(before - requested, 3)
                item["taken_dose"] = round(item["taken_dose"] + requested, 3)
                item["taken_at"] = now
                if before > medication["low_stock_threshold"] >= medication["stock"]:
                    self.hass.bus.async_fire(
                        EVENT_LOW_STOCK,
                        {"medication_id": medication["id"], "stock": medication["stock"]},
                    )
            complete = all(
                item["taken_dose"] >= item["planned_dose"] for item in occurrence["items"]
            )
            occurrence["status"] = "taken" if complete else "partial"
            occurrence["taken_at"] = now if complete else None
            occurrence["completed_by"] = user_id if complete else None
            occurrence["snoozed_until"] = None
            await self._changed()
            self.hass.bus.async_fire(
                EVENT_TAKEN,
                {
                    "occurrence_id": occurrence_id,
                    "regimen_id": occurrence["regimen_id"],
                    "complete": complete,
                    "items": public_data(occurrence["items"]),
                },
            )
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

    async def async_skip(self, occurrence_id: str, user_id: str | None = None) -> dict[str, Any]:
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
                {"occurrence_id": occurrence_id, "regimen_id": occurrence["regimen_id"]},
            )
            return public_data(occurrence)

    async def _async_tick(self, now: datetime) -> None:
        """Create due tickets and emit reminders."""
        async with self._lock:
            now = dt_util.as_local(now)
            previous_raw = self.data.get("last_generated_at")
            previous = (
                _parse_optional_datetime(previous_raw) or now - timedelta(minutes=1)
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
                created_at = _parse_optional_datetime(regimen.get("created_at")) or previous
                range_start = max(previous - timedelta(minutes=1), dt_util.as_local(created_at))
                for scheduled in occurrences_between(regimen["schedule"], range_start, now):
                    key = (regimen["id"], scheduled.isoformat())
                    if key not in known:
                        ticket = occurrence_for(regimen, scheduled)
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

    async def _async_notify(self, regimen: dict[str, Any], occurrence: dict[str, Any]) -> None:
        names = {item["id"]: item["name"] for item in self.data["medications"]}
        lines = [
            f"{item['planned_dose'] - item['taken_dose']:g} × "
            f"{names.get(item['medication_id'], translate(self.hass, 'notification.unknown_medication'))}"
            for item in occurrence["items"]
            if item["taken_dose"] < item["planned_dose"]
        ]
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
                await self.hass.services.async_call(domain, service, service_data, blocking=False)
            except Exception:  # Home Assistant logs provider-specific details.
                _LOGGER.exception("Could not send medication reminder via %s", target)
        for entity_id in regimen["scripts"]:
            try:
                await self.hass.services.async_call(
                    "script", "turn_on", {"entity_id": entity_id}, blocking=False
                )
            except Exception:
                _LOGGER.exception("Could not run medication reminder script %s", entity_id)

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
        return next((item for item in self.data[collection] if item["id"] == item_id), None)

    def _require(self, collection: str, item_id: str) -> dict[str, Any]:
        item = self._find(collection, item_id)
        if item is None:
            raise ValueError(f"Unknown {collection.rstrip('s')}")
        return item


def _parse_optional_datetime(value: str | None) -> datetime | None:
    """Parse an optional stored timestamp safely."""
    return dt_util.parse_datetime(value) if value else None
