# Isolierte Dortmunder Original-Miniatur – Prüfstand

URL: `/stadion/dortmund/original-miniatur/`. Der bestehende Editor, die frühere
prozedurale Vorschau und alle gespeicherten Stadiondaten bleiben unverändert.
Die Route beantwortet ausschließlich GET und liest keine Stadionzeile aus der
Datenbank. Der Schalter wechselt nur lokale Darstellungsgruppen im Browser.

## Quellen, Reduktion und Reproduzierbarkeit

`python scripts/export_dortmund_miniature.py` dekodiert das gelieferte
`dortmundv3_1790167703231.bundle` **offline** mit UnityPy 1.25.3. Es exportiert
319 benannte Meshes (454.366 Dreiecke): Tribünenkomponenten `back/front/left/right
1/2`, alle `center3`-Dach-/Trägerteile, 25 Crowd-Sektionsflächen,
23 Tribünenstreifen und zwei Spielfeldflächen. Das Manifest hält je Bauteil
Meshname, Unity-Path-ID, GameObject-Hierarchie, Materialnamen und
Vertex-/Indexoffsets fest. Selektiert werden die vier tatsächlichen
Basecolor-Texturen `au_seat`, `st051_irpl003_bsm`,
`st051_pllr001_bsm` und `st_coat_band_2018Sig_bsm`. Die übrigen der
283 vorkommenden Materialnamen erhalten nur eine kategorische Vorschaufarbe.
Shader, Transparenz, Normalmaps, Reflection Probes und Lightmaps (die eigene
Zuordnung benötigt weitere Auswertung) wurden **nicht** als originalgetreu
übernommen. Die Crowd-Meshes sind texturierte Flächen und nicht 71.659
individuelle Stuhlmodelle.

`NoDraw_`-Materialteile bleiben im Export nachweisbar und werden anhand
der gespeicherten deckenden Materialkonfiguration in neutralem Farbton
gezeichnet. Die genaue Shaderwirkung in Unity ist nicht geklärt. Der
gleiche Vorschauvertrag gilt im produktiven Editor und im freigegebenen Vergleich. Befund mit
Koordinaten und Renderer-Eigenschaften:
[`dortmund-bestand-quellpruefung.md`](dortmund-bestand-quellpruefung.md).

Im Browser landen eine 16,9-MiB-Binärdatei, ein ~92-KiB-Manifest und vier
verkleinerte WebP-Texturen (zusammen unter 40 KiB), **nicht** das 200-MiB-Bundle.
Die Geometrie ist nicht als allgemeines glTF versprochen; das Format
`unity-mesh-binary-v1` ist nur für diese isolierte Probe. Im WebGL-Modus wird
je selektiertem Mesh ein Draw-Objekt mit UVs und vereinfachtem Material
angelegt. `python scripts/render_dortmund_miniature_2d.py` rendert den
Originalzustand aus denselben Dreiecken als statischen CPU-Z-Buffer-Fallback.
Dieses ältere Standbild kann die ungeklärte `NoDraw_`-Materiallage nicht
verlässlich wiedergeben und ist **kein Unity-Vergleichsrender**.
Es hat keinen Orbit/Zoom. Ausbauzustände werden stattdessen im Browser
als dynamischer, maßbasierter Dachgrundriss mit vier unabhängigen Seiten
gezeigt; ältere Ausbau-Standbilder werden nicht mehr verwendet.

## Maß und Abgleich

Unity-Meshpositionen sind in Metern (x, y=hoch, z). Eltern-Quaternionen
werden beim Offline-Export gebacken; besonders `AUDIAREA` hat eine
180°-Y-Drehung, `MAIN` und `PITCH2021` jeweils eine 90°-Drehung.
Die exportierten Bounds in der gemeinsamen Unity-Weltachse:

| Teil | x | Höhe y | z |
| --- | --- | --- | --- |
| `st081_pitch_0` Spielfeldfläche | −37,9…37,9 | ~0 | −57,2…57,2 |
| `center3_13.001` Dach-/Innenstruktur | −93,14…93,19 | 28,29…43,09 | −115,8…119,06 |
| `center3_21.001` Pylone | −111,2…111,16 | 34,33…68,73 | −133,57…137,07 |

Die Sitzquelle `dortmundv3_1790167703232.json` verortet die
**rückwärtigen Oberrang-Sitze im noch ungedrehten Sitz-Datei-Rahmen** bei
x −108,33…104,53, y 13,0…36,63 und z 58,06…92,66. Gegen die tatsächlich
exportierten Crowd-Meshes zeigt sich eine wichtige Korrektur: Deren rückwärtige
Sektionen liegen bei **x 57,62…92,96 und z −105,07…108,76**. Die Sitzdatei
muss deshalb in den Mesh-Rahmen gedreht werden: `(x,y,z) → (z,y,−x)`.
Der Stadion-Längsverlauf der Meshes ist **z**, aber die rückwärtige
Tribüne aus der Sitzdatei liegt im exportierten Mesh-Rahmen an **+x**.
Die Sitzvorlagen der Ausbauprobe werden vor Verwendung gedreht.
Der OSM-abgeleitete
V2-Grundriss (`blueprints/v2/dortmund.json` → `bvb_v2.json`) bezeichnet
die Längsachse als x und die Querachse als y; er hat Tribünen-Bounds
Längs −116,6…123,0 und quer −96,2…97,2 m. Das Unity-Dach `center3_13`
ist quer etwa ±93 und längs −116…119 m: Größenordnung und Achsen sind
plausibel, aber es wurde **keine millimetergenaue georeferenzierte
OSM-Registrierung** nachgewiesen. Die Unity-Pylone liegen erwartbar
außerhalb dieser Tribünengrenze. Insbesondere die Unity-Spielfeldfläche
114,4 × 75,8 m umfasst mehr als die 105 × 68 m des V2-Spielfeldvertrags;
sie wird nicht auf OSM-Maße verzerrt.

