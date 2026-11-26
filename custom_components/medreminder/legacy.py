"""Carry an install over from the domain used before version 0.10.

Up to version 0.9 the integration used the domain ``medication_reminder``. That
domain belongs to another integration in the HACS catalog, so it was renamed to
``medreminder``. An install from before the rename is moved over once, the first
time the new integration is set up: the stored data, and the entities and
devices with their ids, so dashboards, automations and history keep working.

Entries of the other integration share the old domain. They are recognised and
never touched: that integration stores a patient in every entry, while this one
stored nothing and kept a hub device of its own.
"""

from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_RESTORED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import entity_sources

from .const import DOMAIN
from .storage import MedicationStore

_LOGGER = logging.getLogger(__name__)

LEGACY_DOMAIN = "medication_reminder"
LEGACY_STORAGE_KEY = f"{LEGACY_DOMAIN}.data"
# Suffix of the old data file once it was copied, kept as a fallback.
MIGRATED_SUFFIX = ".migrated"
REPOSITORY = "Finnlife/hass-medreminder"
LEGACY_FOLDER_ISSUE = "legacy_folder"
STORE_COLLECTIONS = ("medications", "packages", "regimens", "occurrences")

# Since Home Assistant 2026.11 a device belongs to one config entry and moves in
# one step; earlier versions add the new entry and drop the old one.
MOVE_DEVICE_WITH_NEW_ENTRY = (
    "new_config_entry_id"
    in inspect.signature(dr.DeviceRegistry.async_update_device).parameters
)

# States in which the old entry is still busy; moving it now would race it.
_BUSY_STATES = (ConfigEntryState.SETUP_IN_PROGRESS, ConfigEntryState.SETUP_RETRY)


