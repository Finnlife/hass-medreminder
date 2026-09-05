# Testanleitung

Diese Anleitung erstellt eine wegwerfbare Home-Assistant-Instanz, die Codex
untersuchen, neu starten und verändern darf, ohne Produktivdaten zu berühren.

## 1. Automatisierte Prüfungen

Python 3 und Node.js installieren und im Repository-Stamm ausführen:

```shell
pip install -r <(python -c "import json;print(chr(10).join(json.load(open('custom_components/medication_reminder/manifest.json'))['requirements']))")
python -m unittest discover -s tests -v
python -m compileall custom_components/medication_reminder tests
node --check custom_components/medication_reminder/frontend/localize.js
node --check custom_components/medication_reminder/frontend/medication-reminder-panel.js
```

Mit installiertem Docker lässt sich zusätzlich Home Assistants Validator starten:

```shell
docker run --rm -v "${PWD}:/github/workspace" ghcr.io/home-assistant/hassfest
```

## 2. Isoliertes Home Assistant starten

Docker Desktop installieren, Port 8123 freihalten und ausführen:

```shell
docker compose -f compose.test.yaml up -d
docker compose -f compose.test.yaml logs -f homeassistant
```

`http://localhost:8123` öffnen, das Onboarding mit einem reinen Testkonto
abschließen und **Medication Reminder** unter **Einstellungen → Geräte & Dienste**
hinzufügen. `.ha-test` wird von Git ignoriert und kann später gelöscht werden.

Nach Änderungen am Quellcode die Testinstanz neu starten:

```shell
docker compose -f compose.test.yaml restart homeassistant
```

## 3. Codex für den vollständigen Test freigeben

1. `http://localhost:8123` im eingebauten Browser von Codex öffnen.
2. Dort selbst mit dem reinen Home-Assistant-Testkonto anmelden und den Tab offen lassen.
3. Dieses Repository als Codex-Workspace geöffnet lassen.
4. Codex ausdrücklich erlauben, nur diese Testinstanz zu bedienen und neu zu starten.
5. Folgenden Auftrag senden:

   > Die isolierte Home-Assistant-Testinstanz läuft unter
   > http://localhost:8123 und ist im eingebauten Browser angemeldet. Teste
   > Medication Reminder vollständig Ende-zu-Ende. Du darfst Testdaten anlegen und
   > löschen und nur den Container hass-medreminder-test neu starten. Greife nicht
   > auf meine Produktivinstanz zu.

Bei bereits angemeldetem Browser ist kein Token nötig. Niemals ein Produktivtoken
in den Chat einfügen oder committen. Falls ein API-Test unumgänglich ist: eigenes
Testkonto anlegen, dessen temporären Token nur in der ignorierten `.env.test`
speichern und anschließend widerrufen.

## 4. Benachrichtigungen testen

Für echte Aktionsbuttons muss eine Companion App mit der Testinstanz verbunden
sein, sodass `notify.mobile_app_*` verfügbar ist. Möglichst ein Testgerät verwenden.
Ein Script kann die Ausführung des Reminder-Scripts bestätigen, aber nicht die
Darstellung und Rückmeldung einer echten Smartphone-Notification.

## 5. Ende-zu-Ende-Checkliste

- Sprache des Home-Assistant-Benutzers zwischen Englisch und Deutsch wechseln;
  Panel, Setup, Entitäten, Aktionen und Benachrichtigungen prüfen.
- In jedem Dialog Text markieren und kopieren; er muss offen bleiben. Nur X und
  Abbrechen dürfen ihn schließen.
- Jedes Formular länger als 30 Sekunden während der Eingabe offen lassen und einen
  Validierungsfehler auslösen; kein Feld und keine Textauswahl darf zurückgesetzt werden.
- Ein Medikament mit allen optionalen Angaben anlegen. Es darf kein Feld für den
  aktuellen Bestand geben; Schritt 2 für die erste Packung muss direkt erscheinen.
- Schritt 2 abbrechen und Bestand null prüfen. Eine Packung anlegen und prüfen, dass
  der Bestand ihrer Restsumme entspricht und nicht direkt bearbeitet werden kann.
- Mehrere Packungen mit verschiedenen MHDs und LOT-Nummern anlegen. Summe,
  eindeutige Spitznamen und Empfehlung der Packung mit nächstem MHD prüfen.
- Eine Dosis erfassen, die größer als der Rest der ersten Packung ist. Die Aufteilung
  auf die zwei ältesten Packungen und unveränderliche Details im Verlauf prüfen.
- Eine ungeplante Mehrfach-Einnahme erfassen und atomare Bestandsabbuchung prüfen.
- Wochenplan mit Werktag/Wochenende und Plan alle x Tage anlegen.
- Eine fällige Alle-x-Tage-Einnahme auf morgen verschieben. Ticket und alle folgenden
  Termine müssen wandern; ein Wochenplan muss diese Aktion ablehnen.
