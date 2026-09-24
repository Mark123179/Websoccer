# Dortmund-Bestand: Geometrie- und Materialbefund

Stand: 24. September 2026. Die Browseransichten sind **kein Unity-Render**.
Diese Prüfung trennt Informationen aus dem gelieferten Bundle von Annahmen
der reduzierten Vorschau.

## Quellen und Koordinaten

`attached_assets/dortmundv3_1790167703231.bundle` enthält 681 Meshes,
472 Materials und 912 Texture2D-Objekte. Der reproduzierbare Export über
`scripts/export_dortmund_miniature.py` wählt 319 Meshes und vier
repräsentative Farbtexturen. Die Bounds unten sind aus den exportierten
Vertexdaten nach der Parent-Rotation in der gemeinsamen Unity-Welt berechnet:
Y ist oben, X die kurze und Z die lange Stadionachse. Kamera-Presets bzw.
Bezeichnungen wie „Hauptseite“ und „Gegenseite“ sind **keine** Quellenangaben.

| Mesh / Hierarchie | Material / Dreiecke | Bounds X / Y / Z in Metern |
| --- | --- | --- |
| `MAIN/back2.001/MESH_back2.001/back2_1` | `NoDraw_.003` / 2 | X 93,30; Y 2,88–36,59; Z −63,50–83,00 |
| `MAIN/left2.001/MESH_left2.001/left2_1` | `NoDraw_.004` / 26 | X −93,35–93,35; Y 2,88–36,57; Z 64,50–120,15 |
| `MAIN/right2.001/MESH_right2.001/right2_13` | `NoDraw_.005` / 10 | X 63,65–94,40; Y 16,46–36,74; Z −116,54–−64,28 |

Die drei Flächen liegen damit an +X, +Z und einer Ecke bei +X/−Z,
**nicht** auf zwei symmetrischen „gegenüberliegenden Fassaden“. Im
exportierten Ausschnitt lässt sich aus diesen Flächen keine durchgehende
gläserne oder gemauerte Außenfassade für −X/−Z ableiten. Das ist kein
Nachweis, dass der vollständige Unity-Level dort überhaupt keine
Fassaden hatte.

## Was `NoDraw_` aussagt – und was nicht

Die zugehörigen MeshRenderer sind aktiviert; die Materialien haben
Render-Queue 2000 und einen gespeicherten Base-Color-Alpha-Wert von 1.
Der Shadername lässt sich mit der verwendeten UnityPy-Auswertung **nicht**
auflösen. Daher belegt der Name `NoDraw_` allein weder Unsichtbarkeit noch
Transparenz oder eine bestimmte Farbe **im Unity-Spiel**. Der bisherige
Browser-Code interpretierte diese unbekannten Shader als opakes Grau und
zeichnete dazu auf −X und −Z weitere selbst entworfene Wände, Glasstreifen
und Pfeiler. Beides war keine quellgetreue Rekonstruktion.

**Vorschauentscheidung:** Die drei `NoDraw_`-Materialteile bleiben in
Manifest und Binärdatei erhalten, werden aber in den Browseransichten
ausgelassen. Dies vermeidet eine frei erfundene opake Fläche; es ist eine
konservative Darstellung bei **unbekannter Shaderwirkung**, keine Aussage
über das tatsächliche Unity-Rendering. Ergänzte Bestandsfassaden werden
nicht gezeichnet. Andere untexturierte Materialien erhalten weiterhin
vereinfachte Kategorienfarben; Shader, Lightmaps und der Großteil der
Texturen fehlen. Somit lässt sich weder aus der offenen Browseransicht
noch aus früheren Screenshots die exakte Unity-Außenansicht bestimmen.

Das Rundum-Konzept bleibt ein eigener, beschrifteter **Entwurf**, keine
Behauptung über den Bestand. Eine verbindliche Unity-Materialrekonstruktion
bräuchte die tatsächlichen Shader-/Passdefinitionen, weitere
Textur-/Lightmap-Zuordnungen und einen Vergleich mit einem Originalrender
in gleicher Kameralage. Ohne diese Daten werden keine Fassadentypen
erraten.

## Sichtvergleich

Die Vergleichsansicht wurde mit demselben Kamerapreset „Gegenseite“ bei
1440 × 900 Pixeln aufgenommen: [vorher mit ergänzten Wänden und Glasstreifen](../screenshots/dortmund-vergleich-bestand-gegenseite-nachher.png),
[jetzt mit Dach](../screenshots/dortmund-quellpruefung-gegenseite-dach-on.png)
und [jetzt ohne Dach](../screenshots/dortmund-quellpruefung-gegenseite-dach-off.png).
Das Vorher-Bild dokumentiert **die frühere Browser-Interpretation, kein
Unity-Originalrender**. Die neue offene Stelle zeigt die Grenze der
Vorschau, nicht den Nachweis einer offenen Stadionfassade im Original.