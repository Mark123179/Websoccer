# Dortmunder Editor: vorhandenes Umfeld in 3D

## Freigegebene Darstellung

Der Nutzer hat das vereinfachte 3D-Umfeld gewählt. Die produktive
Dortmunder Szene übernimmt dieselben Straßen, Grünflächen, Gewässer,
Gebäudepolygone und gegebenenfalls Baumpositionen wie die 2D-Ansicht.
Gebäudehöhen und Baumformen sind schematisch; es werden keine zusätzlichen
Ortsmerkmale erfunden und keine neuen Kartenquellen benötigt.

## Daten und Koordinaten

Die bestehende 2D-Aufbereitung bleibt die gemeinsame Datenquelle. Sie erhält
zusätzlich Gebäudehöhen und Quellenangabe für die 3D-Darstellung. Der
2D-Spielfeldrahmen hat seine Längsachse auf X; die Unity-Längsachse liegt auf
Z. Die Übertragung berücksichtigt diesen Vierteldrehungs-Unterschied sowie
Spielfeldzentrum und Achsenwinkel, ohne gespeicherte Geometrie zu verändern.

## Grenzen und Prüfung

Das Umfeld ist eine separate, gemeinsam entsorgbare Szenengruppe. Es bleibt
bei Dach-, Kamera- und Bestand/Rundum-Wechseln sichtbar und wird nicht mit
Ausbauflächen verformt. Geometrie, Kapazität, Aufträge, Geld und Designs bleiben
unverändert. Tests prüfen Transformation, gemeinsame Daten, Höhen,
Ressourcenfreigabe und leere/fehlerhafte Eingaben. Sichtprüfung erfolgt mit
Software-WebGL auf Bestand und Rundum, einschließlich weiterer Außenkamera.

## Ergebnis der Prüfung

Die vorhandenen Dortmunder Daten liefern 148 Gebäude, 230 Straßenabschnitte
und 67 Grünflächen, jedoch keine Gewässer oder einzelnen Baumpositionen.
Die fehlenden Kategorien erzeugen keine erfundenen Objekte. Die Kartengeometrie
ist zu fünf Renderobjekten gebündelt und bleibt eine vom Ausbau getrennte
Gruppe. Sechs neue JavaScript-Prüfungen decken Transformation, gemeinsame
2D-/3D-Daten, Höhen, Legacy-Daten, Ressourcenfreigabe und Fehlerfälle ab.
Die vier gezielten Django-Editorprüfungen und die bestehenden JavaScript-
Seiten-/Szenenprüfungen bestehen.

Sichtprüfung der produktiven Szene mit echten Editor-Umfelddaten in einem
isolierten Software-WebGL-Testbett:
[Bestand](../../../screenshots/dortmund-umfeld-bestand.png),
[weitere Außenkamera](../../../screenshots/dortmund-umfeld-aussen.png),
[Rundum nach Kamera- und Dachwechsel](../../../screenshots/dortmund-umfeld-rundum.png).
Die Bilder bestätigen die sichtbare Übernahme, nicht eine Vermessung oder
einen authentifizierten vollständigen Editor-Durchlauf.