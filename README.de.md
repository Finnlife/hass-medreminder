# Medication Reminder für Home Assistant

[English](README.md)

Eine lokale Home-Assistant-Custom-Integration für Medikamentenpläne, Bestände,
interaktive Erinnerungen und ein nachvollziehbares Soll-/Ist-Protokoll. Nach der
Einrichtung erscheint **Medications** als eigener Sidebar-Eintrag; der Inhalt wird
bei deutscher Home-Assistant-Sprache vollständig deutsch dargestellt.

## Funktionen

- Medikamente mit Hersteller, Barcode/PZN, Wirkstärke, Darreichungsform,
  Bestandseinheit, Bestand, Warnschwelle und Notizen
- Wochenpläne mit eigener Uhrzeit je Wochentag und mehreren Uhrzeiten pro Tag
- Intervallpläne alle x Tage ab einem frei wählbaren Startdatum
- Mehrere Medikamente und individuelle Dosen pro Einnahme
- Wiederholte Erinnerungen über ausgewählte `notify.*`-Dienste und Scripts
- Mobile Aktionen: alles genommen, 30 Minuten schlummern oder Details öffnen
- Teil-Einnahmen, 30/60/120 Minuten und freie Uhrzeit zum Schlummern sowie Auslassen
- Persistente Tickets, Soll-/Ist-Verlauf und Bestandsabbuchung erst bei Einnahme
- Sensoren, Binärsensoren, Events und Aktionen für Dashboards und Automationen
- Englisch als Entwicklungssprache und Standard, Deutsch als vollständige Übersetzung

## Installation

### Als benutzerdefiniertes HACS-Repository

1. In HACS **Integrationen**, das Drei-Punkte-Menü und **Benutzerdefinierte
   Repositories** öffnen.
2. `https://github.com/Finnlife/hass-medreminder` als Typ **Integration** hinzufügen.
3. **Medication Reminder** herunterladen und Home Assistant neu starten.
4. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach
   **Medication Reminder** suchen und die Integration einmal hinzufügen.
5. Den neuen Sidebar-Eintrag **Medications** öffnen.

Alternativ `custom_components/medication_reminder` in das gleichnamige Verzeichnis
der Home-Assistant-Konfiguration kopieren und Home Assistant neu starten.

Aktionsbuttons benötigen einen kompatiblen Benachrichtigungsdienst, beispielsweise
`notify.mobile_app_*` der Companion App. Andere Dienste können die Nachricht ohne
Buttons anzeigen.

## Schnittstellen und Speicherung

Globale Entitäten bilden nächste, offene, letzte und überfällige Einnahmen ab.
Jedes Medikament erzeugt zusätzlich einen Bestands-Sensor und einen
Low-Stock-Binärsensor. Die endgültigen Entity-IDs vergibt Home Assistant.

Aktionen: `medication_reminder.record_intake`, `medication_reminder.snooze` und
`medication_reminder.adjust_stock`.

Events: `medication_reminder_due`, `medication_reminder_taken`,
`medication_reminder_skipped` und `medication_reminder_low_stock`.

Alle Daten bleiben lokal unter `.storage/medication_reminder.data`. Alte mobile
Aktionen sind idempotent und buchen Bestand nicht doppelt ab. Bis zu 2.000
abgeschlossene Vorgänge werden gespeichert; offene Vorgänge bleiben erhalten.

## Entwicklung und vollständiger Test

Die genaue Anleitung für automatisierte Checks, eine isolierte Docker-Instanz und
die Übergabe an Codex steht in [docs/TESTING.de.md](docs/TESTING.de.md).
