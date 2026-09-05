# Medication Reminder for Home Assistant

<img src="https://raw.githubusercontent.com/Finnlife/hass-medreminder/main/custom_components/medication_reminder/frontend/logo.png" alt="Medication Reminder logo" width="160">

[Deutsch](https://github.com/Finnlife/hass-medreminder/blob/main/README.de.md)

> [!CAUTION]
> **Do not rely on this project for real medication.**
>
> This is a hobby project. It was written for one purpose: reminding its author to
> take vitamins. It is **not** a medical device, it is not certified, validated or
> reviewed by anyone, and it comes with no warranty of any kind.
>
> Reminders can silently fail to arrive, and the recorded history can be wrong or
> incomplete. A Home Assistant restart, an update, a failed notification service, a
> phone in do-not-disturb mode, an empty battery, a bug in this code or a mistake in
> your own configuration are all enough to make a dose disappear without a trace.
>
> If you take prescription medication, or any medication where a missed, doubled or
> mistimed dose matters, **never** use this project as your only reminder or as your
> only intake record. Keep a pill organiser, a paper log, a pharmacy app or whatever
> your doctor or pharmacist recommends, and treat anything shown here as a
> convenience on top of that. For questions about your medication, ask your doctor
> or pharmacist, not this README.

A local Home Assistant custom integration for medication schedules, stock tracking,
actionable reminders, and an auditable planned-versus-actual intake history. After
setup, **Medications** appears as a dedicated sidebar panel.

## How this project was built

Large parts of this project were written with AI assistance. Home Assistant's
integration and frontend interfaces were new to the author, and AI was used to
learn them and to produce much of the code. Everything is reviewed and tested
before it lands, but this is worth knowing when you judge how much to trust the
code — please read it yourself before running it on an instance you care about,
and see the caution above regarding real medication.

## Implemented features (v0.7.3)

- Medication records with manufacturer, barcode/product code, strength, dosage
  form, stock unit, warning threshold, and notes; creating one immediately opens
  a second step for its first physical package
- Weekly schedules with different times per weekday and multiple times per day
- Interval schedules for every x days from a chosen start date
- Move a due interval intake to tomorrow and shift the complete future cycle
- Multiple medications and individual doses in one intake
- Unplanned intakes with an optional note and the same stock and audit guarantees
- One-off intakes planned from automations with a reason, a deduplication
  reference and their own reminder settings
- Repeating reminders through selected `notify.*` services and scripts, with a
  reminder window that stops notification floods after a long absence
- Optional automatic `missed` status for abandoned intakes, so adherence stays honest
- Mobile actions to mark everything taken, snooze for 30 minutes, or skip
- Partial intake, 30/60/120-minute and custom-time snooze, and skip controls in the app
- Persistent open tickets and planned-versus-actual history with status filter and search
- Adherence statistics over the last 30 days
- Date-ranged history export from the History tab as nested JSON or CSV with one
  row per medication dose, including package-allocation snapshots
- Versioned full JSON backup and validated restore
- Stock deduction only after an intake is actually recorded
- Physical packages with expiry date, LOT/batch, printed-code metadata, and a fun
  unique nickname generated automatically when left empty
- Automatic stock calculated from packages, with FEFO recommendations, dose
  splitting across packages, days-of-supply estimates and expiry warnings
- Locally generated, high-contrast QR codes for medications, packages, and open
  intake tickets; the generator accepts only stable eight-character identifiers
  such as `med7K2QF`, never a URL or medication data
- Sensors, binary sensors, a to-do list, a calendar, events, and actions for
  dashboards and automations
- A Lovelace card that records, snoozes and skips due intakes straight from a
  dashboard, registered automatically without a manual resource entry
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

All entities belong to a **Medication schedule** service device; every medication
also gets its own device so dashboards can group by medication.

Global entities:

| Entity | Type | Notes |
| --- | --- | --- |
| Next intake | sensor (timestamp) | attributes: plan, medications, doses |
| Open intakes | sensor (count) | attributes: occurrence IDs and summaries |
| Due now | sensor (count) | only unresolved, unsnoozed intakes |
| Last intake | sensor (timestamp) | attributes: plan and summary |
| Adherence | sensor (%) | 30-day window, diagnostic category |
| Intake due | binary sensor (problem) | attributes: count and summaries |
| Medication intakes | to-do list | ticking an item records the intake, deleting skips it |
| Medication schedule | calendar | planned intakes of every active plan |

Per medication:

| Entity | Type | Notes |
| --- | --- | --- |
| Stock | sensor (measurement) | unit from the medication, package metadata as attributes |
| Days of supply | sensor (days) | stock divided by the planned daily amount |
| Low stock | binary sensor (problem) | at or below the warning threshold |
| Package expiring | binary sensor (problem) | a usable package expires within 30 days |

Every physical package additionally gets its own stock sensor with LOT, expiry
date, initial quantity and printed code as attributes. Home Assistant assigns the
final entity IDs, which can be changed in the device view. Deleting a medication or
package in the panel also removes its device and entities from the registries.

Actions:

- `medication_reminder.record_intake`
- `medication_reminder.record_unplanned_intake`
- `medication_reminder.schedule_intake`
- `medication_reminder.cancel_intake`
- `medication_reminder.skip_intake`
- `medication_reminder.snooze`
- `medication_reminder.postpone_interval`
- `medication_reminder.add_package`
- `medication_reminder.delete_all_data` (requires `confirmation: DELETE`)

Events:

- `medication_reminder_due`
- `medication_reminder_taken`
- `medication_reminder_skipped`
- `medication_reminder_missed`
- `medication_reminder_low_stock`
- `medication_reminder_postponed`

## One-off intakes from automations

`medication_reminder.schedule_intake` plans a single intake that does not belong
to a repeating plan, so an automation can react to something that happened:

```yaml
automation:
  - alias: Magnesium after the gym
    triggers:
      - trigger: zone
        entity_id: person.finn
        zone: zone.gym
        event: leave
    actions:
      - action: medication_reminder.schedule_intake
        data:
          items:
            - medication: Magnesium
              dose: 2
          time: "20:00"
          reason: Workout
          reference: "gym-{{ now().date() }}"
          notify_services:
            - notify.mobile_app_phone
```

The intake then behaves like any other: it shows up in the panel, on the card, in
the to-do list and in the calendar, it reminds through the given services, it
deducts stock when recorded, and it counts towards adherence.

**Picking the medication.** Each item needs a `dose` plus either `medication_id`
or `medication`. `medication` accepts the medication name or its printed scan
code, so automations stay readable and do not have to carry internal ids.

**Picking the time.** Give exactly one of:

| Option | Meaning |
| --- | --- |
| `scheduled_at` | An absolute date and time |
| `time` | A clock time today, or tomorrow when that time has already passed |
| `time` + `date` | A clock time on that exact day |
| `in_minutes` | Minutes from now |

Without any of them the intake is due immediately.

**Running twice is safe.** With a `reference`, a second call for the same
reference reschedules the existing open intake instead of adding a duplicate, and
keeps its ID so an already-sent notification stays valid. Pick a reference that is
stable for the event, for example `gym-{{ now().date() }}`.

**Other options.** `title` sets the heading (defaults to the reason), `scripts`
runs scripts on every reminder, and `repeat_minutes`, `reminder_window_minutes`
and `auto_miss_after_minutes` work exactly like the settings of a repeating plan.

The action returns the created intake, so a following step can use it:

```yaml
      - action: medication_reminder.schedule_intake
        response_variable: planned
        data:
          items:
            - medication: Magnesium
              dose: 2
          in_minutes: 90
      - action: notify.mobile_app_phone
        data:
          message: "Magnesium planned for {{ planned.scheduled_at }}"
```

`medication_reminder.cancel_intake` removes a planned one-off intake again, by
`occurrence_id` or by `reference`. It only touches one-off intakes that are still
open and untouched, and it writes nothing to the history, so a cancelled plan
does not count as skipped:

```yaml
      - action: medication_reminder.cancel_intake
        data:
          reference: "gym-{{ now().date() }}"
```

## Lovelace card

The integration registers `custom:medication-reminder-card` automatically, so no
Lovelace resource has to be added by hand. Add it from the card picker
(**Medication Reminder**) or in YAML:

```yaml
type: custom:medication-reminder-card
title: Medication
mode: due
max: 5
allow_partial: true
show_snooze: true
show_skip: true
show_upcoming: true
upcoming_count: 3
show_stock: true
stock_filter: low
```

| Option | Default | Description |
| --- | --- | --- |
| `title` | `Medication` | Card heading; an empty string hides the header |
| `mode` | `due` | `due` shows only intakes that are due, `open` shows every open intake |
| `max` | `5` | Maximum number of intakes listed, the rest is summarised in one line |
| `allow_partial` | `true` | Editable dose fields for partial intakes; `false` records the full remaining dose |
| `show_snooze` | `true` | 30/60/120-minute snooze buttons |
| `show_skip` | `true` | Skip button |
| `show_upcoming` | `true` | List of the next scheduled intakes |
| `upcoming_count` | `3` | How many upcoming intakes are listed |
| `show_stock` | `false` | Stock overview with a bar per medication |
| `stock_filter` | `low` | `low` lists only medications at or below their threshold, `all` lists every one |

The card uses the integration's WebSocket API, so it shows the same package
recommendations as the panel and records partial doses. It refreshes on every
Medication Reminder event and additionally polls every 15 seconds.

### The card does not show up

The card module is registered by the integration itself, so it only appears
after Home Assistant has loaded the new files. In order:

1. **Restart Home Assistant.** Copying the files or updating in HACS is not
   enough — the module is registered while the integration starts.
2. **Check that the file is served.** Open
   `/medication_reminder_frontend/medication-reminder-card.js` on your Home
   Assistant host. A 404 means the update did not reach the `custom_components`
   directory; anything else means the file is there.
3. **Reload the browser without its cache** (Ctrl+Shift+R, or clear the app
   cache in the Companion App). The script tag lives in the dashboard page
   itself, so a cached page will not contain it.
4. **Look under "Custom" in the card picker**, or search for *Medication*.
5. **Check the browser console** for an error mentioning `localize.js`. That
   would mean only part of the frontend folder was updated.

As a fallback the module can also be added by hand under **Settings →
Dashboards → three-dot menu → Resources**, as a JavaScript module with the URL
`/medication_reminder_frontend/medication-reminder-card.js`.

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
After a restart, missed scheduled times are reconstructed for up to 30 days.
Intake recording is idempotent: using an old completed notification action again
does not deduct stock twice. The latest 2,000 closed occurrences are retained,
while open occurrences are never removed automatically.

Each plan controls its own reminder behaviour:

- **Repeat every** – how often an open reminder is repeated.
- **Stop reminding after** – no further notifications once this many minutes have
  passed since the due time. The ticket stays open in the panel. `0` keeps
  reminding until the intake is resolved. This prevents a notification flood after
  a holiday or a long shutdown.
- **Mark as missed after** – closes an abandoned intake as `missed` without
  touching stock, so adherence statistics stay honest. `0` keeps it open forever.

Snoozing always wins over the repeat interval: when a snooze expires, the next
reminder is sent immediately instead of waiting for the repeat window.

Editing a plan removes its untouched future tickets so schedule changes take
effect right away; due and partially completed tickets are kept.

The trash button in the panel header can permanently delete all Medication
Reminder records after a second confirmation with `DELETE`. This keeps the
integration itself installed. The same server-side confirmation is required by the
Home Assistant action.

The storage schema is versioned. Legacy manual stock is converted into a physical
`Legacy` package, and stock is always recalculated from package remainders. This
project is still pre-1.0: back up `.storage/medication_reminder.data` before
upgrading because the storage compatibility contract is not considered final until
version 1.0.

## Development and testing

See [docs/TESTING.md](https://github.com/Finnlife/hass-medreminder/blob/main/docs/TESTING.md) for automated checks, the isolated Docker
test instance, and the exact handoff needed for a full Codex browser test.

## License

Released under the [MIT License](https://github.com/Finnlife/hass-medreminder/blob/main/LICENSE).
