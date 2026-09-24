# Dortmund-Bestand: Geometrie- und Materialbefund

Stand: 24. September 2026. Die Browseransichten sind **kein Unity-Render**.
Diese Prüfung trennt Informationen aus dem gelieferten Bundle von Annahmen
der reduzierten Vorschau.

**Aktuelle Darstellungsentscheidung:** Nach dieser Quellprüfung wurde die
Schließung der Gegenseite ausdrücklich als **Rekonstruktion** freigegeben.
Danach wurden die drei originalen `NoDraw_`-Außenwände nur in der
Bestandsvorschau an deren Grundfarbton angeglichen. Diese Farbwahl ist
**kein Quellenbefund** und verändert weder den Unity-Export noch dessen
gespeicherte Materialwerte. Im Rundum-Konzept behalten die Quellflächen
ihre zuvor abgeleitete helle Browserfarbe.
Die Ergänzung ist kein Unity-Original; die folgenden älteren Aussagen zur
damals bewusst offenen Browseransicht dokumentieren den Zustand vor dieser
Freigabe. Die Quellenbefunde und ihre Unsicherheit gelten unverändert.

## Nachprüfung der gemeldeten dunklen Außenkante

Die erneut gelieferte Bundle-Datei
`attached_assets/dortmundv3_1790253864852.bundle` ist bytegleich mit der
bereits geprüften Datei (SHA-256:
`b626002f437097d92e914b93e7036257e63b9574c0d2a8f4fa8592407b2bad66`).
Die ebenfalls gelieferten Lichtmap-/Lichtprobe- und Sitzdateien enthalten
keine zusätzliche Fassadengeometrie. Die Aufnahme
`attached_assets/image_1790253745777.png` zeigt eine schräge Ansicht der
−X/−Z-Seite mit Dach. Der vorhandene Preset „Gegenseite“ schaut bei Azimut
−2,28 rad, Elevation 0,53 rad und Abstand 490 m auf diese beiden Seiten;
die Aufnahme kann zusätzlich frei gedreht worden sein. Sie enthält **keine
Kameraposition oder Orbit-Werte**:
Eine Zuordnung *jedes einzelnen Bildpixels* zu einem Unity-Dreieck wäre
deshalb vorgetäuschte Genauigkeit. Die Untersuchung unten ordnet stattdessen
die sichtbare lange −Z-Kante den Weltkoordinaten und Meshes zu.

Die dunkle Zone ist nicht einheitlich: In der gelieferten 602 × 292-Aufnahme
ist etwa Pixel (225, 190) dunkelgrau `(36, 45, 45)`, während (225, 200)
genau die Hintergrundfarbe `(22, 34, 37)` hat. Der obere Teil zeigt somit
auch dunkle vorhandene Bauteile; der darunter sichtbare Hintergrund ist
eine tatsächliche Sichtöffnung, nicht bloß ein schwarzes Wandmaterial.
Kamerawinkel, Dachkante und die fehlende Originalbeleuchtung verstärken
die Wirkung. Die Browseransichten setzen `DoubleSide` ein und zeigen damit
auch Rückseiten von nach *innen* gerichteten Flächen; eine von außen
sichtbare Rückseite ist noch keine äußere Abschlusswand.

| Bereich an −Z | Nachweis aus exportierten Dreiecken | Bedeutung |
| --- | --- | --- |
| Oberrang mittig, \|X\| < 50 m, Y 16–36 m | `right2_5.001`, Material `st051_star002.015`: 1.040 hinreichend vertikale Dreiecke mit 2.075 m² Projektion in Richtung **+Z (innen)**, 0 m² in Richtung −Z. Die Rangstufen liegen etwa Z −84…−112 m. | Viel echte Geometrie, aber kein nach außen orientierter flächiger Abschluss. |
| Unterbau mittig | `right1_1.001` liegt bei Y 3–12,5 m und Z −83…−93 m; `right1_4.001` ist stellenweise weiter außen bei Z −111…−72 m, aber nicht als durchgehende Außenhaut. | Die hellen Teilflächen und die dunklen Zwischenräume stammen von unterschiedlichen echten Teilen bzw. freien Sichtlinien. |
| Äußere Ecke | `right2_13.001` (`NoDraw_.005`) liegt bei X 63,65…94,40 m, Y 16,46…36,74 m, Z −116,54…−64,28 m. | Die bereits wiederhergestellte Quellfläche verschließt nur die Ecke, nicht die Mitte der langen Seite. |

