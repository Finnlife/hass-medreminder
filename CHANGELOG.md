# Changelog

Every released version is described here, in English, so an update in HACS says
what actually changed. The release workflow reads the section matching the
version in the integration manifest and refuses to publish without one.

Entries are grouped as **Added**, **Changed**, **Fixed**, **Removed** and
**Security**, newest version first. Versions follow the manifest, and the
project is still pre-1.0: the storage compatibility contract is not final until
version 1.0.

## 0.9.5

This release closes the findings of a security review. Several of them could be
reached by any signed-in user, not only by an administrator.

### Changed

- Adding, editing and deleting medications, packages and plans, importing and
  exporting a backup and deleting all data now require an administrator. The
  `add_package` and `delete_all_data` actions are admin actions; automations
  can still call them. Recording, snoozing and skipping an intake and planning
  or cancelling a one-off intake stay open to every user.
- A plan holds at most 24 intake times per day.
- An intake that has been open for 30 days is closed as missed, even when its
  plan has no miss timeout, so open intakes no longer pile up forever.
- The pending and due intake sensors list at most 20 intakes in their
  attributes; their state still counts all of them.
- Only one label is printed at a time.

### Fixed

- A crafted backup could store markup in an ID that the panel and the card
  then rendered unescaped, running script in the browser of whoever opened
  them next. Every value placed in the markup is escaped now, imported IDs
  must look like generated ones, and every imported record goes through the
  same validation as a save from the panel.
- A calendar request over an arbitrary range walked every day in it and could
  stall Home Assistant. A request now covers at most a year.
- A reminder restored with a repeat interval of zero fired on every tick.
- A backup holding an open one-off intake could not be restored.

### Security

- The workflows pin every action to a commit, the release job keeps no git
  credentials in its workspace, and the version reaches the release scripts
  through the environment instead of being expanded into them.

## 0.9.4

### Fixed

- A reminder could call any Home Assistant service, not only a notification.
  Its targets come from the panel, a backup import and the `schedule_intake`
  action, which non-admin users can reach as well, and the call runs later
  without a user context, so a non-admin user could make the integration call
  admin-only services. Reminder targets are now restricted to `notify.*`
  services and reminder scripts to `script.*` entities; anything else is
  rejected when it is saved or imported. Targets stored by an earlier version
  that do not match are skipped and logged instead of being called.

## 0.9.3

### Added

- The manifest lists the integration under Health & wellbeing and under
  Calendars & to-dos, so Home Assistant can file it in the matching category
  when browsing integrations.

## 0.9.2

### Changed

- The HACS validation now runs every check, including the brand assets, against
  the icon the integration ships itself. Nothing changed in the integration.

## 0.9.1

### Changed

- An automatic package nickname is now drawn at random from the names no open
  package is using, instead of taking the next one in the list, so packages
  added one after another no longer get names that look alike.

## 0.9.0

### Changed

- A package nickname now has to be unique across the whole instance rather than
  only within one medication, so a nickname always points at exactly one box.
  Only packages that still hold stock take part, so an empty package releases
  its name again and the pool cannot run dry. Existing data with a name used
  twice is numbered during the upgrade.
- The pool grew from 16 to 78 names, and the automatic pick now draws from the
  names no open package is using.
- The nickname field no longer offers a dropdown. Either type a name or leave it
  empty for an automatic one; both end up unique.

## 0.8.1

### Fixed

- The gear icon on the integration page jumped to the Medications panel instead
  of opening the options, so label printing could not be configured at all. The
  panel no longer claims to be the configuration page of the integration.

## 0.8.0

### Added

- Every QR code in the panel can be printed on a Zebra label printer. Printing
  runs through a labelprint service on the MQTT broker Home Assistant is already
  connected to, so the integration keeps no broker credentials of its own, and a
  press sends nothing but the scan code and the name shown with it.
- The integration gained an options dialog for printing: switch it on, set the
  base topic, the template, the label size and the number of copies.

### Fixed

- The icon generator for the screenshot harness required an argument the
  documented command did not pass, so it could not be run as described.

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