async def async_migrate_legacy_install(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move an install of the old domain over to ``entry``, once."""
    legacy_entries = _legacy_entries(hass)
    if any(old.state in _BUSY_STATES for old in legacy_entries):
        _LOGGER.warning(
            "The previous Medication Reminder install is still starting; "
            "it is moved over on the next start"
        )
        return
    for old in legacy_entries:
        if old.state is ConfigEntryState.LOADED:
            # Unloading saves its data and releases its entities, which can
            # only change integration while nothing has them loaded.
            await hass.config_entries.async_unload(old.entry_id)

    copied = await async_copy_legacy_storage(hass)
    if copied:
        _LOGGER.info("Moved the stored data over from %s", LEGACY_STORAGE_KEY)

    for old in legacy_entries:
        try:
            _move_registry_entries(hass, old.entry_id, entry.entry_id)
        except ValueError as err:
            # The registry refused an entity. Keep the old entry, so whatever
            # is left of it is moved on the next start instead of being lost.
            _LOGGER.warning(
                "Could not move the previous Medication Reminder install (%s) "
                "over yet (%s); it is tried again on the next start",
                old.entry_id,
                err,
            )
            continue
        _take_over_entry_settings(hass, old, entry)
        await hass.config_entries.async_remove(old.entry_id)
        _LOGGER.info(
            "Moved the previous Medication Reminder install (%s) over", old.entry_id
        )


async def async_copy_legacy_storage(hass: HomeAssistant) -> bool:
    """Copy the old data to the new key unless the new key already holds data.

    Both sides go through Home Assistant's storage helper: it caches the storage
    folder at startup, so a file written next to it would not be seen and would
    be overwritten by an empty store. The old file is kept under a new name, so
    the data survives even if something goes wrong later in the move.
    """
    new_store = MedicationStore(hass)
    existing = await new_store.async_load()
    if existing is not None and any(
        existing.get(collection) for collection in STORE_COLLECTIONS
    ):
        return False
    old_store = MedicationStore(hass, LEGACY_STORAGE_KEY)
    try:
        data = await old_store.async_load()
    except (NotImplementedError, ValueError, TypeError, KeyError) as err:
        _LOGGER.warning(
            "Could not read %s (%s); it was left in place", LEGACY_STORAGE_KEY, err
        )
        return False
    if data is None:
        return False
    if not is_own_data(data):
        _LOGGER.warning(
            "%s does not look like Medication Reminder data; it was left in place",
            LEGACY_STORAGE_KEY,
        )
        return False
    await new_store.async_save(data)
    old_path = Path(hass.config.path(".storage", LEGACY_STORAGE_KEY))
    await hass.async_add_executor_job(_keep_as_backup, old_path)
    return True


def _keep_as_backup(old_path: Path) -> None:
    if old_path.is_file():
        old_path.rename(old_path.with_name(old_path.name + MIGRATED_SUFFIX))


def is_own_data(data: Any) -> bool:
    """Return whether stored data was written by this integration."""
    return isinstance(data, dict) and all(
        isinstance(data.get(collection), list) for collection in STORE_COLLECTIONS
    )


def is_own_entry(entry: ConfigEntry, hub_entry_ids: set[str]) -> bool:
    """Return whether an entry of the old domain belongs to this integration."""
    return entry.entry_id in hub_entry_ids or not entry.data


@callback
def _legacy_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    devices = dr.async_get(hass)
    hub_entry_ids = {
        entry.entry_id
        for entry in hass.config_entries.async_entries(LEGACY_DOMAIN)
        if any(
            (LEGACY_DOMAIN, LEGACY_DOMAIN) in device.identifiers
            for device in dr.async_entries_for_config_entry(devices, entry.entry_id)
        )
    }
    return [
        entry
        for entry in hass.config_entries.async_entries(LEGACY_DOMAIN)
        if is_own_entry(entry, hub_entry_ids)
    ]


@callback
def _take_over_entry_settings(
    hass: HomeAssistant, old: ConfigEntry, entry: ConfigEntry
) -> None:
    """Carry the label printing options and the entry title over.

    Both live on the config entry itself, not in the stored data, so they
    would be lost with the old entry. Settings already made on the new entry
    win.
    """
    changes: dict[str, Any] = {}
    if old.options and not entry.options:
        changes["options"] = dict(old.options)
    if old.title and old.title != entry.title:
        changes["title"] = old.title
    if changes:
        hass.config_entries.async_update_entry(entry, **changes)


def new_unique_id(unique_id: str) -> str:
    """Return the unique id an entity has under the new domain."""
    prefix = f"{LEGACY_DOMAIN}_"
    return (
        DOMAIN + "_" + unique_id[len(prefix) :]
        if unique_id.startswith(prefix)
        else unique_id
    )


def new_identifier(identifier: tuple[str, str]) -> tuple[str, str]:
    """Return the device identifier a device has under the new domain."""
    domain, value = identifier
    if domain != LEGACY_DOMAIN:
        return identifier
    return (DOMAIN, DOMAIN if value == LEGACY_DOMAIN else value)


@callback
def _move_registry_entries(hass: HomeAssistant, old_id: str, new_id: str) -> None:
    """Hand devices and entities of the old entry to the new one, ids intact."""
    # Entities first: since Home Assistant 2026.11 moving a device to another
    # entry also drops the entities still linked to the old one, which would
    # then be created afresh and lose the ids and names users gave them.
    entities = er.async_get(hass)
    loaded = entity_sources(hass)
    for entity in er.async_entries_for_config_entry(entities, old_id):
        if entity.platform != LEGACY_DOMAIN:
            continue
        _drop_placeholder_state(hass, entity.entity_id, loaded)
        unique_id = new_unique_id(entity.unique_id)
        if existing := entities.async_get_entity_id(entity.domain, DOMAIN, unique_id):
            # Already created under the new domain; keep that one.
            _LOGGER.debug("Keeping %s instead of %s", existing, entity.entity_id)
            entities.async_remove(entity.entity_id)
            continue
        _LOGGER.debug("Moving %s over", entity.entity_id)
        entities.async_update_entity_platform(
            entity.entity_id,
            DOMAIN,
            new_config_entry_id=new_id,
            new_unique_id=unique_id,
        )

    devices = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(devices, old_id):
        identifiers = {new_identifier(item) for item in device.identifiers}
        if MOVE_DEVICE_WITH_NEW_ENTRY:
            devices.async_update_device(
                device.id, new_identifiers=identifiers, new_config_entry_id=new_id
            )
        else:
            devices.async_update_device(
                device.id, new_identifiers=identifiers, add_config_entry_id=new_id
            )
            devices.async_update_device(device.id, remove_config_entry_id=old_id)


@callback
def _drop_placeholder_state(
    hass: HomeAssistant, entity_id: str, loaded: dict[str, Any]
) -> None:
    """Remove the state an unloaded entity leaves behind.

    Unloading an entry leaves its entities as ``unavailable`` placeholders.
    Before Home Assistant 2026.6 the registry refuses to move any entity that
    has a state, so the placeholder has to go; the moved entity writes its
    state again once the new entry sets it up.
    """
    if entity_id in loaded:
        return
    state = hass.states.get(entity_id)
    if state is not None and state.attributes.get(ATTR_RESTORED):
        hass.states.async_remove(entity_id)


async def async_check_legacy_folder(hass: HomeAssistant) -> None:
    """Raise a repair issue while the old copy of this integration is on disk."""
    folder = Path(hass.config.path("custom_components", LEGACY_DOMAIN))
    if await hass.async_add_executor_job(_is_own_legacy_folder, folder):
        ir.async_create_issue(
            hass,
            DOMAIN,
            LEGACY_FOLDER_ISSUE,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=LEGACY_FOLDER_ISSUE,
            translation_placeholders={"path": str(folder)},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, LEGACY_FOLDER_ISSUE)


def _is_own_legacy_folder(folder: Path) -> bool:
    """Return whether the old folder holds this integration, not the other one."""
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return REPOSITORY in str(manifest.get("documentation", "")) or REPOSITORY in str(
        manifest.get("issue_tracker", "")
    )
