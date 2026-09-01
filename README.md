# Medication Reminder for Home Assistant

<img src="custom_components/medication_reminder/frontend/logo.png" alt="Medication Reminder logo" width="160">

[Deutsch](README.de.md)

A local Home Assistant custom integration for medication schedules, stock tracking,
actionable reminders, and an auditable planned-versus-actual intake history. After
setup, **Medications** appears as a dedicated sidebar panel.

## Implemented features (v0.5.0)

- Medication records with manufacturer, barcode/product code, strength, dosage
  form, stock unit, warning threshold, and notes; creating one immediately opens
  a second step for its first physical package
- Weekly schedules with different times per weekday and multiple times per day
- Interval schedules for every x days from a chosen start date
- Move a due interval intake to tomorrow and shift the complete future cycle
- Multiple medications and individual doses in one intake
- Unplanned intakes with the same stock and audit guarantees as scheduled intakes
- Repeating reminders through selected `notify.*` services and scripts
- Mobile actions to mark everything taken, snooze for 30 minutes, or open details
- Partial intake, 30/60/120-minute and custom-time snooze, and skip controls in the app
- Persistent open tickets and planned-versus-actual history
- Date-ranged history export from the History tab as nested JSON or CSV with one
  row per medication dose, including package-allocation snapshots
- Versioned full JSON backup and validated restore for medications, packages,
  schedules, open tickets, and retained history
- Stock deduction only after an intake is actually recorded
- Physical packages with expiry date, LOT/batch, printed-code metadata, and a fun
  unique nickname generated automatically when left empty
- Automatic stock calculated from packages, with FEFO recommendations and dose
  splitting across packages when one package is not enough
- Locally generated, high-contrast QR codes for medications, packages, and open
  intake tickets; the generator accepts only stable eight-character identifiers
  such as `med7K2QF`, never a URL or medication data
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
medication also creates a stock sensor and a low-stock binary sensor. Every physical
package gets its own stock sensor with LOT, expiry date, initial quantity, and printed
code attributes. Home Assistant assigns final entity IDs, which can be changed in the
device view.

Actions:

- `medication_reminder.record_intake`
- `medication_reminder.snooze`
- `medication_reminder.add_package`
- `medication_reminder.record_unplanned_intake`
- `medication_reminder.postpone_interval`
- `medication_reminder.delete_all_data` (requires `confirmation: DELETE`)

Events:

- `medication_reminder_due`
- `medication_reminder_taken`
- `medication_reminder_skipped`
- `medication_reminder_low_stock`
- `medication_reminder_postponed`

## History export

Open **History**, choose an inclusive **From** and **To** date, and download JSON or
CSV. The range uses the recorded time when available and otherwise the scheduled
time. JSON keeps occurrences, doses, and package allocations nested. CSV writes one
row per medication dose and stores package allocations as JSON in the final column.
Only the retained completed and skipped history is exported; open tickets and master
data are not included in this export.

## Full backup and restore

Open **Backup and restore** from the database button in the panel header. A full
backup downloads a versioned JSON file containing every medication, package,
schedule, open ticket, retained history record, and internal scheduling timestamp.

Restore accepts only a compatible Medication Reminder backup. The complete file is
validated and older supported storage data is migrated before anything changes.
After confirmation, restore atomically replaces the current Medication Reminder
data. Download the current backup first if you may need to return to it.

## Storage and behavior

All data remains in Home Assistant under `.storage/medication_reminder.data`.
After a restart, missed scheduled times are generated for up to 30 days. Intake
recording is idempotent: using an old completed notification action again does not
deduct stock twice. The latest 2,000 completed occurrences are retained, while
open occurrences are never removed automatically.

The trash button in the panel header can permanently delete all Medication Reminder
records after a second confirmation with `DELETE`. This keeps the integration itself
installed. The same server-side confirmation is required by the Home Assistant action.

The storage schema is versioned. The current migration converts any legacy manual
stock into a physical `Legacy` package and keeps intake history unchanged. Stock is
always recalculated from package remainders. This project is still
pre-1.0: back up `.storage/medication_reminder.data` before upgrading because the
storage compatibility contract is not considered final until version 1.0.

## Development and testing

See [docs/TESTING.md](docs/TESTING.md) for automated checks, the isolated Docker
test instance, and the exact handoff needed for a full Codex browser test.
