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

Zur Nachprüfung wurden auch alle 362 bislang nicht exportierten MeshFilter
mit ihren vollständigen Parent-Transformationen in Weltkoordinaten
ausgewertet. Niedrige Bauteile an den Außenseiten wurden nach Höhe,
Dreiecksausrichtung und Material getrennt: Die bislang fehlenden
`EXTRA/*_nf_nr`-Teile sind vor allem beleuchtete Flächen, Dachdetails und
zwei schmale Glasstreifen (`front_nf_nr_5` an X −74…−72, Y 17…20;
`back_nf_nr_5` an X 72…75, Y 12…20). `AD/ad_normal` trägt
Werbeflächen. Keines davon ist eine bislang ausgelassene durchgehende
Außenwand an −X oder −Z; die Glasstreifen haben eine eigene,
hier nicht rekonstruierte transparente Materialwirkung.

| Mesh / Hierarchie | Material / Dreiecke | Bounds X / Y / Z in Metern |
| --- | --- | --- |
| `MAIN/back2.001/MESH_back2.001/back2_1` | `NoDraw_.003` / 2 | X 93,30; Y 2,88–36,59; Z −63,50–83,00 |
| `MAIN/left2.001/MESH_left2.001/left2_1` | `NoDraw_.004` / 26 | X −93,35–93,35; Y 2,88–36,57; Z 64,50–120,15 |
| `MAIN/right2.001/MESH_right2.001/right2_13` | `NoDraw_.005` / 10 | X 63,65–94,40; Y 16,46–36,74; Z −116,54–−64,28 |

Die drei Flächen liegen damit an +X, +Z und einer Ecke bei +X/−Z,
**nicht** auf zwei symmetrischen „gegenüberliegenden Fassaden“. Im
Bundle sind an −X die `front1`-Tribünenstruktur und der `front2`-Oberrang
vorhanden, an −Z `right1`-Betonbauteile und `right2`-Rangstruktur. An +Z
liegt außerdem der breite Betonunterbau `left1_0`. Das sind echte Bauteile
im Browser-Export, **aber keine zusätzliche, durchgehende niedrige
Außenhaut wie `back2_1` an +X**. Unter den 681 gelieferten Meshes wurde
keine solche flächige Abschlusswand an −X/−Z gefunden. Damit bleiben
dort offene Bereiche in dieser Quellgeometrie, die nicht mit frei
erfundenen Wandflächen geschlossen werden dürfen. Die Auswertung
beansprucht kein Urteil über außerhalb des Bundles geladene Unity-Szenen.

## Was `NoDraw_` aussagt – und was nicht

Die zugehörigen MeshRenderer sind aktiviert; die Materialien haben
Render-Queue 2000 und einen gespeicherten Base-Color-Alpha-Wert von 1.
Alle drei speichern außerdem `baseColorFactor = (0,906, 0,906, 0,906, 1)`,
keine Base-Color-Textur, `_BUILTIN_SrcBlend=1`,
`_BUILTIN_DstBlend=0` und `_AlphaClip=0`: Das spricht in der
gespeicherten Materialkonfiguration für deckendes Zeichnen. Sie
referenzieren denselben nicht auflösbaren Shader-Pfad wie andere
Stadionmaterialien; der Shadername und die tatsächlichen Passes sind
mit UnityPy **nicht** auslesbar. `NoDraw_` ist deshalb weder ein Beweis
für Unsichtbarkeit noch eine Garantie für den genauen Unity-Look.
Der frühere Browser-Code zeichnete zusätzlich auf −X und −Z frei
entworfene Wände, Glasstreifen und Pfeiler. Diese waren keine
quellgetreue Rekonstruktion und bleiben entfernt.

**Vorschauentscheidung:** Die drei originalen `NoDraw_`-Meshflächen werden
in beiden Browseransichten wieder gezeichnet. Der Offline-Export hält
ihren aus den geprüften Materialwerten abgeleiteten hellen Farbwert
`#e7e7e7` pro Teil fest und bricht bei abweichender Blend-/Alpha-Lage
ab; ohne diesen Nachweis wird eine `NoDraw_`-Fläche nicht mit der
generischen grauen Standardfarbe ersetzt. Die Farbe ist eine
**vereinfachte Materialvorschau**, keine exakte Unity-Shaderausgabe.
Ergänzte Bestandsfassaden werden nicht gezeichnet. Andere untexturierte
Materialien erhalten weiterhin vereinfachte Kategorienfarben; Shader,
Lightmaps und der Großteil der Texturen fehlen. Die Browseransicht ist
daher weiterhin kein vollständiger Unity-Render.

Das Rundum-Konzept bleibt ein eigener, beschrifteter **Entwurf**, keine
Behauptung über den Bestand. Eine verbindliche Unity-Materialrekonstruktion
bräuchte die tatsächlichen Shader-/Passdefinitionen, weitere
Textur-/Lightmap-Zuordnungen und einen Vergleich mit einem Originalrender
in gleicher Kameralage. Ohne diese Daten werden keine Fassadentypen
erraten.

## Sichtvergleich

Die Vergleichsansicht wurde mit demselben Kamerapreset „Gegenseite“ bei
1440 × 900 Pixeln aufgenommen: [vorher mit ergänzten Wänden und Glasstreifen](../screenshots/dortmund-vergleich-bestand-gegenseite-nachher.png),
[Zwischenstand mit ausgelassenen Quellflächen](../screenshots/dortmund-quellpruefung-gegenseite-dach-on.png),
[jetzt mit Dach](../screenshots/dortmund-bestandswaende-gegenseite-dach-on.png)
und [jetzt ohne Dach](../screenshots/dortmund-bestandswaende-gegenseite-dach-off.png).
Das Vorher-Bild dokumentiert **die frühere Browser-Interpretation, kein
Unity-Originalrender**. Die Gegenseite zeigt auch nach dem Wiederanzeigen
der Quellflächen keinen durchgehenden Abschluss an −X/−Z: Dort ist im
Bundle keiner nachgewiesen. Die vorhandenen hellen Quellflächen an
+X/+Z sind in der [Außenperspektive ohne Dach](../screenshots/dortmund-bestandswaende-quellflaechen-aussen.png)
sichtbar. Der [produktive Editor mit Dach aus](../screenshots/dortmund-editor-bestandswaende-gegenseite-dach-aus.png)
zeigt dieselbe Bestandstrennung.