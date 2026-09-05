# Changelog

Every released version is described here, in English, so an update in HACS says
what actually changed. The release workflow reads the section matching the
version in the integration manifest and refuses to publish without one.

Entries are grouped as **Added**, **Changed**, **Fixed** and **Removed**, newest
version first. Versions follow the manifest, and the project is still pre-1.0:
the storage compatibility contract is not final until version 1.0.

## 0.7.6

### Changed

- Release notes now come from this changelog instead of being generated from
  commit subjects, so an update describes what changed rather than how it was
  committed.

## 0.7.5

### Added

- The integration ships its own brand icon, so Home Assistant shows the logo in
  HACS, on the integrations page and on its devices instead of a placeholder.

### Changed

- The panel logo dropped from 1254 to 512 pixels. The header draws it at 34
  pixels, so the previous file spent 669 kB of every panel load on resolution
  nobody could see.

## 0.7.4

### Added

- Screenshots of the panel and the card are captured automatically from a
  standalone harness with fixed demo data, in both languages and in a dark
  variant, and appear in the readme.

### Fixed

- The header button for recording an intake referenced an icon that Material
  Design Icons does not have, so Home Assistant rendered an empty box there.

## 0.7.3

### Added

- The language of the panel and the card can be overridden temporarily, through
  `medicationReminder.setLanguage("en")` in the browser console or `?lang=` in
  the panel URL. It only affects the current browser session and exists so the
  interface can be captured in every language without changing the language of
  the whole installation.

## 0.7.2

### Fixed

- The readme rendered a broken logo inside HACS, because HACS renders it in the
  Home Assistant frontend where a relative path resolves against the Home
  Assistant host. All of its links and images are absolute now.

## 0.7.1

### Added

- The repository carries an MIT license and the manifest names an issue tracker,
  both of which the HACS validator requires.

### Changed

- Every push is validated by the unit tests, `ruff`, `hassfest` and the HACS
  validator, and a release is published automatically from the version in the
  manifest.

## 0.7.0

### Added

- One-off intakes can be planned from an automation with
  `medication_reminder.schedule_intake`, for example magnesium in the evening
  after a workout. The medication may be named instead of referenced by id, the
  time may be absolute, a clock time or an offset, and a reason is stored with
  the intake and shown in the app, the reminder and the history export.
- Repeating a trigger is safe: with a `reference`, a second call reschedules the
  existing open intake instead of creating a duplicate.
- `medication_reminder.cancel_intake` removes a planned one-off intake again
  without writing it to the history, so cancelling does not count as skipped.

### Fixed

- Reloading the integration after an update left the previous card module
  registered next to the new one, and the older card class won.

## 0.6.1

### Added

- A Lovelace card shows due intakes on any dashboard and records, snoozes or
  skips them without opening the panel. It is registered automatically, so no
  Lovelace resource has to be added by hand, and it ships a visual editor.
- A to-do list entity and a calendar entity expose the intakes natively, next to
  new sensors for days of supply, adherence, due count and expiring packages.

### Changed

- The panel interface was rebuilt around Home Assistant's own theme, which also
  fixes unreadable contrast in dark themes, and a background refresh no longer
  discards text that is being typed.
- Each plan controls how long it keeps reminding and whether an abandoned intake
  is closed as missed, so a restart after a long absence no longer notifies for
  every reconstructed ticket forever.

### Fixed

- A snooze shorter than the repeat interval was swallowed instead of firing when
  it expired.
- Deleting a medication or a package left its device and entities behind as
  permanently unavailable.
- Stock had two possible sources, and the printed QR codes resolved to nothing
  when scanned.
