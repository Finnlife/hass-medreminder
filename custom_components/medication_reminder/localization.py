"""Small runtime catalog for notification content."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant

_CATALOGS: Mapping[str, Mapping[str, str]] = {
    "en": {
        "notification.title": "Medication intake",
        "notification.unknown_medication": "Medication",
        "notification.take_all": "Mark all taken",
        "notification.snooze_30": "Remind me in 30 min",
        "notification.details": "Details",
    },
    "de": {
        "notification.title": "Medikamenteneinnahme",
        "notification.unknown_medication": "Medikament",
        "notification.take_all": "Alles genommen",
        "notification.snooze_30": "In 30 Min. erinnern",
        "notification.details": "Details",
    },
}


def translate(hass: HomeAssistant, key: str, **variables: Any) -> str:
    """Translate a runtime string using Home Assistant's configured language."""
    language = str(getattr(hass.config, "language", "en") or "en").lower().split("-")[0]
    catalog = _CATALOGS.get(language, _CATALOGS["en"])
    template = catalog.get(key, _CATALOGS["en"].get(key, key))
    return template.format(**variables)
