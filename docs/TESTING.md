# Testing guide

This guide creates a disposable Home Assistant instance that Codex can inspect,
restart, and test without touching production data.

## 1. Run the automated checks

Install Python 3 and Node.js, then run from the repository root:

```shell
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
- Create, edit, and delete medications with all optional metadata.
- Adjust stock positively and negatively; reject negative resulting stock.
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
- Generate and scan medication, package, and intake QR codes. Verify highlighting,
  navigation, and that an intake scan never deducts stock without confirmation.
- Restart Home Assistant with open, snoozed, and completed tickets; verify storage,
  due generation, package allocation snapshots, and history.
- Check global, medication, and package entities, action schemas, events, desktop
  layout, and a narrow mobile viewport.

The physical delivery and rendering of a Companion App notification is the only
step that requires a real device and human confirmation. Codex can verify the
generated payload, Home Assistant event handling, and all browser-visible behavior.
