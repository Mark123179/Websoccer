# Dortmund: Neon-Umfeld und kartierte Bäume

Der Nutzer möchte das produktive 3D-Umfeld im dunklen Neon-Schema der
2D-Ansicht und seines Screenshots. Er hat die Übernahme kartierter Bäume
aus dem bereits vorhandenen Dortmund-OSM-Auszug gewählt.

## Darstellung

Fast schwarzer Grund, zurückhaltende cyanfarbene Straßen und Gebäudekanten,
dunkle Gebäudevolumen sowie grüne Flächen und erkennbare grüne Baumkronen.
Die Darstellung betrifft das Umfeld, nicht die Originalmaterialien des Stadions.
Sie bleibt unabhängig von Ausbau, Dach und Kamera.

## Gemeinsame Daten

Der vorhandene OSM-Baumauszug wird unter Erhalt seiner Quellenangabe in den
Editorrahmen umgerechnet. Derselbe Datensatz wird in 2D und 3D verwendet.
Vorhandene explizite Editor-Baumpositionen haben Vorrang. Die Ergänzung
verändert weder gespeicherte Stadiongeometrie noch Designs oder Kapazitäten.
Baumformen und Größen bleiben schematisch; keine Zufallsbäume.

## Prüfung

Koordinaten gegen die Georeferenz der ursprünglichen 2D-Karte prüfen.
Gezielte Tests für Datenübernahme, Vorrang vorhandener Bäume, Nichtmutation,
Neonmaterialien und Ressourcenfreigabe. Gerenderte Sichtprüfung in Bestand
und Rundum einschließlich sichtbarer Bäume.

## Ergebnis

248 vorhandene OSM-Baumpositionen wurden in den ursprünglichen Blueprint-
Spielfeldrahmen umgerechnet. Die unabhängig angepasste Rotation und Skalierung
der Vergleichsszene wurden nicht übernommen. Der Editor ergänzt die Daten
nur in seiner Antwort; gespeicherte Geometrie und Designs bleiben unverändert.
Explizite bestehende Baumlisten haben Vorrang, auch wenn sie leer sind.

16 gezielte JavaScript- und 11 Django-Prüfungen bestehen. Sichtprüfung erfolgte
im angemeldeten produktiven Editor: 2D, Wechsel nach 3D und Rundum. Keine
JavaScript-Laufzeitfehler. Bäume sind in beiden Ansichten sichtbar.

- [Bestand mit Neon-Umfeld](../../../screenshots/dortmund-neon-umfeld-bestand.png)
- [Rundum mit Neon-Umfeld](../../../screenshots/dortmund-neon-umfeld-rundum.png)
- [2D mit denselben Baumpositionen](../../../screenshots/dortmund-neon-editor-2d.png)