Die Exportprüfung umfasst 319 ausgewählte Meshes. Von den übrigen 362
MeshFiltern wurde jeder mit der **vollständigen** Parent-Transformation
erneut vermessen. Bei Z < −95 m, Y innerhalb 4–37 m, mindestens 10 m
X-Spannweite und 3 m Höhenspannweite findet sich nur ein nicht exportiertes
Mesh mit vertikaler Z-Projektionsfläche über 1 m²:
`right_nf_nr_2` (`st051_emit001.003`, 4,2 m²). Das ist ein
Emissions-/Beleuchtungsteil, keine ausgelassene Fassadenplatte. Die
Lichtmaps könnten die Helligkeit der vorhandenen Teile verändern, aber
keine fehlenden Dreiecke erzeugen. Der Export schließt also hier keine
nachweisbare breite Außenwand durch den Namensfilter aus; an der
mittleren äußeren Kante liefert das Bundle keine belegte durchgehende
Abschlussfläche. Die gespeicherten Unity-Shader-Passes sind weiterhin
nicht auflösbar; die genaue Materialwirkung lässt sich ohne Originalrender
mit demselben Orbit nicht verbindlich vergleichen.

**Folge des damaligen Originalabgleichs:** Keine neue Wand ist als Unity-Original
nachweisbar. Die später ausdrücklich beauftragte, separat gekennzeichnete
Rekonstruktion ist unten dokumentiert; sie deutet kein Rangteil zur Quellwand
um. Die belegten `NoDraw_`-Flächen bleiben in beiden Ansichten erhalten.
Dieser Befund betrifft nur die reduzierte Bestandsvorschau; Rundum-Entwurf,
2D-Bearbeitung/Speichern, Kapazität und Ökonomie werden nicht verändert.

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

## Herkunft der früheren Fassadenbilder

| Aufnahme / Ansicht | Was sichtbar ist | Herkunft und Aussagekraft |
| --- | --- | --- |
| [Bestand vor der Browser-Ergänzung](../screenshots/dortmund-bestand-gegenseite-tatsaechlich-vorher.png) | Echte ausgewählte Bundle-Meshes in vereinfachter Browserbeleuchtung; damals waren einzelne `NoDraw_`-Quellflächen noch ausgelassen. | Keine verbindliche Unity-Farbe und kein Beweis für eine geschlossene Außenwand. |
| [Bestand mit vermeintlichen „Fenstern“](../screenshots/dortmund-vergleich-bestand-gegenseite-nachher.png) | Zusätzlich zu den Quellmeshes eine von der Browserimplementierung gezeichnete Wand auf −X und −Z samt diagonalen Übergängen, dunklen Bändern auf 7–12 und 23–28 m, Gesims und regelmäßigen Pfosten. | Die frühere Ergänzung hieß `RECONSTRUCTED_EXISTING_FACADE`; ihre Wandfarbe (`#707975`) und „Verglasung“ (`#26383a`) waren **frei gewählt**. Weder Unity-Fenster noch aus OSM gemessene Öffnungen. Die Ergänzung ist entfernt. |
| [Bestand mit Quellflächen](../screenshots/dortmund-bestandswaende-gegenseite-dach-on.png), [Dach aus](../screenshots/dortmund-bestandswaende-gegenseite-dach-off.png) | Ausgewählte Originaldreiecke einschließlich der drei `NoDraw_`-Flächen; nicht texturierte Materialien als Kategorienfarben, `NoDraw_` anhand gespeicherter deckender Werte hellgrau. | Aktuelle **Mesh-Vorschau**, nicht Unity-Originalrender. Offene Bereiche an −X/−Z bleiben offen. |
| [Rundum-Konzept](../screenshots/dortmund-rundum-gegenseite-nachher.png) | Eigene vierseitige Ausbauhülle mit konstruierten Wänden, Bändern, Stützen und Dachanschlüssen. | Entwurf, **nicht** Bestandsfassade; die dortige einfarbige Wand belegt keine Quelle für eine Bestandswand. |

