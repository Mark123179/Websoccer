# Managerprofil-Timeline: Spielticket-Karten

## Ziel

Timeline-Einträge mit Spielergebnis sollen wie authentische Eintrittskarten wirken. Die Gestaltung muss innerhalb der bestehenden horizontalen Managerprofil-Timeline funktionieren und normale Timeline-Einträge unverändert lassen.

## Ticket-Regel

Jeder Timeline-Eintrag mit einem Spielergebnis verwendet das Ticket-Layout. Dies gilt für automatisch erzeugte Finaleinträge und manuell erstellte Ergebnis-Einträge.

## Gemeinsame Inhalte

Jede Variante zeigt:

- Heimstadion als vollflächiges Hintergrundbild
- Hauptfarbe des Heimvereins als horizontalen Farbstreifen
- Heim- und Auswärtsverein mit Wappen
- Ergebnis als stärkstes Textelement
- Wettbewerb und Spieldatum
- rechten, optisch abtrennbaren Ticketstreifen
- Ticketcode in Form eines Barcodes oder einer vergleichbaren Strichgrafik

Ein optionaler Spielbericht-Link kann später die gesamte Karte klickbar machen. Er ist nicht Teil der ersten visuellen Dummys.

## Varianten

### 1. Klassische Eintrittskarte

Authentisches modernes Stadionticket. Dunkle Lesemaske über dem Stadionfoto, breiter Vereinsfarbstreifen, zentriertes Ergebnis und heller Abrissstreifen mit Perforation, Barcode und kleiner Tickettypografie.

### 2. Panorama-Ticket

Das Stadionbild ist das dominante Element. Vereinsfarbe und Ergebnis liegen kompakter darüber. Der dunkle Abrissstreifen verwendet eine QR-artige Codegrafik. Diese Variante priorisiert Atmosphäre.

### 3. Retro-Spieltagkarte

Gedruckte, leicht gealterte Papierwirkung mit gestanzter Ecke und grobem Ticketcode. Das Stadionfoto wirkt reproduziert statt digital. Diese Variante priorisiert Charakter und Fußballnostalgie.

### 4. Sammlerpass / Finalticket

Hochwertige, kontrastreiche Variante mit hervorgehobener Wettbewerbsmarke, großem Ergebnis und nummeriertem Abrissstreifen. Diese Variante eignet sich besonders für bedeutende Spiele.

## Mockup-Daten

Die vier Varianten verwenden realistische Dummy-Spiele mit unterschiedlichen Heimvereinen, Vereinsfarben, Stadien, Ergebnissen und Wettbewerben. Die Daten sind ausschließlich für die visuelle Auswahl und verändern keine Anwendungsdaten.

## Einbettung und Größen

- Ausgangspunkt ist die echte Managerprofil-Timeline.
- Die bestehende feste Artboard- und horizontale Scrolllogik bleibt erhalten.
- Die Ticketkarte bleibt ungefähr im vorhandenen Kartenformat von 234 Pixel Breite.
- Der rechte Abrissstreifen ist Teil der Karte und darf die Timeline nicht verbreitern.
- Text und Ergebnis müssen trotz Stadionbild einen zugänglichen Kontrast behalten.
- Bei langen Vereinsnamen werden Namen gekürzt oder typografisch verkleinert, ohne den Ergebnisblock zu verschieben.

## Technische Richtung nach Auswahl

Für eine spätere Integration werden Ergebnis-Einträge um strukturierte, optionale Spieldaten ergänzt oder an ein bestehendes Spiel gekoppelt. Benötigt werden Heim-/Auswärtsverein, Wappen, Ergebnis, Wettbewerb, Datum, Stadionbild, Heimfarbe und optional eine Spielbericht-URL. Bestehende freie Ergebnistexte bleiben als Rückfall erhalten.

## Abnahmekriterien für die Dummys

- Vier visuell klar unterscheidbare Ticketvarianten sind nebeneinander sichtbar.
- Alle Varianten enthalten Stadionbild, Heimfarbe, Ergebnis und Abrissstreifen.
- Die Varianten orientieren sich sichtbar an der bereitgestellten Ticketreferenz, ohne sie pixelgenau zu kopieren.
- Keine Änderung an der produktiven Managerprofil-Timeline oder an gespeicherten Daten.
- Die Vorschau funktioniert ohne Backend und ohne Anmeldung.