- Fällige Einnahme mit mehreren Medikamenten und Wiederholungen auslösen.
- Alles, eine Teilauswahl und später die Restmenge erfassen.
- 30/60/120 Minuten und freie Uhrzeit schlummern; Wiederbeginn prüfen.
- Einnahme auslassen und unveränderten Bestand prüfen.
- Alte Notification-Aktion erneut auslösen; keine doppelte Abbuchung zulassen.
- QR-Codes für Medikament, Packung und Einnahme erzeugen und scannen. Jede Nutzlast
  muss exakt aus `med` plus fünf eindeutigen Buchstaben/Ziffern bestehen und darf
  keine URL enthalten.
- Einen ein- und mehrtägigen Zeitraum als JSON und CSV exportieren. Inklusive
  Grenzen, verschachtelte Packungsdaten im JSON, eine CSV-Zeile je Dosis, UTF-8 und
  den Ausschluss offener Tickets prüfen.
- Ein Vollbackup herunterladen, eine erkennbare Änderung vornehmen und das Backup
  wiederherstellen. Medikamente/Packungsbestand, Pläne, offene Tickets, Verlauf und
  Scan-Codes prüfen. Fehlerhafte und neuere Backupversionen müssen ohne Änderung der
  Live-Daten abgelehnt werden.
- Home Assistant mit offenen, schlummernden und erledigten Tickets neu starten;
  Persistenz, Nacherzeugung, Packungs-Snapshots und Verlauf prüfen.
- Daten mit altem manuellem Bestand aktualisieren und prüfen, dass eine `Legacy`-
  Packung mit derselben Restmenge entsteht.
- Globale, Medikamenten- und Packungsentitäten, Aktionsschemata, Events sowie
  Desktop- und Mobilansicht prüfen.
- Eine falsche Löschbestätigung eingeben und unveränderte Daten prüfen. Danach mit
  `DELETE` alle Domänendaten löschen; die Integration muss installiert bleiben.

Nur Zustellung und Darstellung einer Companion-App-Benachrichtigung benötigen ein
echtes Gerät und menschliche Bestätigung. Payload, Events und Browser-Verhalten
kann Codex vollständig prüfen.

## Continuous Integration und Releases

In `.github/workflows` liegen zwei Workflows.

**`validate.yml`** läuft bei jedem Push und Pull Request sowie einmal wöchentlich,
damit Änderungen in Home Assistant oder HACS auffallen, bevor sie eine
Installation erreichen. Er führt die Unit-Tests aus, kompiliert die Integration,
prüft die Frontend-Module syntaktisch, lässt `ruff` laufen und ruft die
offiziellen Validatoren `hassfest` und HACS auf.

Der HACS-Job braucht zwei Angaben am GitHub-Repository selbst, sonst schlägt er
fehl: eine **Beschreibung** und mindestens ein **Topic**. Beides wird über das
Zahnrad neben *About* auf der Repository-Seite gesetzt. Die `brands`-Prüfung ist
abgeschaltet, weil sie nur für Integrationen gilt, die in die HACS-Standardliste
wollen — dafür braucht es einen Pull Request gegen `home-assistant/brands`.

**`release.yml`** veröffentlicht ein Release, sobald sich die Version in
`custom_components/medication_reminder/manifest.json` auf `main` ändert. HACS
bietet immer das an, worauf das neueste GitHub-Release zeigt; dieser Schritt
liefert das Update also tatsächlich aus.

Ein Release zu schneiden heißt damit:

1. `version` in `manifest.json` **und** `FRONTEND_CACHE_KEY` in `const.py` auf
   denselben Wert setzen. Der Workflow verweigert das Release, wenn beide
   auseinanderlaufen, weil Browser sonst weiter Panel und Karte aus dem Cache
   ausliefern.
2. Die Änderung in `CHANGELOG.md` unter einer Überschrift `## <version>`
   beschreiben, auf Englisch. Die Release-Notes stammen aus diesem Abschnitt,
   das ist also der Text, den ein Update in HACS zeigt. Ohne Abschnitt wird das
   Release verweigert, und die Testsuite schlägt schon fehl, sobald das Manifest
   eine Version nennt, die der Changelog nicht beschreibt.
3. Nach `main` pushen.

Der Workflow führt danach Tests und `hassfest` erneut aus, legt das Tag an und
veröffentlicht ein Release mit generierten Notizen sowie einer
`medication_reminder.zip` für die manuelle Installation. HACS selbst liest die
Dateien aus dem Tag und ignoriert dieses Asset. Dieselbe Version zweimal zu
veröffentlichen ist wirkungslos, der Workflow kann also gefahrlos erneut laufen.

