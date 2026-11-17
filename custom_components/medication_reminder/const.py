"""Constants for Medication Reminder."""

from typing import Final

DOMAIN: Final = "medication_reminder"
PLATFORMS: Final = ["binary_sensor", "calendar", "sensor", "todo"]
STORAGE_KEY: Final = f"{DOMAIN}.data"
STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 7
PANEL_URL: Final = DOMAIN
PANEL_STATIC_URL: Final = f"/{DOMAIN}_frontend"
FRONTEND_CACHE_KEY: Final = "0.9.0"

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

# --- Label printing over MQTT -------------------------------------------------
# Jobs go to a labelprint service on the broker Home Assistant already uses.
OPTION_PRINTING_ENABLED: Final = "label_printing_enabled"
OPTION_BASE_TOPIC: Final = "label_base_topic"
OPTION_TEMPLATE: Final = "label_template"
OPTION_LABEL_SIZE: Final = "label_size"
OPTION_COPIES: Final = "label_copies"

DEFAULT_BASE_TOPIC: Final = "labelprint"
DEFAULT_TEMPLATE: Final = "qr_nickname"
DEFAULT_COPIES: Final = 1
MAX_COPIES: Final = 20
# The template turns the name sideways next to the code, so a long one would
# only be cut off by the printer.
MAX_LABEL_NAME_LENGTH: Final = 40
# How long a print job waits for the service to answer on the result topic.
PRINT_RESULT_TIMEOUT: Final = 15

OPEN_STATUSES: Final = ("pending", "partial")
CLOSED_STATUSES: Final = ("taken", "skipped", "missed")
ALL_STATUSES: Final = OPEN_STATUSES + CLOSED_STATUSES

# Memorable names for physical packages. A name is only ever handed out
# once among the packages that still hold something, so a nickname always
# points at exactly one box.
PACKAGE_NICKNAMES: Final = (
    "Amber", "Apollo", "Aspen", "Atlas",
    "Banjo", "Basil", "Biscuit", "Bumblebee",
    "Cedar", "Clover", "Cobalt", "Comet",
    "Cosmo", "Daisy", "Delta", "Domino",
    "Dusty", "Echo", "Ember", "Fable",
    "Falcon", "Fern", "Fizz", "Foxy",
    "Ginger", "Gizmo", "Hazel", "Hopper",
    "Indigo", "Ivy", "Jasper", "Juniper",
    "Kiwi", "Koda", "Lagoon", "Lemon",
    "Lumen", "Mango", "Maple", "Marble",
    "Mochi", "Monsoon", "Nimbus", "Nova",
    "Nutmeg", "Olive", "Onyx", "Opal",
    "Pebble", "Pepper", "Pixel", "Plum",
    "Poppy", "Quartz", "Quill", "Raven",
    "Rocket", "Rusty", "Saffron", "Sage",
    "Scout", "Sorrel", "Sunny", "Tango",
    "Thistle", "Topaz", "Truffle", "Tulip",
    "Umber", "Vanilla", "Velvet", "Walnut",
    "Willow", "Yarrow", "Yoshi", "Zephyr",
    "Ziggy", "Zinnia",
)