## Ausbauprobe und Grenzen

Die vorherige Variante mit 18 angesetzten Stufen, Dachplatte und Außenwand
war keine überzeugende Verbindung mit dem Originalstadion und ist aus der
interaktiven Probe entfernt. Der aktuelle Prototyp verwendet für **alle vier
Seiten** einen gemeinsamen, stetigen Verformungsverlauf über die
Original-Vertices. Die Binärdatei bleibt unverändert; die abgeleitete
Geometrie wird im Browser aus ihr berechnet. Dadurch verändern sich
die oberen Strukturteile, Dachkranz, Träger und zugehörige Fassadenteile.
In den Ecken wirkt derselbe Verlauf aus beiden Nachbarseiten auf jeden
Originalvertex; es wird keine eigene schwebende Dachplatte angesetzt.
Die Pylone werden ebenfalls verformt; ihre realen Ankerpunkte an anderen
Bauteilen sind nicht als statisch geprüft. Die besetzten Crowd-Flächen
bleiben unverformt: Ihre äußersten Sitzreihen verankern neue, in Abschnitten
verbundene Rangflächen. Die nur aus diesen gemessenen Reihen abgeleiteten
Zusatzplätze beginnen **außerhalb** der bereits belegten Ursprungsreihe und
verwenden das 148-Vertex-Stuhlmesh aus dem Bleacher-Bundle (nicht Boxen).
Bestehende Zugänge und Sektionslücken der Quellreihe bleiben erhalten.

`python scripts/build_dortmund_expansion_data.py` erstellt das rund 124-KiB
große Messmanifest aus der Sitzdatei, dem exportierten Dach-/Pylonmesh und
dem Originalstuhl. Ein Schritt umfasst jeweils ganze gemessene Reihen, also
mindestens 1.000 und ggf. etwas mehr zusätzliche **modellierte** Plätze:
Rückseite 5 × 248 = 1.240; Vorderseite 5 × 248 = 1.240;
linke Seite 11 × 94 = 1.034; rechte Seite 3 × 380 = 1.140.
Die Ausgangszahl 71.659 entstammt den Sitzpositionen der Quelldatei,
**nicht** der maßgeblichen Wirtschaftskapazität des Stadions.

Die Dachaußenkante und die äußeren Pylone haben je Seite nur rund 18 m
radialen Abstand. Mit 4 m Sicherheitsabstand und 0,91 m Reihentiefe
begrenzt der Prototyp jede Seite auf **15 zusätzliche Reihen**.
Aufgrund der ganzzahligen Schritte ergibt das derzeit maximal
**85.833 modellierte Plätze**, also **nicht** 120.000. 120.000 bleibt eine
zusätzliche globale Obergrenze, aber diese Version kann sie mit dem
vorhandenen Dach/Pylon-Fußabdruck nicht erreichen. Für mehr wäre ein
grundlegend neu abgestützter Dach-/Pylonaufbau oder ein zusätzlicher Rang
nötig; das ist aus den Originalmeshes nicht nachgewiesen und wird hier
nicht behauptet. Selbst unterhalb dieser Grenze sind Statik, Sichtlinien,
Fluchtwege, Materialdehnung und der Anschluss einzelner Fassadenteile
nicht bautechnisch abgenommen. Die Probe ist daher weiterhin **kein
produktiver Ausbau**. Elversberg bleibt ohne Originaldaten außen vor.

Ohne WebGL zeigt der Originalzustand weiterhin die CPU-Projektion aus
Originaldreiecken. Für beliebige Kombinationen der vier Ausbaustände zeigt
die Ersatzansicht einen ausdrücklich als solchen beschriebenen,
maßbasierten 2D-Dachgrundriss statt fälschlich ein altes Standbild der
früheren Ausbauprobe. Für einen produktiven Wechsel wären UV/Lightmap-
Neuerzeugung und ein stadienspezifischer Mesh-/Sitzeditor nötig.
**Kein Editorwechsel und keine Aktivierung** ohne Nutzerentscheidung.

## Prüfstand

- Die isolierte Route liefert HTTP 200, die Binärdatei wird als statisches
  Asset ausgeliefert und alle Indizes liegen innerhalb ihrer Mesh-Vertices.
- Der normale Screenshot-Browser konnte keinen WebGL-Kontext aufbauen
  (Chromium: `BindToCurrentSequence failed`); die berechnete 2D-Ansicht
  wurde dort sichtbar geprüft. Mit `--enable-unsafe-swiftshader
  --use-gl=angle --use-angle=swiftshader` waren Original- und Ausbauzustand
  als 3D-Screenshots sichtbar. Dieser **Software**-Renderer zeigte bei
  1280×900 etwa 1 fps und ist kein GPU-Desktop-Benchmark.
  Ein 430×900-Chromium-Fenster ohne GPU zeigte die 2D-Ansicht. Die
  WebGL-Ansicht meldet ihre FPS; auf schmalen Geräten wechselt sie nach
  zwei aufeinanderfolgenden langsamen Messfenstern in den 2D-Modus.
  Echte GPU-Desktop- und Mobil-Leistungswerte sind **nicht abgenommen**.
- Die Referenzbilder zeigen stärkere Farbdifferenzierung, Banden und
  Lichtwirkung als die reduzierte Probe; ohne alle Material- und
  Lightmap-Zuordnungen ist der Eindruck bewusst weniger originalgetreu.