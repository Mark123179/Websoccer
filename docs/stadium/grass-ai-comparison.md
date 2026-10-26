# Isolierte KI-Rasenvergleichsserie

Die Serie ist ein zusätzlicher Materialvergleich, kein Ersatz des bereits
abgenommenen, vom Nutzer gelieferten Variantenpakets oder einer gespeicherten
Vereinsauswahl. Kein produktiver Import lädt `grass_surface_study.js`.

## Erzeugung

Die hier verfügbare Bildgenerierung erzeugte eine senkrechte, diffus beleuchtete
Grasaufnahme ohne Linien, Menschen, Tore oder Perspektive. Keine Higgsfield-
Integration und keine fremden Fotos. Eingabe: fein geschnittener natürlicher
Fußballrasen, gleichmäßige Albedo, kein Mähmuster, keine Schatten/Vignette.
Die tatsächliche KI-Datei und ihr SHA-256 stehen im Downloadpaket.

`python scripts/grass_study_materials.py` erzeugt aus dieser Basis:

- eine periodisch bereinigte Detailkarte; breite generierte Beleuchtung wird
  entfernt, echte Grasdetails bleiben erhalten;
- vier unabhängige Mähkarten, als relative Blattorientierung mit geglätteten
  Übergängen und wechselnder Detailausrichtung statt harter Lackflächen;
- vier getrennt dokumentierte sRGB-Grundtöne;
- eine RGB-Datenmaske im Feldmaß: R komprimiertes Gras, G offener Boden nur
  im Torraum, B Laufwege. Zentrum und Torbereiche werden gezielt bespielt.

Alle zwölf Albedos sind 3150 × 2040 Pixel für 105 × 68 Meter (30 px/m).
Die Details werden in zwei gedrehten, unterschiedlich skalierten Lagen
gemischt. Die Basis hat keine eingebrannten Schatten. Stark beansprucht bleibt
überwiegend grün, mit lokal begrenzten Kontaktspuren statt flächigem Schlamm.
Unabhängige Lagen und Parameter bleiben neben den fertigen WebP-Dateien erhalten.
Die Mähkontraste, Grüntöne und Abnutzungsfaktoren stehen im Manifest.

| Gruppe | Varianten | Kontrollierter Unterschied |
|---|---|---|
| A | A1–A4 | Vier Muster, Mittelgrün, frisch |
| B | B1–B3 | Drei zusätzliche Grüntöne, Längsstreifen, frisch |
| C | C1–C2 | Zwei zusätzliche Nutzungsgrade, Längsstreifen, Mittelgrün |
| D | D1–D3 | Ausgewählte Kombinationen |

## Echter gemeinsamer Renderer

`node scripts/export_grass_study.mjs` verwendet `mountStudyModel`,
`createStudyLighting` und das echte gemeinsame Feld aus `createStadiumStage`.
Der freigegebene 75%-Kamerakompromiss bleibt identisch: 1880 × 940,
Position (0,98,110), Neigung 44°, Brennweite 1337.4782524186542,
Hauptpunkt (940,681.3221103379157). Der offene Rahmen bleibt erhalten.

Es wird ausschließlich das Material der zehn bestehenden Grasflächen ersetzt.
UVs sind über alle Streifen kontinuierlich: u=(52.5−worldX)/105,
v=(worldZ+34)/68. Texturen werden einmalig als sRGB dekodiert; Standard-Mipmaps
und bis zu 8× anisotrope Filterung verringern Flimmern. Die alten Materialien
und UVs werden beim Wechsel wiederhergestellt. Die studieneigene bisherige
Farbübersteuerung wirkt nicht auf das neue weiße, texturierte Material.

Linien, Mittelkreis, Geometrie, Tore, Spielkoordinaten, Lichter und deren
Montagepunkte werden weder in die Textur gemalt noch verändert. Alle Varianten
werden am gleichen Taglicht gerendert, A1/C2 zusätzlich mit den belegten
Dortmunder Nachtquellen. `--elversberg` kontrolliert A1/C2 in einem zweiten
Stadionrahmen bei identischer Feldprojektion, ohne erfundene Nachtleuchten.

Die lokale Elversberg-Datenbank besitzt beim Export keine StadiumGeometry.
Deshalb verwendet der rein dateibasierte Export die vorhandene kanonische
Elversberg-Blueprint-Szene plus deren bestehende `load_surroundings()`-Quelle.
Es wird keine Geometrie in die Datenbank geschrieben und kein Ausbau simuliert.

## Reproduktion und Lieferung

Große Quellbilder und Renderausgaben liegen ausschließlich im ignorierten
`generated-artifacts/grass-study/`, nicht im Git-Verlauf. Der Browserexport
liest die Texturen über eine ausschließlich im Prüfprozess abgefangene URL;
es gibt keinen neuen öffentlichen Asset-Endpunkt und keine Änderung der
produktiven Rasenauswahl.

1. Die gelieferte KI-Basis unter `generated-artifacts/grass-study/grass-ai-base.png`
   ablegen; `python scripts/grass_study_materials.py` ausführen.
2. Die vorhandene kanonische Elversberg-Blueprint-JSON samt unveränderter
   `load_surroundings()`-Quelle als `elversberg-scene.json` daneben speichern.
3. Bei laufendem Dev-Workflow `node scripts/export_grass_study.mjs` und
   `node scripts/export_grass_study.mjs --elversberg` ausführen.
4. `python scripts/grass_study_report.py` erstellt die selbständige HTML-Studie
   mit eingebetteten Einzelbildern sowie die beschrifteten Vergleichstafeln.

Die Verifikationsdateien binden jeden tatsächlichen Render mit SHA-256 an
Kamera, identische Eckpunktprojektionen, Flächenzahl und Lichtzustand.
Der Export bricht bei veränderter Feldgeometrie, Projektionsmatrix,
Quellleuchtenausrichtung oder einem Shaderfehler ab.
