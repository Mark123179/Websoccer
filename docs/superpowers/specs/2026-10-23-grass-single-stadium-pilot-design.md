# Rasen-Pilot: ein vorhandenes Stadion im 2D-Modus

## Auftrag und Freigabegrenze

Der Nutzer möchte nur eine kleine Testvariante mit einem bereits vorhandenen
Stadion. Zuerst wird die Darstellung im 2D-Modus beurteilt. Erst nach deren
Abnahme wird der Stadioneditor betrachtet; ein breiter Rollout folgt nicht
automatisch.

## Gewählter Ansatz

Eine getrennte, nur für Administratoren zugängliche Testseite mit Dortmund.
Sie verwendet das vorhandene Stadionmodell und die bestehende feste,
spielfeldzentrierte 2D-Spielperspektive. Keine Orbitkamera, keine neue
Stadionrekonstruktion, kein zweites Vergleichsstadion.

Alternativen:

- Die normale Stadionansicht um einen Testschalter erweitern: weniger
  Trennung und unnötige Berührung des normalen Betriebs.
- Nur die gelieferte HTML-Studie anzeigen: einfach, prüft aber gerade nicht
  die Wirkung im vorhandenen Stadion und dessen tatsächlicher Beleuchtung.

## Bedienung

- Beim Öffnen ist der unveränderte heutige Rasen ausgewählt.
- Eine kompakte Auswahl bietet Bestand sowie die zwölf beschrifteten
  Varianten A1–A4, B1–B3, C1–C2 und D1–D3.
- Vorhandene Tag-/Nacht- und Dachschalter dienen dem Vergleich.
- Der Wechsel verändert nur das Rasenmaterial derselben Szene.
- Keine zusätzliche Bearbeitung der Musterparameter, keine Vereinsauswahl,
  kein Speichern, keine neue Spielsimulation oder Änderung der Tickerzeiten.

## Rendering und Datenfluss

Die vorhandene Szene und ihre Kamera bleiben maßgeblich. Die Materiallagen
aus dem gelieferten `rasenvarianten_paket.zip` werden an den vorhandenen
Renderer angepasst, nicht durch die Vergleichsbilder ersetzt.
Spielfeldmaße, Feldprojektion, Linien, Umgebung und Lichtfaktoren bleiben
unverändert. Die Abnutzungsmaske bleibt an Feldkoordinaten gebunden.

Die Admin-Route liefert ausschließlich lesende Konfiguration. Neue
Materialdateien werden über den bestehenden Asset-/Speicherweg ausgeliefert,
nicht als Datenbank-Blobs gespeichert. Gelieferte Generierungsprogramme
werden nicht ausgeführt. Es gibt keinen Schreibzugriff auf Vereinsdaten,
StadiumDesign, Geometrie oder gespeicherte Materialauswahl.

Der Variantenwechsel verwaltet Materialzustand und Texturen lokal. Ein Wechsel
zurück zum Bestand stellt das ursprüngliche Material wieder her. Die
allgemeinen Materialvorgaben des Stadionrenderers werden nicht geändert.

## Fehlerverhalten

Fehlende Dateien oder ein fehlgeschlagener Shader erzeugen eine sichtbare
Fehlermeldung. Eine betroffene Variante wird nicht als erfolgreich angezeigt.
Der Bestand bleibt erreichbar. Keine stillen Ersatztexturen und keine
Lockerung der bestehenden Admin-Zugriffskontrolle.

## Prüfung und Abnahmekriterien

- Nicht-Administratoren können die Testseite nicht verwenden.
- Der normale Stadionaufruf und der Stadioneditor behalten ihr Verhalten.
- Alle zwölf Varianten lassen sich wechseln; Bestand wird wiederhergestellt.
- Umschalten und Neuladen verändern keine gespeicherten Stadiondaten.
- Spielfeld, Linien und Kamera bleiben beim Materialwechsel deckungsgleich.
- Tatsächliche Ansichten bei Tag und Nacht prüfen; die gelieferten
  Albedo-Luminanzprotokolle gelten nicht als Flutlichtabnahme.
- Ergebnis zur visuellen Nutzerabnahme vorlegen. Kein Editorumbau und kein
  Rollout ohne die jeweils nächste Freigabe.