Die alte Fensterwand ist in der Git-Historie anhand der inzwischen entfernten
Dateien `_ExistingFacade.ts` und `dortmund_existing_facade.js` nachvollziehbar.
Das Paket lieferte dagegen `back2_1.001`, `left2_1.001` und `right2_13.001`
als tatsächliche `NoDraw_`-Dreiecke. Ihre Browserfarbe ist eine Annäherung an
gespeicherte Materialwerte, nicht eine Aufnahme der Shaderausgabe.

## Originalabgleich: derzeitige Grenze

Die beiden aktuellen 3D-Ansichten verwenden **identische** exportierte
`manifest.json` und `geometry.bin` und für den Bestand dieselben vier
Basecolor-Texturen, Kameraparameter (Perspektive 42°, Zielpunkt
`(0, 25, 0)`, „Gegenseite“: Azimut −2,28 rad, Elevation 0,53 rad,
Distanz 490 m), Beleuchtungswerte und Materialzuordnung. Dach *an* bzw.
*aus* ist jeweils ein Browser-Schalter. Damit sind die Aufnahmen innerhalb
der Browserdarstellung vergleichbar; die Szene ist **keine** vollständige
Unity-Szene. Die OSM-Umgebung des Vergleichs ist eine separate schematische
Kulisse und keine Fassadenquelle.

Es liegt im Arbeitsverzeichnis kein zuordenbarer **Originalrender aus Unity
mit Kameradaten**, keine `.unity`-Szenendatei und keine zugehörigen
Shader-/Pass-Quelldateien vor. Die hochgeladene
[`image_1790253745777.png`](../attached_assets/image_1790253745777.png)
zeigt eine Browseraufnahme ohne auslesbare Orbit-Daten, **keinen
nachgewiesenen Unity-Originalrender**. Die gelieferten Lightmap-JSONs
beschreiben Renderer-Indizes und UV-Offsets, nicht die komplette
Szenenbeleuchtung; die Bundle-Texturen allein ersetzen keine aufgelösten
Shader/Passes oder eine Szenenhierarchie mit externen Objekten.

| Vergleichsbereich | Geometrie in der Browserprobe | Was ohne Unity-Referenz offen bleibt |
| --- | --- | --- |
| −Z-Mitte, Dach an | Rang- und Unterbauteile; zwischen ihnen teils Hintergrund statt Außenhaut. | Ob die vollständige Unity-Szene zusätzliche Objekte lädt; wie Shader und Licht diese Teile erscheinen lassen. |
| −X und −X/−Z-Ecke, Dach aus | Rangstruktur und offene Sichtlinien; keine ergänzte Bestandswand. | Ob anderswo in der Unity-Szene eine abschließende Wand liegt. |
| +X, +Z und +X/−Z-Ecke | Die drei belegten `NoDraw_`-Flächen, hell vereinfacht dargestellt. | Tatsächlicher `NoDraw_`-Shader-Pass, Culling, Licht und endgültige Farbe. |

Für einen **gleichwinkligen Originalvergleich** benötigt man die vollständige
Unity-Szene (inklusive möglicher separat geladener Gebäude-/Prefab-Objekte),
ihre referenzierten Shader/Materialien, Texturen und Lightmaps samt Zuordnung
und Beleuchtung sowie einen Unity-Render der −X/−Z-Seite mit Kameraposition,
Zielpunkt, Projektion/Bildwinkel, Auflösung und Dach-/Sichtbarkeitszustand.
Eine zuordenbare Kameraaufnahme desselben Zustands in der Browserprobe
erlaubt dann den Abgleich von Geometrie, Material und Beleuchtung. Bis dahin
ist **keine fehlende Originalfassade nachgewiesen** und eine Farbangleichung
an das bisherige Browserbild wäre unbegründet. Beim Originalabgleich blieben
Produktiv- und Vergleichsgeometrie deshalb unverändert; die spätere,
ausdrücklich nicht als Original ausgegebene Rekonstruktion ist unten beschrieben.

## Später beauftragte Rekonstruktion der Gegenseite

Nach dem Originalabgleich wurde eine **sichtbar geschlossene und als
Rekonstruktion gekennzeichnete** Bestands-Gegenseite ausdrücklich freigegeben.
Diese Entscheidung ändert den Quellenbefund oben nicht: Die ergänzte Fläche
ist ein neutral eingefärbter, separat benannter Browser-Zusatz, **keine**
nachgewiesene Unity-Fassade. Es werden keine Fenster, Glasbänder oder
Originalmaterialien behauptet. Die exportierten Dreiecke, einschließlich der
drei `NoDraw_`-Flächen, bleiben unverändert und sichtbar.

