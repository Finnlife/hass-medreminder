"""Constants for Medication Reminder."""

from typing import Final

DOMAIN: Final = "medication_reminder"
PLATFORMS: Final = ["binary_sensor", "calendar", "sensor", "todo"]
STORAGE_KEY: Final = f"{DOMAIN}.data"
STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 6
PANEL_URL: Final = DOMAIN
PANEL_STATIC_URL: Final = f"/{DOMAIN}_frontend"
FRONTEND_CACHE_KEY: Final = "0.7.0"

EVENT_DUE: Final = f"{DOMAIN}_due"
EVENT_TAKEN: Final = f"{DOMAIN}_taken"
EVENT_SKIPPED: Final = f"{DOMAIN}_skipped"
EVENT_MISSED: Final = f"{DOMAIN}_missed"
EVENT_LOW_STOCK: Final = f"{DOMAIN}_low_stock"
EVENT_POSTPONED: Final = f"{DOMAIN}_postponed"

DEFAULT_REPEAT_MINUTES: Final = 30
DEFAULT_REMINDER_WINDOW_MINUTES: Final = 180
DEFAULT_AUTO_MISS_MINUTES: Final = 0

# How far back missed schedule entries are reconstructed after a restart.
CATCHUP_DAYS: Final = 30
# How often the manager evaluates schedules and reminders.
TICK_SECONDS: Final = 30
MAX_HISTORY: Final = 2000
ADHERENCE_WINDOW_DAYS: Final = 30
# How far ahead an automation may plan a single intake.
AD_HOC_MAX_LEAD_DAYS: Final = 365

OPEN_STATUSES: Final = ("pending", "partial")
CLOSED_STATUSES: Final = ("taken", "skipped", "missed")
ALL_STATUSES: Final = OPEN_STATUSES + CLOSED_STATUSES

PACKAGE_NICKNAMES: Final = (
    "Apollo",
    "Bumblebee",
    "Comet",
    "Daisy",
    "Echo",
    "Foxy",
    "Kiwi",
    "Mochi",
    "Nova",
    "Pebble",
    "Pixel",
    "Rocket",
    "Sunny",
    "Tango",
    "Yoshi",
    "Ziggy",
)
