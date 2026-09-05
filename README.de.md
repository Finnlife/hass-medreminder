# Medication Reminder für Home Assistant

<img src="https://raw.githubusercontent.com/Finnlife/hass-medreminder/main/custom_components/medication_reminder/frontend/logo.png" alt="Medication-Reminder-Logo" width="160">

[English](https://github.com/Finnlife/hass-medreminder/blob/main/README.md)

> [!CAUTION]
> **Verlasse dich bei echten Medikamenten nicht auf dieses Projekt.**
>
> Das hier ist ein Hobbyprojekt. Es ist zu einem Zweck entstanden: den Autor daran
> zu erinnern, seine Vitamine zu nehmen. Es ist **kein** Medizinprodukt, es ist
> nicht zertifiziert, nicht validiert, von niemandem geprüft und kommt ohne
> jegliche Gewährleistung.
>
> Erinnerungen können ausbleiben, ohne dass es jemand merkt, und der aufgezeichnete
> Verlauf kann falsch oder unvollständig sein. Ein Neustart von Home Assistant, ein
> Update, ein ausgefallener Benachrichtigungsdienst, ein Handy im Nicht-stören-Modus,
> ein leerer Akku, ein Fehler in diesem Code oder ein Fehler in deiner eigenen
> Konfiguration reichen jeweils aus, damit eine Dosis spurlos verschwindet.
>
> Wenn du verschreibungspflichtige Medikamente nimmst oder überhaupt Medikamente,
> bei denen eine vergessene, doppelte oder falsch getimte Dosis eine Rolle spielt,
> nutze dieses Projekt **niemals** als einzige Erinnerung und niemals als einzigen
> Einnahmenachweis. Behalte deine Tablettenbox, dein Papierprotokoll, deine
> Apotheken-App oder was auch immer Arzt oder Apotheke dir empfehlen, und betrachte
> alles hier nur als Komfort obendrauf. Bei Fragen zu deiner Medikation wende dich
> an Arzt oder Apotheke, nicht an diese README.

Eine lokale Home-Assistant-Custom-Integration für Medikamentenpläne, Bestände,
interaktive Erinnerungen und ein nachvollziehbares Soll-/Ist-Protokoll. Nach der
Einrichtung erscheint **Medications** als eigener Sidebar-Eintrag; der Inhalt wird
bei deutscher Home-Assistant-Sprache vollständig deutsch dargestellt.

## Wie dieses Projekt entstanden ist

Große Teile dieses Projekts sind mit KI-Unterstützung entstanden. Die Integrations-
und Frontend-Schnittstellen von Home Assistant waren für den Autor neu; KI wurde
genutzt, um sie zu lernen und einen Großteil des Codes zu schreiben. Alles wird vor
dem Einchecken geprüft und getestet, aber das gehört zur Einschätzung dazu, wie
sehr man diesem Code vertrauen sollte — lies ihn selbst, bevor du ihn auf einer
Instanz laufen lässt, die dir wichtig ist, und beachte den Warnhinweis oben zu
echten Medikamenten.

## Implementierte Funktionen (v0.7.6)

- Medikamentenstammdaten mit Hersteller, Barcode/Produktcode, Stärke,
  Darreichungsform, Bestandseinheit, Warnschwelle und Notizen; nach dem Anlegen
  öffnet direkt ein zweiter Schritt für die erste physische Packung
- Wochenpläne mit unterschiedlichen Zeiten je Wochentag und mehreren Zeiten pro Tag
- Intervallpläne alle x Tage ab einem gewählten Startdatum
- Fällige Intervall-Einnahme auf morgen schieben und den ganzen Folgezyklus mitziehen
- Mehrere Medikamente und individuelle Dosen in einer Einnahme
- Ungeplante Einnahmen mit optionaler Notiz und denselben Bestands- und
  Nachweisgarantien
- Einmalige Einnahmen aus Automatisierungen, mit Grund, Referenz gegen
  Dopplungen und eigenen Erinnerungseinstellungen
- Wiederholte Erinnerungen über ausgewählte `notify.*`-Dienste und Skripte, mit
  Erinnerungsfenster gegen Benachrichtigungsfluten nach längerer Abwesenheit
- Optionaler automatischer Status `versäumt` für liegengebliebene Einnahmen
- Mobile Aktionen für „alles genommen“, 30 Minuten vertagen oder auslassen
- Teil-Einnahme, Vertagung um 30/60/120 Minuten oder auf eine freie Zeit sowie
  Auslassen direkt in der App
- Dauerhafte offene Tickets und Soll-Ist-Verlauf mit Statusfilter und Suche
- Therapietreue-Statistik über die letzten 30 Tage
- Verlaufsexport für einen Zeitraum als verschachteltes JSON oder als CSV mit einer
  Zeile je Medikamentendosis inklusive Packungszuordnungen
- Versioniertes JSON-Vollbackup und validierte Wiederherstellung
- Bestandsabbuchung erst, wenn eine Einnahme wirklich erfasst wurde
- Physische Packungen mit MHD, LOT/Charge, aufgedrucktem Code und automatisch
  vergebenem, eindeutigem Spitznamen
- Automatischer Bestand aus den Packungen, mit FEFO-Empfehlung, Dosisaufteilung
  über mehrere Packungen, Reichweitenschätzung und Ablaufwarnungen
- Lokal erzeugte, kontraststarke QR-Codes für Medikamente, Packungen und offene
  Einnahme-Tickets; der Generator akzeptiert nur stabile Kurzkennungen wie
  `med7K2QF`, niemals eine URL oder Medikamentendaten
- Sensoren, Binärsensoren, To-do-Liste, Kalender, Events und Aktionen für
  Dashboards und Automationen
- Lovelace-Karte zum Erfassen, Vertagen und Auslassen direkt im Dashboard,
  automatisch registriert ohne manuellen Ressourceneintrag
- Englisch als Standard, mit deutscher Oberfläche, Entitäten, Einrichtung,
  Aktionen und Benachrichtigungen

## Screenshots

| Überblick | Medikamente |
| --- | --- |
| <img src="https://raw.githubusercontent.com/Finnlife/hass-medreminder/main/docs/screenshots/overview-de.png" alt="Überblick mit fälligen Einnahmen" width="420"> | <img src="https://raw.githubusercontent.com/Finnlife/hass-medreminder/main/docs/screenshots/medications-de.png" alt="Medikamente mit Packungen" width="420"> |

| Pläne | Dashboard-Karte |
| --- | --- |
| <img src="https://raw.githubusercontent.com/Finnlife/hass-medreminder/main/docs/screenshots/plans-de.png" alt="Einnahmepläne" width="420"> | <img src="https://raw.githubusercontent.com/Finnlife/hass-medreminder/main/docs/screenshots/card-de.png" alt="Lovelace-Karte" width="260"> |

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

Alle Entitäten hängen am Service-Gerät **Medication schedule**; zusätzlich bekommt
jedes Medikament ein eigenes Gerät, damit Dashboards nach Medikament gruppieren
können.

Globale Entitäten:

| Entität | Typ | Hinweise |
| --- | --- | --- |
| Nächste Einnahme | Sensor (Zeitstempel) | Attribute: Plan, Medikamente, Dosen |
| Offene Einnahmen | Sensor (Anzahl) | Attribute: IDs und Kurzfassungen |
| Jetzt fällig | Sensor (Anzahl) | nur unerledigte, nicht vertagte Einnahmen |
| Letzte Einnahme | Sensor (Zeitstempel) | Attribute: Plan und Kurzfassung |
| Therapietreue | Sensor (%) | 30-Tage-Fenster, Diagnose-Kategorie |
| Einnahme fällig | Binärsensor (Problem) | Attribute: Anzahl und Kurzfassungen |
| Medikamenteneinnahmen | To-do-Liste | Abhaken erfasst die Einnahme, Löschen lässt sie aus |
| Medikamentenplan | Kalender | geplante Einnahmen aller aktiven Pläne |

Je Medikament:

| Entität | Typ | Hinweise |
| --- | --- | --- |
| Bestand | Sensor (Messwert) | Einheit aus dem Medikament, Packungsdaten als Attribute |
| Reichweite | Sensor (Tage) | Bestand geteilt durch die geplante Tagesmenge |
| Bestand niedrig | Binärsensor (Problem) | auf oder unter der Warnschwelle |
| Packung läuft ab | Binärsensor (Problem) | eine nutzbare Packung läuft binnen 30 Tagen ab |

Jede physische Packung erhält zusätzlich einen eigenen Bestands-Sensor mit LOT,
MHD, Anfangsmenge und aufgedrucktem Code als Attribute. Die endgültigen Entity-IDs
vergibt Home Assistant. Wird ein Medikament oder eine Packung im Panel gelöscht,
verschwinden auch Gerät und Entitäten aus der Registry.

Aktionen:

- `medication_reminder.record_intake`
- `medication_reminder.record_unplanned_intake`
- `medication_reminder.schedule_intake`
- `medication_reminder.cancel_intake`
- `medication_reminder.skip_intake`
- `medication_reminder.snooze`
- `medication_reminder.postpone_interval`
- `medication_reminder.add_package`
- `medication_reminder.delete_all_data` (benötigt `confirmation: DELETE`)

Events:

- `medication_reminder_due`
- `medication_reminder_taken`
- `medication_reminder_skipped`
- `medication_reminder_missed`
- `medication_reminder_low_stock`
- `medication_reminder_postponed`

## Einmalige Einnahmen aus Automatisierungen

`medication_reminder.schedule_intake` plant eine einzelne Einnahme außerhalb
wiederkehrender Pläne. Damit kann eine Automatisierung auf ein Ereignis reagieren:

```yaml
automation:
  - alias: Magnesium nach dem Sport
    triggers:
      - trigger: zone
        entity_id: person.finn
        zone: zone.fitnessstudio
        event: leave
    actions:
      - action: medication_reminder.schedule_intake
        data:
          items:
            - medication: Magnesium
              dose: 2
          time: "20:00"
          reason: Sport
          reference: "sport-{{ now().date() }}"
          notify_services:
            - notify.mobile_app_handy
```

Die Einnahme verhält sich danach wie jede andere: Sie erscheint im Panel, auf der
Karte, in der To-do-Liste und im Kalender, erinnert über die angegebenen Dienste,
bucht beim Erfassen den Bestand ab und zählt in die Therapietreue.

**Medikament wählen.** Jeder Eintrag braucht `dose` und entweder `medication_id`
oder `medication`. `medication` akzeptiert den Medikamentennamen oder den
aufgedruckten Scan-Code — Automatisierungen bleiben so lesbar und müssen keine
internen IDs mitschleppen.

**Zeitpunkt wählen.** Genau eine dieser Angaben:

| Option | Bedeutung |
| --- | --- |
| `scheduled_at` | Absolutes Datum mit Uhrzeit |
| `time` | Uhrzeit heute, oder morgen, wenn sie schon vorbei ist |
| `time` + `date` | Uhrzeit an genau diesem Tag |
| `in_minutes` | Minuten ab jetzt |

Ohne Angabe ist die Einnahme sofort fällig.

**Doppeltes Auslösen ist unkritisch.** Mit `reference` verschiebt ein zweiter
Aufruf mit derselben Referenz die bestehende offene Einnahme, statt eine zweite
anzulegen, und behält deren ID, damit eine bereits verschickte Benachrichtigung
gültig bleibt. Wähle eine Referenz, die zum Ereignis stabil ist, etwa
`sport-{{ now().date() }}`.

**Weitere Optionen.** `title` setzt die Überschrift (Standard: der Grund),
`scripts` startet Skripte bei jeder Erinnerung, und `repeat_minutes`,
`reminder_window_minutes` sowie `auto_miss_after_minutes` verhalten sich genau wie
die Einstellungen eines wiederkehrenden Plans.

Die Aktion liefert die angelegte Einnahme zurück, ein Folgeschritt kann sie nutzen:

```yaml
      - action: medication_reminder.schedule_intake
        response_variable: geplant
        data:
          items:
            - medication: Magnesium
              dose: 2
          in_minutes: 90
      - action: notify.mobile_app_handy
        data:
          message: "Magnesium geplant für {{ geplant.scheduled_at }}"
```

`medication_reminder.cancel_intake` entfernt eine geplante einmalige Einnahme
wieder, per `occurrence_id` oder per `reference`. Es greift nur auf einmalige,
noch offene und unberührte Einnahmen zu und schreibt nichts in den Verlauf — eine
abgebrochene Planung gilt also nicht als ausgelassen:

```yaml
      - action: medication_reminder.cancel_intake
        data:
          reference: "sport-{{ now().date() }}"
```

## Lovelace-Karte

Die Integration registriert `custom:medication-reminder-card` automatisch, eine
Lovelace-Ressource muss also nicht von Hand eingetragen werden. Die Karte lässt
sich über die Kartenauswahl (**Medication Reminder**) oder in YAML einbinden:

```yaml
type: custom:medication-reminder-card
title: Medikamente
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

| Option | Standard | Bedeutung |
| --- | --- | --- |
| `title` | `Medikamente` | Überschrift; ein leerer String blendet den Kopf aus |
| `mode` | `due` | `due` zeigt nur fällige Einnahmen, `open` alle offenen |
| `max` | `5` | Höchstzahl gelisteter Einnahmen, der Rest wird in einer Zeile zusammengefasst |
| `allow_partial` | `true` | Bearbeitbare Dosisfelder für Teil-Einnahmen; `false` erfasst die volle Restdosis |
| `show_snooze` | `true` | Buttons zum Vertagen um 30/60/120 Minuten |
| `show_skip` | `true` | Auslassen-Button |
| `show_upcoming` | `true` | Liste der nächsten geplanten Einnahmen |
| `upcoming_count` | `3` | Anzahl der aufgeführten kommenden Einnahmen |
| `show_stock` | `false` | Bestandsübersicht mit Balken je Medikament |
| `stock_filter` | `low` | `low` listet nur Medikamente auf oder unter der Warnschwelle, `all` alle |

Die Karte nutzt die WebSocket-API der Integration und zeigt deshalb dieselben
Packungsempfehlungen wie das Panel und erfasst auch Teil-Dosen. Sie aktualisiert
sich bei jedem Medication-Reminder-Event und pollt zusätzlich alle 15 Sekunden.

### Die Karte taucht nicht auf

Das Kartenmodul wird von der Integration selbst registriert und erscheint daher
erst, wenn Home Assistant die neuen Dateien geladen hat. Der Reihe nach:

1. **Home Assistant neu starten.** Dateien kopieren oder in HACS aktualisieren
   reicht nicht — das Modul wird beim Start der Integration registriert.
2. **Prüfen, ob die Datei ausgeliefert wird.** Rufe
   `/medication_reminder_frontend/medication-reminder-card.js` auf deiner
   Home-Assistant-Adresse auf. Ein 404 heißt, das Update ist nicht im
   `custom_components`-Verzeichnis angekommen; alles andere heißt, die Datei ist da.
3. **Browser ohne Cache neu laden** (Strg+Umschalt+R, in der Companion App den
   App-Cache leeren). Das Script-Tag steckt in der Dashboard-Seite selbst, eine
   gecachte Seite enthält es also nicht.
4. **In der Kartenauswahl unter „Benutzerdefiniert" schauen** oder nach
   *Medication* suchen.
5. **Browser-Konsole prüfen**, ob ein Fehler zu `localize.js` erscheint. Das
   hieße, dass nur ein Teil des Frontend-Ordners aktualisiert wurde.

Als Rückfalloption lässt sich das Modul auch von Hand unter **Einstellungen →
Dashboards → Drei-Punkte-Menü → Ressourcen** als JavaScript-Modul mit der URL
`/medication_reminder_frontend/medication-reminder-card.js` eintragen.

## Verlauf exportieren

Im Tab **Verlauf** einen inklusiven Zeitraum von **Von** bis **Bis** auswählen und
JSON oder CSV herunterladen. Wenn vorhanden, zählt der tatsächliche
Erfassungszeitpunkt, sonst der geplante Zeitpunkt. JSON enthält Vorgänge, Dosen und
Packungszuordnungen verschachtelt. CSV schreibt je Medikamentendosis eine Zeile und
legt Packungszuordnungen als JSON in der letzten Spalte ab. Exportiert wird nur der
gespeicherte abgeschlossene und ausgelassene Verlauf; offene Tickets und Stammdaten
sind nicht Teil dieses Exports.

## Vollbackup und Wiederherstellung

Über den Datenbank-Button im Panel-Header **Sichern und wiederherstellen** öffnen.
Das vollständige Backup lädt eine versionierte JSON-Datei mit allen Medikamenten,
Packungen, Plänen, offenen Tickets, gespeicherten Verlaufseinträgen und internen
Zeitplanständen herunter.

Die Wiederherstellung akzeptiert nur ein kompatibles Medication-Reminder-Backup.
Die komplette Datei wird validiert und ein unterstützter älterer Speicherstand vor
jeder Änderung migriert. Nach der Bestätigung ersetzt der Import den aktuellen
Medication-Reminder-Datenstand atomar. Lade vorher den aktuellen Stand herunter,
falls du später zu ihm zurückkehren möchtest.

## Speicherung und Verhalten

Alle Daten bleiben lokal unter `.storage/medication_reminder.data`. Nach einem
Neustart werden verpasste Termine für bis zu 30 Tage nachgebildet. Alte mobile
Aktionen sind idempotent und buchen Bestand nicht doppelt ab. Bis zu 2.000
abgeschlossene Vorgänge werden gespeichert; offene Vorgänge bleiben erhalten.

Jeder Plan steuert sein Erinnerungsverhalten selbst:

- **Erinnerung wiederholen alle** – Abstand zwischen zwei Erinnerungen.
- **Erinnern beenden nach** – nach so vielen Minuten ab Fälligkeit werden keine
  Benachrichtigungen mehr verschickt. Das Ticket bleibt im Panel offen. `0`
  erinnert, bis die Einnahme erledigt ist. Das verhindert eine Benachrichtigungs-
  flut nach Urlaub oder längerem Ausfall.
- **Als versäumt markieren nach** – schließt eine liegengebliebene Einnahme als
  `versäumt`, ohne den Bestand anzufassen, damit die Therapietreue-Statistik
  ehrlich bleibt. `0` lässt sie dauerhaft offen.

Eine Vertagung schlägt immer das Wiederholungsintervall: Läuft die Vertagung ab,
wird sofort erinnert und nicht erst nach dem nächsten Wiederholungsfenster.

Beim Bearbeiten eines Plans werden unberührte künftige Tickets entfernt, damit
Planänderungen sofort greifen; fällige und teilweise erfasste Tickets bleiben.

Über den Papierkorb im Panel-Header lassen sich nach einer zweiten Bestätigung mit
`DELETE` sämtliche Medication-Reminder-Daten dauerhaft löschen. Die Integration
selbst bleibt installiert. Dieselbe serverseitige Bestätigung gilt für die
Home-Assistant-Aktion.

Das Speicherschema ist versioniert; alter manueller Bestand wird verlustfrei in
eine physische `Legacy`-Packung überführt. Der Bestand wird danach immer aus den
Restmengen der Packungen berechnet. Das Projekt ist weiterhin vor Version 1.0. Vor
0.x-Updates sollte deshalb eine Sicherung von `.storage/medication_reminder.data`
erstellt werden; der dauerhafte Kompatibilitätsvertrag gilt erst ab Version 1.0.

## Entwicklung und vollständiger Test

Die genaue Anleitung für automatisierte Checks, eine isolierte Docker-Instanz und
die Übergabe an Codex steht in [docs/TESTING.de.md](https://github.com/Finnlife/hass-medreminder/blob/main/docs/TESTING.de.md).


Die Änderungen je Version stehen im [Changelog](https://github.com/Finnlife/hass-medreminder/blob/main/CHANGELOG.md).

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](https://github.com/Finnlife/hass-medreminder/blob/main/LICENSE).
