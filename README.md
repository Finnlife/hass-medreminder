# Medication Reminder for Home Assistant

[Deutsch](README.de.md)

A local Home Assistant custom integration for medication schedules, stock tracking,
actionable reminders, and an auditable planned-versus-actual intake history. After
setup, **Medications** appears as a dedicated sidebar panel.

## Features

- Medication records with manufacturer, barcode/product code, strength, dosage
  form, stock unit, current stock, warning threshold, and notes
- Weekly schedules with different times per weekday and multiple times per day
- Interval schedules for every x days from a chosen start date
- Multiple medications and individual doses in one intake
- Repeating reminders through selected `notify.*` services and scripts
- Mobile actions to mark everything taken, snooze for 30 minutes, or open details
- Partial intake, 30/60/120-minute and custom-time snooze, and skip controls in the app
- Persistent open tickets and planned-versus-actual history
- Stock deduction only after an intake is actually recorded
- Sensors, binary sensors, events, and actions for dashboards and automations
- English by default, with German UI, entity, setup, action, and notification translations

## Installation

### HACS custom repository

1. In HACS, open **Integrations**, then the three-dot menu and **Custom repositories**.
2. Add `https://github.com/Finnlife/hass-medreminder` as an **Integration**.
3. Download **Medication Reminder** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**, search for
   **Medication Reminder**, and add it once.
5. Open **Medications** in the sidebar.

Alternatively, copy `custom_components/medication_reminder` to the same path in
your Home Assistant configuration and restart Home Assistant.

Action buttons require a notification service that supports Home Assistant
actions, such as a Companion App `notify.mobile_app_*` service. Other notification
providers may display the message without its buttons.

## Home Assistant interfaces

Global entities represent the next, pending, last, and overdue intakes. Each
medication also creates a stock sensor and a low-stock binary sensor. Home Assistant
assigns final entity IDs, which can be changed in the device view.

Actions:

- `medication_reminder.record_intake`
- `medication_reminder.snooze`
- `medication_reminder.adjust_stock`

Events:

- `medication_reminder_due`
- `medication_reminder_taken`
- `medication_reminder_skipped`
- `medication_reminder_low_stock`

## Storage and behavior

All data remains in Home Assistant under `.storage/medication_reminder.data`.
After a restart, missed scheduled times are generated for up to 30 days. Intake
recording is idempotent: using an old completed notification action again does not
deduct stock twice. The latest 2,000 completed occurrences are retained, while
open occurrences are never removed automatically.

## Development and testing

See [docs/TESTING.md](docs/TESTING.md) for automated checks, the isolated Docker
test instance, and the exact handoff needed for a full Codex browser test.

