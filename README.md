# Medication Reminder für Home Assistant

Eine lokale Home-Assistant-Custom-Integration für Medikamentenpläne, Bestände,
mobile Erinnerungen und ein nachvollziehbares Soll-/Ist-Protokoll. Nach der
Einrichtung erscheint **Medikamente** als eigener Eintrag in der Sidebar.

## Funktionen

- Medikamente mit Hersteller, Barcode/PZN, Wirkstärke, Darreichungsform,
  Bestandseinheit, Bestand, Warnschwelle und Notizen
- Wochenpläne mit eigener Uhrzeit je Wochentag und mehreren Uhrzeiten pro Tag
- Intervallpläne alle x Tage ab einem frei wählbaren Startdatum
- Mehrere Medikamente und individuelle Dosen pro Einnahme
- Wiederholte Erinnerungen über ausgewählte `notify.*`-Dienste und Scripts
- Mobile Aktionen: alles genommen, 30 Minuten schlummern oder App öffnen
- In der App: Teil-Einnahmen, 30/60/120 Minuten oder bis zu einer freien Uhrzeit
  schlummern und Einnahmen auslassen
- Persistente offene Einnahme-Tickets und Verlauf mit Soll-/Ist-Zeit
- Bestandsabbuchung erst bei einer tatsächlich erfassten Dosis
- Sensoren, Binärsensoren, Events und Dienste für eigene Dashboards und Automationen

## Installation

1. Den Ordner `custom_components/medication_reminder` in das gleichnamige
   Verzeichnis deiner Home-Assistant-Konfiguration kopieren.
2. Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach
   **Medication Reminder** suchen und die Integration einmal hinzufügen.
4. Die neue Seite **Medikamente** in der Sidebar öffnen.

Für Action-Buttons wird ein Benachrichtigungsdienst der Home-Assistant-Companion-App
benötigt, beispielsweise `notify.mobile_app_mein_handy`. Andere Notify-Dienste
erhalten die Nachricht, ignorieren aber möglicherweise die Buttons.

## Home-Assistant-Schnittstellen

Globale Entitäten:

- `sensor.medikamentenplan_nachste_einnahme`
- `sensor.medikamentenplan_offene_einnahmen`
- `sensor.medikamentenplan_letzte_einnahme`
- `binary_sensor.medikamentenplan_einnahme_uberfallig`

Für jedes Medikament entstehen ein Bestands-Sensor und ein Low-Stock-Binärsensor.
Die endgültigen Entity-IDs werden von Home Assistant vergeben und können in der
Geräteansicht angepasst werden.

Dienste:

- `medication_reminder.record_intake`
- `medication_reminder.snooze`
- `medication_reminder.adjust_stock`

Events:

- `medication_reminder_due`
- `medication_reminder_taken`
- `medication_reminder_skipped`
- `medication_reminder_low_stock`

## Datenspeicherung und Verhalten

Alle Daten liegen lokal im Home-Assistant-Storage unter
`.storage/medication_reminder.data`. Bei einem Neustart werden seit dem letzten
Lauf verpasste Soll-Zeitpunkte bis maximal 30 Tage nacherzeugt. Ein Vorgang wird
idempotent verarbeitet: Ein erneuter Klick auf eine bereits abgeschlossene mobile
Aktion bucht keinen Bestand doppelt ab. Die letzten 2.000 abgeschlossenen Vorgänge
bleiben erhalten; offene Vorgänge werden nie automatisch entfernt.

## Entwicklung und Prüfung

```bash
python -m unittest discover -s tests -v
python -m compileall custom_components/medication_reminder
node --check custom_components/medication_reminder/frontend/medication-reminder-panel.js
```

Für eine vollständige Integration-Prüfung empfiehlt sich zusätzlich eine aktuelle
Home-Assistant-Entwicklungsumgebung mit `pytest-homeassistant-custom-component`.

