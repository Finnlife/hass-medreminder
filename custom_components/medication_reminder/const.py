"""Constants for Medication Reminder."""

from typing import Final

DOMAIN: Final = "medication_reminder"
PLATFORMS: Final = ["sensor", "binary_sensor"]
STORAGE_KEY: Final = f"{DOMAIN}.data"
STORAGE_VERSION: Final = 1
PANEL_URL: Final = DOMAIN
PANEL_STATIC_URL: Final = f"/{DOMAIN}_frontend"
SIGNAL_UPDATE: Final = f"{DOMAIN}_update"

EVENT_DUE: Final = f"{DOMAIN}_due"
EVENT_TAKEN: Final = f"{DOMAIN}_taken"
EVENT_SKIPPED: Final = f"{DOMAIN}_skipped"
EVENT_LOW_STOCK: Final = f"{DOMAIN}_low_stock"

DEFAULT_REPEAT_MINUTES: Final = 30
MAX_HISTORY: Final = 2000