## Sprache für Screenshots umschalten

Panel und Karte folgen der Sprache von Home Assistant, was das Aufnehmen beider
Sprachen umständlich macht. Eine temporäre Übersteuerung löst das, ohne die
Einstellung der ganzen Installation anzufassen.

In der Browser-Konsole, auf jeder Seite mit Panel oder Karte:

```js
medicationReminder.setLanguage("en")   // sofort umschalten
medicationReminder.setLanguage("de")
medicationReminder.resetLanguage()     // wieder Home Assistant folgen
medicationReminder.languages           // ["en", "de"]
```

Alle eingehängten Panels und Karten rendern sofort neu, ein Reload ist nicht
nötig. Die Übersteuerung liegt im `sessionStorage`, überlebt also ein Neuladen
des Tabs und verschwindet beim Schließen. Sie erreicht den Server nie, fremde
Sitzungen bleiben unberührt.

Das Panel akzeptiert zusätzlich `?lang=` in der URL, praktisch für
skriptgesteuerte Aufnahmen:

```
/medication_reminder?lang=de
```

Eine Sprache in der URL sticht die in der Konsole gesetzte.

Die Übersteuerung betrifft nur Panel und Karte. Entitätsnamen,
Aktionsbeschreibungen und der Text einer Erinnerungs-Benachrichtigung kommen aus
Home Assistant und folgen dessen Spracheinstellung.

## Screenshots neu erzeugen

Die Bilder in der README stammen aus `docs/screenshot/harness.html`, einer
eigenständigen Seite, die den echten Panel- und Karten-Modulen feste Demodaten
unterschiebt. Es ist keine Home-Assistant-Instanz beteiligt, eine Aufnahme
braucht also weder Onboarding noch Datenbank noch Konto — und sie rendert immer
dieselben Pixel, weil die Browser-Uhr auf den Referenzzeitpunkt in
`docs/screenshot/fixture.js` festgenagelt wird.

```shell
npm install --no-save playwright@1.63.0
npx playwright install chromium
node scripts/capture-screenshots.mjs
```

Das schreibt `docs/screenshots/*.png` für beide Sprachen, dazu eine dunkle
Variante von Überblick und Karte. Der Lauf schlägt fehl, wenn das Frontend einen
Fehler protokolliert oder ein Asset wie das Logo nicht lädt — ein kaputtes Bild
schafft es also nicht unbemerkt in die README.

Der Workflow `Screenshots` macht dasselbe bei jedem Push, der das Frontend
berührt, und committet das Ergebnis, wenn es sich unterscheidet. Da ein anderer
Browser-Build Text minimal anders rendert, ist die Playwright-Version gepinnt;
auf einem anderen Betriebssystem erzeugte Bilder weichen leicht ab, bis dieser
Workflow sie neu erzeugt.

Die Icons liegen als Pfaddaten in `docs/screenshot/icons.js`, damit die Aufnahme
ohne Icon-Paket auskommt. Nach dem Hinzufügen eines `mdi:`-Icons in Panel oder
Karte neu erzeugen:

```shell
npm install --no-save @mdi/js
node scripts/generate-icons.mjs
```

Das Skript bricht bei einem Icon-Namen ab, den Material Design Icons nicht
kennt. Das lohnt sich nach jeder Icon-Änderung: ein unbekannter Name rendert in
Home Assistant als leeres Kästchen, ganz ohne Fehlermeldung.

## Das Marken-Icon

Home Assistant zeigt ein Icon für die Integration in HACS, auf der
Integrationsseite und an ihren Geräten. Seit Home Assistant 2026.3 kann eine
Custom Integration dieses Icon selbst mitliefern, in einem `brand/`-Verzeichnis;
ein lokales Bild hat Vorrang vor dem Brands-CDN. Ein Pull Request gegen
`home-assistant/brands` ist nicht nötig.

In `custom_components/medication_reminder/brand/` liegen deshalb `icon.png`
(256x256) und `icon@2x.png` (512x512), abgeleitet aus dem Panel-Logo. Home
Assistant greift überall dort auf das Icon zurück, wo sonst ein Logo stünde —
eine eigene `logo.png` würde die quadratische Grafik nur verdoppeln.

Nach einer Änderung am Logo neu erzeugen:

```shell
python scripts/generate-brand-icons.py
```

Das Skript schneidet den transparenten Rand weg, füllt die Grafik zu einem
Quadrat auf statt sie zu verzerren, und schreibt beide geforderten Größen.

Ältere Home-Assistant-Versionen lesen das Icon weiterhin aus dem Brands-CDN, wo
es unter `custom_integrations/medication_reminder/` eingetragen werden müsste.
