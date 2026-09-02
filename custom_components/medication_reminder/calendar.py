"""Calendar entity showing planned and recorded medication intakes."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import MedicationReminderEntity
from .manager import MedicationManager

EVENT_DURATION = timedelta(minutes=15)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the medication schedule calendar."""
    manager: MedicationManager = hass.data[DOMAIN]["managers"][entry.entry_id]
    async_add_entities([MedicationScheduleCalendar(manager)])


class MedicationScheduleCalendar(MedicationReminderEntity, CalendarEntity):
    """Planned intakes of every active schedule as calendar events."""

    _attr_translation_key = "schedule_calendar"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "schedule_calendar")

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        events = self.manager.planned_events(now, now + timedelta(days=90))
        return _to_event(events[0]) if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        events = self.manager.planned_events(
            dt_util.as_local(start_date), dt_util.as_local(end_date)
        )
        return [_to_event(event) for event in events]


def _to_event(event: dict) -> CalendarEvent:
    return CalendarEvent(
        start=event["start"],
        end=event["start"] + EVENT_DURATION,
        summary=event["summary"],
        description="\n".join(
            part for part in (event["description"], event["instructions"]) if part
        )
        or None,
        uid=f"{event['regimen_id']}-{event['start'].isoformat()}",
    )
