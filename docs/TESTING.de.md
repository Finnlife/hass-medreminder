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

Ein Release zu schneiden heißt damit nur:

1. `version` in `manifest.json` **und** `FRONTEND_CACHE_KEY` in `const.py` auf
   denselben Wert setzen. Der Workflow verweigert das Release, wenn beide
   auseinanderlaufen, weil Browser sonst weiter Panel und Karte aus dem Cache
   ausliefern.
2. Nach `main` pushen.

Der Workflow führt danach Tests und `hassfest` erneut aus, legt das Tag an und
veröffentlicht ein Release mit generierten Notizen sowie einer
`medication_reminder.zip` für die manuelle Installation. HACS selbst liest die
Dateien aus dem Tag und ignoriert dieses Asset. Dieselbe Version zweimal zu
veröffentlichen ist wirkungslos, der Workflow kann also gefahrlos erneut laufen.
