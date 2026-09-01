# Medication Reminder für Home Assistant

<img src="custom_components/medication_reminder/frontend/logo.png" alt="Medication-Reminder-Logo" width="160">

[English](README.md)

Eine lokale Home-Assistant-Custom-Integration für Medikamentenpläne, Bestände,
interaktive Erinnerungen und ein nachvollziehbares Soll-/Ist-Protokoll. Nach der
Einrichtung erscheint **Medications** als eigener Sidebar-Eintrag; der Inhalt wird
bei deutscher Home-Assistant-Sprache vollständig deutsch dargestellt.

## Implementierte Funktionen (v0.4.1)

- Medikamente mit Hersteller, Barcode/PZN, Wirkstärke, Darreichungsform,
  Bestandseinheit, Warnschwelle und Notizen; nach dem Anlegen öffnet sich direkt
  Schritt 2 für die erste physische Packung
- Wochenpläne mit eigener Uhrzeit je Wochentag und mehreren Uhrzeiten pro Tag
- Intervallpläne alle x Tage ab einem frei wählbaren Startdatum
- Eine fällige Intervall-Einnahme auf morgen verschieben und damit den gesamten
  zukünftigen Zyklus versetzen
- Mehrere Medikamente und individuelle Dosen pro Einnahme
- Ungeplante Einnahmen mit denselben Bestands- und Protokollgarantien
- Wiederholte Erinnerungen über ausgewählte `notify.*`-Dienste und Scripts
- Mobile Aktionen: alles genommen, 30 Minuten schlummern oder Details öffnen
- Teil-Einnahmen, 30/60/120 Minuten und freie Uhrzeit zum Schlummern sowie Auslassen
- Persistente Tickets, Soll-/Ist-Verlauf und Bestandsabbuchung erst bei Einnahme
- Zeitraum-Export des Verlaufs im Tab **Verlauf** als verschachteltes JSON oder CSV
  mit einer Zeile je Medikamentendosis inklusive Packungs-Snapshots
- Physische Packungen mit MHD, LOT/Charge, aufgedrucktem Code und automatisch
  wählbarem, eindeutigem Spitznamen
- Automatisch aus Packungen berechneter Bestand, FEFO-Empfehlung nach nächstem MHD
  und Aufteilung einer Dosis auf mehrere Packungen
- Lokal erzeugte, kontrastreiche QR-Codes für Medikamente, Packungen und offene
  Einnahmen; der Generator akzeptiert ausschließlich stabile achtstellige Kennungen
  wie `med7K2QF`, niemals eine URL oder Medikamentendaten
- Sensoren, Binärsensoren, Events und Aktionen für Dashboards und Automationen
- Englisch als Entwicklungssprache und Standard, Deutsch als vollständige Übersetzung

## Aktuelle Einschränkungen / noch nicht umgesetzt

- Im Panel gibt es noch keinen Kamera-Scanner und keine Auflösung gescannter Codes.
  QR-Codes können gedruckt und als Text gescannt werden, öffnen aber noch keine
  Packung und protokollieren keine Einnahme automatisch.
- Barcode- und DataMatrix-Werte werden nur als Metadaten gespeichert. Erzeugt werden
  derzeit QR-Codes, keine druckbaren 1D-Barcodes oder DataMatrix-Symbole.
- Eine mobile Notification kann die komplette Einnahme bestätigen oder 30 Minuten
  schlummern. Einzelne Medikamente sowie 60/120 Minuten oder eine freie Uhrzeit sind
  nach dem Öffnen der App auswählbar, nicht direkt in der Notification.
- MHDs werden gespeichert und für FEFO verwendet. Eigene MHD-/Rückrufwarnungen,
  Bestandsprognosen und Nachbestellprozesse fehlen noch.
- Entitätsnamen und Entity-IDs werden in den nativen Home-Assistant-Einstellungen
  bearbeitet; das Medication-Reminder-Panel besitzt keinen eigenen Entity-Editor.
- Der Export umfasst aktuell nur den gespeicherten abgeschlossenen/ausgelassenen
  Einnahmeverlauf. Vollbackup/-import und Export offener oder zukünftiger Tickets fehlen.
- Getrennte Patientenprofile, Cloud-Synchronisierung, Medizingeräte-Anbindungen und
  Wechselwirkungsprüfungen sind nicht vorhanden.

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

## Home-Assistant-Schnittstellen

Globale Entitäten bilden nächste, offene, letzte und überfällige Einnahmen ab.
Jedes Medikament erzeugt zusätzlich einen Bestands-Sensor und einen
Low-Stock-Binärsensor. Jede physische Packung erhält einen eigenen Bestands-Sensor
mit LOT, MHD, Anfangsmenge und aufgedrucktem Code als Attribute. Die endgültigen
Entity-IDs vergibt Home Assistant.

Aktionen: `medication_reminder.record_intake`, `medication_reminder.snooze`,
`medication_reminder.add_package`,
`medication_reminder.record_unplanned_intake` und
`medication_reminder.postpone_interval` sowie
`medication_reminder.delete_all_data` (benötigt `confirmation: DELETE`).

Events: `medication_reminder_due`, `medication_reminder_taken`,
`medication_reminder_skipped`, `medication_reminder_low_stock` und
`medication_reminder_postponed`.

## Verlauf exportieren

Im Tab **Verlauf** einen inklusiven Zeitraum von **Von** bis **Bis** auswählen und
JSON oder CSV herunterladen. Wenn vorhanden, zählt der tatsächliche
Erfassungszeitpunkt, sonst der geplante Zeitpunkt. JSON enthält Vorgänge, Dosen und
Packungszuordnungen verschachtelt. CSV schreibt je Medikamentendosis eine Zeile und
legt Packungszuordnungen als JSON in der letzten Spalte ab. Exportiert wird nur der
gespeicherte abgeschlossene und ausgelassene Verlauf; offene Tickets und Stammdaten
sind nicht Teil dieses Exports.

## Speicherung und Verhalten

Alle Daten bleiben lokal unter `.storage/medication_reminder.data`. Alte mobile
Aktionen sind idempotent und buchen Bestand nicht doppelt ab. Bis zu 2.000
abgeschlossene Vorgänge werden gespeichert; offene Vorgänge bleiben erhalten.
Über den Papierkorb im Panel-Header lassen sich nach einer zweiten Bestätigung mit
`DELETE` sämtliche Medication-Reminder-Daten dauerhaft löschen. Die Integration
selbst bleibt installiert. Dieselbe serverseitige Bestätigung gilt für die
Home-Assistant-Aktion.
Das Speicherschema ist versioniert; die aktuelle Migration überführt vorhandenen
manuellen Bestand verlustfrei in eine physische `Legacy`-Packung. Der Bestand wird
danach immer aus den Restmengen der Packungen berechnet, ohne die Einnahmehistorie
umzuschreiben. Das Projekt
ist weiterhin vor Version 1.0. Vor 0.x-Updates sollte deshalb eine Sicherung von
`.storage/medication_reminder.data` erstellt werden; der dauerhafte
Kompatibilitätsvertrag gilt erst ab Version 1.0.

## Entwicklung und vollständiger Test

Die genaue Anleitung für automatisierte Checks, eine isolierte Docker-Instanz und
die Übergabe an Codex steht in [docs/TESTING.de.md](docs/TESTING.de.md).