Die ergänzte Hülle folgt der −X-Seite von Z +64,5 bis −64,3 m, führt über
den −X/−Z-Bogen zur −Z-Kante und schließt diese bis X +63,65 m bei
Z −116,54 m. Sie reicht vom Boden bis etwa 36,6 m. Nur unter der belegten
`right2_13.001`-Eckfläche (+X/−Z, Beginn Y 16,46 m) setzt sie die untere
Hülle bis X +94,4 m fort. Damit wird die originale obere Eckfläche weder
überzeichnet noch zur Rekonstruktion umgedeutet. Die Abmessungen sind
visuelle Annahmen für die Vorschau, keine vermessene Bestandsaufnahme.
Im Rundum-Konzept wird diese Ergänzung nicht gezeichnet.

Gleicher Preset „Gegenseite“ (Azimut −2,28 rad, Elevation 0,53 rad,
Distanz 490 m), 1440 × 900 Pixel: [vor der Ergänzung, Dach an](../screenshots/dortmund-bestandswaende-gegenseite-dach-on.png),
[Vergleich danach, Dach an](../screenshots/dortmund-rekonstruktion-gegenseite-dach-an.png),
[Vergleich danach, Dach aus](../screenshots/dortmund-rekonstruktion-gegenseite-dach-aus.png),
[gedrehter Eckblick ohne Dach](../screenshots/dortmund-rekonstruktion-gegenseite-ecke.png)
und [flacher Außenblick ohne Dach](../screenshots/dortmund-rekonstruktion-gegenseite-flach.png).
Die Vergleichsaufnahme enthält eine schematische OSM-Umgebung; die
[Editor-Szene mit Dach](../screenshots/dortmund-editor-rekonstruktion-gegenseite-dach-an.png)
und [ohne Dach](../screenshots/dortmund-editor-rekonstruktion-gegenseite-dach-aus.png)
zeigen dieselbe Fassadengeometrie ohne diese Umgebung. Der Editor-Nachweis
zeigt die produktive 3D-Szenenkomponente in einem isolierten Browser-Testbett,
nicht eine authentifizierte Aufnahme der kompletten Editoroberfläche.

## Farbangleichung in der Bestandsvorschau

Die originalen Außenwandmeshes `back2_1.001`, `left2_1.001` und
`right2_13.001` bleiben als `ORIGINAL_`-Objekte erhalten. Nur in der
Bestandsdarstellung erhalten sie ein separates Vorschaumaterial mit
dem Grundton `#737e7a` sowie derselben Rauheit und Metallizität wie
die rekonstruierte Wand. Schattierungen durch Licht bleiben möglich.
Beim Wechsel zum Rundum-Konzept stellt der Editor ihre bisherigen
hellen Quellvorschau-Materialien wieder her. Die Vergleichsansicht
trennt „Original“ und „Rundum“ ebenso. Dach, Sitzränge und übrige
Quellmaterialien sind nicht betroffen. `#e7e7e7` im Export bleibt der
aus gespeicherten NoDraw-Werten abgeleitete Wert; `#737e7a` ist eine
nutzergewünschte **Browserfarbe**, keine belegte Unity-Originalfarbe.

Gleiche Kamera „Gegenseite“ wie oben: [Vergleich nach der Farbangleichung
mit Dach](../screenshots/dortmund-farbangleichung-vergleich-dach-an.png)
und [ohne Dach](../screenshots/dortmund-farbangleichung-vergleich-dach-aus.png);
[Editor-Szene mit Dach](../screenshots/dortmund-farbangleichung-editor-dach-an.png)
und [ohne Dach](../screenshots/dortmund-farbangleichung-editor-dach-aus.png).
Der [flache Editor-Eckblick](../screenshots/dortmund-farbangleichung-editor-flach.png)
zeigt die Anschlüsse ohne Dach. Diese Aufnahmen stammen aus dem
Software-WebGL-Testbrowser; die Editor-Szene wurde wie zuvor isoliert
aufgenommen, nicht über einen angemeldeten Managerzugang.