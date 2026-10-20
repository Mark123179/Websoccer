---
name: Amtliche Gebäudehöhen richtig einordnen
description: Grenzen amtlicher LoD-Höhen als Sichtbeleg und Besonderheiten des Saarland-WFS.
---

Amtliche „measured“-Gebäudehöhen sind ohne eindeutige Grundrisszuordnung,
Höhenreferenz und Gelände relativ zum Spielfeld kein vollständiger
Fassaden-Sichtnachweis. Schwache Überlappung darf nicht durch eine
Namens-/Nähevermutung oder eine typische Supermarkthöhe ersetzt werden.

**Why:** In der Elversberger Umfeldrecherche waren gemessene Komponenten
für Wasgau/TVE räumlich plausibel zuordenbar, für Lidl jedoch nicht.
Zudem blieben im amtlichen Dienst obere und untere Höhenreferenzen
unbestimmt. Ein belastbarer numerischer Wert kann trotzdem zum falschen
Gebäude gehören oder auf einer unzureichenden Geländeannahme beruhen.

**How to apply:** Quellenidentität und räumliche Überlappung getrennt von
der Sichtberechnung bewerten. Hüllmodelle und angenommene Höhen ausdrücklich
kennzeichnen; kein ortsverifiziertes Hintergrundbild aus ihnen ableiten.

Der Saarland-LoD2-WFS kann bei gefüllten Antworten `numberReturned=0`
melden und Seiten begrenzen. Seine EPSG:4326-Geometrieantwort ist
zweidimensional; die Höhe ist separat attributiert.

**Why:** Eine naive Auswertung dieser Antwortattribute würde echte Daten
als fehlend behandeln oder die begrenzte erste Seite für vollständig halten.

**How to apply:** Tatsächliche Gebäudeelemente zählen, Seiten eindeutig
zusammenführen und eine kurze Schlussseite verlangen; bei Fehlerantworten
keine stillen Ersatzwerte einsetzen.

## NRW: amtlicher Zahlenwert ist nicht automatisch eine Messung

Bei LoD2 zusätzlich die Herkunftsattribute prüfen: das Produkt enthält auch
Standardwerte. Mehrere räumlich passende Teilkörper mit unterschiedlichen
Bodenniveaus ergeben noch keine belegte Einzelhöhe für einen ganzen
OSM-Gebäudegrundriss.

**Why:** Die Kölner Abelbauten überdecken mehrere amtliche Teilkörper;
die Auswahl einer maximalen oder mittleren Höhe würde Präzision vortäuschen.

**How to apply:** Nur im dokumentierten Überdeckungsumfang übernehmen.
Ungeeignete Einzelhöhen weiterhin als unvermessen kennzeichnen; die
Quellbezeichnung „measuredHeight“ nicht als ausreichenden Messnachweis lesen.

NRW-WCS-Parameterfehler bei großen Ausschnitten sind kein Nachweis fehlender
Höhendaten.

**Why:** Derselbe gültige DGM-Bereich war in kleineren, explizit dokumentierten
Teilausschnitten erreichbar, obwohl die Gesamtanfrage abgewiesen wurde.

**How to apply:** Dienstgrenzen von räumlicher Datenabdeckung unterscheiden;
Auflösung und Höhenbezug bei einer Aufteilung unverändert lassen.
