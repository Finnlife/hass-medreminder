# Testing guide

This guide creates a disposable Home Assistant instance that Codex can inspect,
restart, and test without touching production data.

## 1. Run the automated checks

Install Python 3 and Node.js, then run from the repository root:

```shell
pip install -r <(python -c "import json;print(chr(10).join(json.load(open('custom_components/medication_reminder/manifest.json'))['requirements']))")
python -m unittest discover -s tests -v
python -m compileall custom_components/medication_reminder tests
node --check custom_components/medication_reminder/frontend/localize.js
node --check custom_components/medication_reminder/frontend/medication-reminder-panel.js
```

For Home Assistant's integration validator, install Docker and run:

```shell
docker run --rm -v "${PWD}:/github/workspace" ghcr.io/home-assistant/hassfest
```

## 2. Start an isolated Home Assistant instance

Install Docker Desktop, make sure port 8123 is free, and run:

```shell
docker compose -f compose.test.yaml up -d
docker compose -f compose.test.yaml logs -f homeassistant
```

Open `http://localhost:8123`, complete onboarding with a test-only owner account,
and add **Medication Reminder** under **Settings → Devices & services**. The
`.ha-test` directory is ignored by Git and may be deleted when the test data is no
longer needed.

After a source change, restart the test instance:

```shell
docker compose -f compose.test.yaml restart homeassistant
```

## 3. Give Codex access for a full test

1. Open `http://localhost:8123` in Codex's in-app Browser.
2. Sign in manually with the test-only Home Assistant account and leave the tab open.
3. Keep the repository itself open as the Codex workspace.
4. Tell Codex explicitly that it may operate and restart this test instance.
5. Use this prompt:

   > The isolated Home Assistant test instance is running at
   > http://localhost:8123 and is signed in in the in-app Browser. Test Medication
   > Reminder end to end. You may create and delete test data and restart only the
   > hass-medreminder-test container. Do not access my production instance.

No long-lived token is needed when the Browser is already signed in. Never paste a
production token into chat or commit it. If API-only testing is required, create a
test-only Home Assistant user, store its temporary token in an ignored `.env.test`
file, and revoke it after testing.

## 4. Enable notification testing

For a real action-button test, connect a Companion App to the test instance so a
`notify.mobile_app_*` action is available. Use a spare/test device if possible. A
configured script can verify reminder script execution, but it cannot prove that a
phone renders and returns notification actions correctly.

## 5. End-to-end checklist

- Switch the Home Assistant user language between English and German; reload and
  verify panel, setup flow, entities, actions, and notifications.
- Select and copy text in every modal; confirm it stays open. Close only with the X
  or Cancel button.
- Keep each form open for more than 30 seconds while typing and trigger a validation
  error; confirm no entered field or text selection is reset.
- Create a medication with all optional metadata. Confirm there is no current-stock
  field and that step 2 opens automatically for the first package.
- Cancel step 2 and confirm stock is zero. Add a package and confirm stock equals
  the sum of its package remainders and cannot be edited directly.
- Add multiple packages with different expiry dates and LOT numbers. Verify that
  stock is their sum, nicknames are unique, and the earliest expiry is recommended.
- Record a dose larger than the first package remainder. Verify a split across the
  two earliest packages and matching immutable allocation details in history.
- Record an unplanned multi-medication intake and verify atomic stock deduction.
- Create a weekday/weekend schedule and an every-x-days schedule.
- Move a due every-x-days intake to tomorrow and verify both its ticket and all
  following cycle dates shift, while weekly schedules reject this action.
- Trigger a due intake with multiple medications and verify repeated reminders.
- Record all doses, a partial selection, and the remaining selection later.
- Verify 30/60/120-minute and custom-time snooze, then wait or move the test time
  forward and confirm reminders resume.
- Skip an intake and confirm stock remains unchanged.
- Reuse an old notification action and confirm stock is not deducted twice.
- Generate medication, package, and intake QR codes. Verify that each scanned
  payload is exactly `med` plus five unambiguous letters/digits and contains no URL.
- Export a one-day and multi-day history range as JSON and CSV. Verify inclusive
  boundaries, nested package allocations in JSON, one CSV row per dose, UTF-8 text,
  and that open tickets are excluded.
- Download a full backup, create a recognizable change, and restore the backup.
  Verify medication/package stock, schedules, open tickets, history, and scan codes.
  Reject malformed and newer unsupported backup versions without changing live data.
