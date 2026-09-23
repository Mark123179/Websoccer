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

Im Browser landen eine 16,9-MiB-Binärdatei, ein ~92-KiB-Manifest und vier
verkleinerte WebP-Texturen (zusammen unter 40 KiB), **nicht** das 200-MiB-Bundle.
Die Geometrie ist nicht als allgemeines glTF versprochen; das Format
`unity-mesh-binary-v1` ist nur für diese isolierte Probe. Im WebGL-Modus wird
je selektiertem Mesh ein Draw-Objekt mit UVs und vereinfachtem Material
angelegt. `python scripts/render_dortmund_miniature_2d.py` rendert dieselben
extrahierten Dreiecke als statischen CPU-Z-Buffer-Fallback. Dieser hat keinen
Orbit/Zoom; er erlaubt aber den Vorher/Nachher- und Dachhautvergleich ohne WebGL.

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
**rückwärtigen Oberrang-Sitze** in x −108,33…104,53, y 13,0…36,63 und
z 58,06…92,66. Die gleichnamigen Crowd-Meshes sitzen sektional dort
(siehe `dortmund-unity-assets-pruefung.md`). Der exportierte Stadionschüssel-
Längsverlauf ist also **z**, Querrichtung **x**. Der OSM-abgeleitete
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

Die *rückwärtige* Seite (+z, hinter einem Tor) erhält 18 neue Stufen ab
der gemessenen Oberrang-Kante z=92,661/y=36,6251. Die zusätzlichen
Sitzmarker sind instanziierte Vorschau-Boxen mit drei durchgehenden Gängen,
keine erfundenen alten Unity-Sitze und keine Änderung der Wirtschaftskapazität.
Zwei keilförmige Eckbrücken schließen an die Seitenkontur an. Eine neue
Außenwand mit Fassadenfeldern und Stützen sowie eine erhöhte Dachfortsetzung
mit Rippen/Querstreben schließen geometrisch an die alte Dachaußenkante an.
„Ohne Dachhaut“ entfernt **nur die neue Dachfläche** und zeigt Reihen und
Tragwerk, ohne eine Sitz- oder Innenkamera zu verwenden. Die 2D-Bilder der
ersten beiden Zustände teilen dieselbe Kamera; der offene Technikblick ist
zusätzlich höher fotografiert, damit die neuen Sitzreihen sichtbar sind.

Das ist eine **modellierte Ergänzung** auf einer nachweisbar extrahierten
Originalbasis, keine aus dem Unity-Bundle gefundene fertige Ausbaustufe.
Der vorhandene zusammenhängende Dachkranz und die Pylone sind fest:
Für einen *produktiven* Umbau müsste man die betroffenen `center3`-Dach-
und Pylonmeshes an Bauteil-/Sektorgrenzen teilen, feste und bewegliche
Teile markieren, Lichtkarten neu erzeugen und die Ecke samt Fassaden-
Anschluss detailliert konstruieren. Hier überlappt der neue Dachansatz
die Bestandskante; Materialfugen und Tragwerksanschlüsse sind nicht
statikgerecht nachgewiesen. Andere drei Seiten besitzen zwar
entsprechende `front/left/right`-Unter-/Oberrangmeshes, ihre
Crowd-Sektionen, Dachanschlüsse und Fassadenmodule sind unterschiedlich;
eine kopierte +z-Erweiterung wäre dort falsch. Deshalb erfolgt
**kein Editorwechsel und keine Aktivierung** ohne Nutzerentscheidung.

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