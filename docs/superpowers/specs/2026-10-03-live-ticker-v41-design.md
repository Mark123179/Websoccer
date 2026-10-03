# Freigegebene Umstellung auf die gelieferte v4.1-Baseline

## Umfang

- Geliefertes Erzähler-Paket vollständig bytegleich übernehmen. Keine Engine-Formeln ändern.
- Neue Geschichten tragen `v4.1`; bestehende Geschichten behalten ihre tatsächliche Erzählerversion.
- Ausschließlich die gespeicherten Geschichten 237, 239, 242 und 244 neu aufbauen.
- Vorher sämtliche Felder der alten MatchStory und MatchEvent in Dateien exportieren.
- Die übrigen 197 historischen Geschichten einschließlich der fünf widersprüchlichen Schuss-aufs-Tor-Fälle unverändert erhalten. Keine Ergebnisse oder Quelldaten umschreiben.

## Abnahme

- Die vier behobenen Fälle haben keine Issues und treffen die Schuss-aufs-Tor-Summen.
- Referenzen 114 und 179: Text unverändert, 140 beziehungsweise 108 Zeilen, 900 Sekunden, ein beziehungsweise null Issues.
- Neue Referenz 6: freigegebenes Drehbuch mit 123 Zeilen, 1.310 Sekunden und fünf Issues.
- Zweimaliges Erzählen ergibt identische Texte und Zeitwerte.
- Tests prüfen das gelieferte Paket byteweise und die Versionszuordnung je Geschichte.
- Fingerprints belegen unveränderte übrige Geschichten und unveränderte sämtliche SimulatedMatch-Daten.
- Vollständige Suite auf einer frischen isolierten PostgreSQL-Testdatenbank; keine Änderung der normalen Testdatenbank.

## Historische Texte

Der Nutzer hat den selektiven Neuaufbau ausdrücklich freigegeben. Ein bereits gelesener Ticker gehört zur Spielerinnerung; ein Paketwechsel allein rechtfertigt daher keinen Komplett-Neuaufbau.