- Restart Home Assistant with open, snoozed, and completed tickets; verify storage,
  due generation, package allocation snapshots, and history.
- Upgrade data containing legacy manual stock and verify it becomes a `Legacy`
  package with the same remaining quantity.
- Check global, medication, and package entities, action schemas, events, desktop
  layout, and a narrow mobile viewport.
- Enter a wrong delete confirmation and verify nothing changes. Then use `DELETE`,
  verify every domain record is removed, and confirm the integration remains installed.

The physical delivery and rendering of a Companion App notification is the only
step that requires a real device and human confirmation. Codex can verify the
generated payload, Home Assistant event handling, and all browser-visible behavior.

## Continuous integration and releases

Two workflows live in `.github/workflows`.

**`validate.yml`** runs on every push and pull request, and once a week so that
changes in Home Assistant or HACS surface before they reach an installation. It
runs the unit tests, byte-compiles the integration, syntax-checks the frontend
modules, runs `ruff`, and runs the official `hassfest` and HACS validators.

The HACS job needs two things set on the GitHub repository itself, otherwise it
fails: a **description** and at least one **topic**. Both are set under the gear
icon next to *About* on the repository page. The `brands` check is skipped,
because it only applies to integrations that want to join the HACS default list,
which requires a pull request against `home-assistant/brands`.

**`release.yml`** publishes a release whenever the version in
`custom_components/medication_reminder/manifest.json` changes on `main`. HACS
offers whatever the newest GitHub release points at, so this is the step that
actually ships an update to installations.

Cutting a release therefore means one thing:

1. Bump `version` in `manifest.json` **and** `FRONTEND_CACHE_KEY` in `const.py`
   to the same value. The workflow refuses to release when they differ, because
   browsers would keep serving the cached panel and card.
2. Push to `main`.

The workflow then re-runs the tests and `hassfest`, creates the tag, and
publishes a release with generated notes plus a `medication_reminder.zip` for
manual installation. HACS itself reads the files from the tag and ignores that
asset. Publishing the same version twice is a no-op, so the workflow is safe to
re-run.

## Switching the language for screenshots

The panel and the card follow Home Assistant's language, which makes capturing
both languages awkward. A temporary override solves that without touching the
setting of the whole installation.

In the browser console, on any page that shows the panel or the card:

```js
medicationReminder.setLanguage("en")   // switch immediately
medicationReminder.setLanguage("de")
medicationReminder.resetLanguage()     // follow Home Assistant again
medicationReminder.languages           // ["en", "de"]
```

Every mounted panel and card re-renders at once, so no reload is needed. The
override lives in `sessionStorage`, which means it survives a reload of the tab
and disappears when the tab is closed. It never reaches the server, so nobody
else's session is affected.

The panel also accepts `?lang=` in its URL, which is handy for scripted
captures:

```
/medication_reminder?lang=en
```

A language in the URL wins over one set in the console.

The override only covers the panel and the card. Entity names, action
descriptions and the text of a reminder notification come from Home Assistant
and follow its own language setting.

## Regenerating the screenshots

The images in the readme come from `docs/screenshot/harness.html`, a standalone
page that feeds the real panel and card modules a fixed set of demo data. No
Home Assistant instance is involved, so a capture needs no onboarding, no
database and no account, and it always renders the same pixels: the browser
clock is pinned to the reference time in `docs/screenshot/fixture.js`.

```shell
npm install --no-save playwright@1.63.0
npx playwright install chromium
node scripts/capture-screenshots.mjs
```

This writes `docs/screenshots/*.png` for both languages, plus a dark variant of
the overview and the card. The run fails when the frontend logs an error or when
an asset such as the logo does not load, so a broken image cannot reach the
readme unnoticed.

The `Screenshots` workflow does the same on every push that touches the frontend
and commits the result when it differs. Because a different browser build
renders text slightly differently, the workflow pins the Playwright version;
images generated on another operating system will differ marginally until that
workflow regenerates them.

Icons are vendored into `docs/screenshot/icons.js` so the capture needs no icon
package. After adding an `mdi:` icon to the panel or the card, refresh them:

```shell
npm install --no-save @mdi/js
node scripts/generate-icons.mjs
```

That script fails on an icon name that Material Design Icons does not know,
which is worth running after any icon change: an unknown name renders as an
empty box in Home Assistant without any error.
