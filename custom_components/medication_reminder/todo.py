"""To-do list entity exposing every open medication intake."""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import MedicationReminderEntity
from .manager import MedicationManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the intake to-do list."""
    manager: MedicationManager = hass.data[DOMAIN]["managers"][entry.entry_id]
    async_add_entities([MedicationIntakeTodoList(manager)])


class MedicationIntakeTodoList(MedicationReminderEntity, TodoListEntity):
    """Open intake tickets as a native Home Assistant to-do list.

    Completing an item records the full remaining dose, removing one skips it.
    """

    _attr_translation_key = "intake_list"
    _attr_icon = "mdi:clipboard-list-outline"
    _attr_supported_features = (
        TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, manager: MedicationManager) -> None:
        super().__init__(manager, "intake_list")

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=occurrence["id"],
                summary=self.manager.occurrence_label(occurrence),
                status=TodoItemStatus.NEEDS_ACTION,
                due=dt_util.parse_datetime(occurrence["scheduled_at"]),
                description=occurrence.get("regimen_name") or None,
            )
            for occurrence in self.manager.open_occurrences()
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Record the intake when an item is ticked off."""
        if item.status != TodoItemStatus.COMPLETED or not item.uid:
            return
        try:
            await self.manager.async_record_intake(item.uid)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Skip the intakes behind the removed items."""
        for uid in uids:
            try:
                await self.manager.async_skip(uid)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
