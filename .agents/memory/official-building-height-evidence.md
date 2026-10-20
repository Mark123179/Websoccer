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


## Brücken: Bodenvergleich ist kein Decknachweis

Ungeklärte Brückenhöhen ausdrücklich als Geländeableitung statt gemessener
Fahrbahn behandeln. Den nativen Bodenvergleich einschließlich seiner
Kontrollalarme unabhängig davon erhalten.

**Why:** DGM1 enthält unter Brücken den Boden und keine Bauwerke. DOM1
enthält zwar Bauwerke, aber auch Vegetation und temporäre Objekte. Eine
OSM-Brückenlinie oder ein Layer-Wert macht daraus keine zugeordnete Deckmessung.
Der Nutzer verlangt räumliche Belege statt stiller Brücken-Ausnahmen.

**How to apply:** Erst mit räumlich belegter Deckquelle eigene Bauwerkshöhen
freigeben. Ohne diese Belege keine Layer-Aufschläge oder Endpunktglättung als
Messung ausgeben; Deckstatus und Bodenfehler getrennt berichten.

Kleine Offline-Bodenbelege nicht als vollständige Flächen- oder
Quantilprüfung ausgeben. Rangproben können den dokumentierten Quantilwert
nachrechnen, aber nicht die Rangfolge einer nicht mitgelieferten Population
erneut beweisen.

**Why:** Die realen Kölner Brückenalarme lassen sich mit wenigen nativen
Pixeln erhalten; ein knapp überschrittener Gesamtflächen-Quantilgrenzwert
hängt dagegen von der gesamten Stichprobenverteilung ab.

**How to apply:** Vollständige Objektprofile, lokale Alarmbelege und
historische Populationsstatistik in Offline-Tests ausdrücklich unterscheiden.
Für eine neue Gesamtflächen-Abnahme den vollständigen nativen Lauf verlangen.
## Teilkörper: Quellkonflikte und Projektion

Für ausdrücklich dargestellte LoD2-Teilkörper keine Quellüberlappung durch
Auswahl des höheren oder niedrigeren Körpers auflösen. Strittige Flächen
bleiben unvermessen; die Freigabe einer Gesamthöhe ist ein eigener Nachweis.

**Why:** An den westlichen Abelbauten überlappen amtliche Grundkanten minimal.
Außerdem können inverse PROJ-Transformationen bereits ausgeschnittener
extrem schmaler Restflächen numerisch ungültige Ringe erzeugen, obwohl
die amtlichen Originalgrundrisse gültig sind.

**How to apply:** In den Darstellungsrahmen projizieren, erst dort
partitionieren, Rechengenauigkeit offenlegen und den ursprünglichen
OSM-Grundriss erhalten. Quell-NHN je Teilkörper direkt auf den
Spielfeldbezug umrechnen, nicht auf den höchsten generalisierten
Geländepunkt setzen. Nicht mit einer Dachflächenrekonstruktion verwechseln.
