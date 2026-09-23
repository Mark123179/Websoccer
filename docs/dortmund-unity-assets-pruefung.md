# Dortmunder Unity-Assets: technische Prüfung

Stand: 23. September 2026. **Untersuchung, kein Import.** Weder `StadiumGeometry`/`StadiumDesign` noch die verbindliche Kapazität wurden verändert.

## Methode und Abgrenzung

Die gelieferten UnityFS-Dateien wurden mit **UnityPy 1.25.3** unter Python 3.12 geöffnet. Das 209.090.661-Byte-Dortmund-Bundle (Unity `6000.3.12f1`) ist bytegleich mit dem früher gelieferten Exemplar (SHA-256 `b626002f437097d92e914b93e7036257e63b9574c0d2a8f4fa8592407b2bad66`); nur ein Exemplar wurde ausgewertet. Die folgenden Meshdaten stammen aus **dekodierten Vertex-/Indexpuffern** (`MeshHandler.process()`), nicht aus Objektlisten oder dem Vorschau-Generator. Vier Stichproben wurden außerdem mit `UnityPy.export.MeshExporter.export_mesh` tatsächlich als OBJ nach `/tmp` exportiert (temporäre Analyse, kein produktiver Import). Vier Bildtexturen, darunter zwei Lightmaps, wurden tatsächlich per `Texture2D.image` dekodiert und als kleine PNG-Proben nach `/tmp` geschrieben. Die großen Binärdateien wurden nicht ins Webprojekt kopiert.

Nachvollziehbarer Kurzcheck:

```python
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler
from UnityPy.export.MeshExporter import export_mesh
env = UnityPy.load("attached_assets/dortmundv3_1790167703231.bundle")
mesh = next(o.read() for o in env.objects if o.type.name == "Mesh"
            and o.peek_name() == "center3_13.001")
handler = MeshHandler(mesh)
handler.process()
print(len(handler.m_Vertices), sum(map(len, handler.get_triangles())))
print(len(export_mesh(mesh).encode("utf-8")))
```

Ein vollständiger Import nach glTF/WebGL, Qualitätsvergleich im selben Kamerawinkel oder Lizenzprüfung der enthaltenen Shader/Texturen ist **nicht** durchgeführt. Insbesondere ist ein erfolgreiches OBJ noch kein fertiges Browser-Material.

## Tatsächlich ausgelesene Bestände

| Quelle | Geometrie, Oberflächen und Zweck |
| --- | --- |
| `dortmundv3_1790167703231.bundle` (200 MiB) | 10.418 Unity-Objekte: **681 Meshes**, 681 MeshRenderer, 472 Materials, **912 Texture2D**, 2.044 GameObjects/Transforms, 6 Cubemaps, 6 ReflectionProbes, 863 Light-Objekte. Summe Mesh-Metadaten: **1.364.438 Vertices**, **1.078.584 Dreiecke**, ca. **78,5 MB Vertexpuffer** plus **6,47 MB Indexpuffer** vor Web-Konvertierung. Alle 681 Mesh-Vertexdaten lagen im Bundle, kein externer Mesh-Stream. Diese Summen umfassen auch Requisiten/Crowd-Flächen, nicht nur die bauliche Hülle; sie sind keine deduplizierte Browser-Szene. |
| `Bleacher_1790167741678.bundle` (483 KiB) | Tatsächliches Sitzmodell `MESH_Chair_Stadium` mit 148 Vertices, ein Material `audi_high`, zwei 1024²-Texturen (`weatheredNormalMap`, Plastikoberfläche); **kein zweites Stadion**. Als instanziertes Sitzmodell denkbar, nicht 71.659 separat geladene Meshes. |
| `lighting_1790167741677.bundle` (41 MiB) | 31 Light-Objekte, 6 Cubemaps, 12 Texture2D, 36 GameObjects, **kein Mesh**. Beleuchtungs-/Atmosphäre-Assets, nicht die Stadionhülle. |
| `skybox_1790167741678.bundle` (278 MiB; Unity `6000.0.52f1`) | 70 Materialien, 108 Texture2D, 46 Cubemaps, **kein Mesh**; Himmel-/Reflexionsauswahl, nicht Stadiongeometrie. |
| `weather_1790167741677.bundle` (3,6 MiB) | 6 Partikelsysteme, 6 Materialien und 6 Texture2D (u. a. Regen/Schnee), **kein Mesh**; Wettereffekte. |
| Begleit-DLLs (`SeatInject`, `StadiumInjection`, `LightingInject`) | Mono/.NET-Unity-Plugins; keine unmittelbar ausführbaren Browser-Assets und hier nicht ausgeführt. |

Unter den 912 Dortmund-Texturen liegen **292 echte Lightmap-Bildobjekte** (`Lightmap-0…145_comp_light` und `…_comp_dir`, jeweils 512 × 512) vor. Die übrigen sind Oberflächen-/Hilfstexturen. Unity-Formate: 637 × DXT5, 146 × BC6H, 116 × DXT1, 10 × BC7 und je ein RGB24, RGBA32, DXT5Crunched. Häufige Abmessungen: 412 × 512², 139 × 1024², 100 × 256²; 15 Texturen mit 2048². **Das separate** `dortmundv3_lightmaps_1790167703232.json` enthält dagegen nur 681 Renderer-Pfade, UV-Scale/Offset und 146 Indizes, **keine Bildpixel**. Die Stichprobe `Lightmap-50_comp_dir` wurde als 512²-RGBA-Bild aus dem im Bundle referenzierten `.resS`-Stream dekodiert (Pixel [0,0] = 96/166/38/216 vor PNG-Verkleinerung); `Lightmap-50_comp_light` ebenfalls. Die Renderer-Stichproben im Bundle melden `m_LightmapIndex=65535`, während das externe JSON gültige Indizes enthält: Die Zuordnung muss beim Konverter ausdrücklich aus JSON und Bundle-Texturen gemeinsam rekonstruiert und visuell geprüft werden. BC6H-HDR- und gerichtete Lightmaps brauchen eine eigene WebGL-kompatible Umsetzung; bloßes PNG-Exportieren bewahrt die Unity-Beleuchtung nicht automatisch.

`dortmundv3_lightprobes_1790167703230.json` enthält **140 Positionen mit SH-Koeffizienten** für indirektes Licht, keine Bildkarten und keine Meshes. Seine Verwendung in Three.js ist eine gesonderte Shader-/Lighting-Aufgabe.

## Geometrische Stichprobe und Sitzabgleich

Die Namen der Objekte werden über `GameObject → MeshFilter → Mesh`, `MeshRenderer → Material → Texture2D` aufgelöst. Lokale Unity-Meshkoordinaten sind `(x, y=Höhe, z)`; sowohl `AUDIAREA` als auch `SCARECROW` tragen eine Quaternion für **180° um Y** (x und z wechseln im Weltkoordinatensystem das Vorzeichen). OBJ-Export von UnityPy spiegelt zusätzlich x für das OBJ-Handedness-Format; dessen Zahlen dürfen daher nicht ohne Hierarchie/Koordinatenwechsel mit dem JSON verglichen werden. Die folgenden Grenzen sind **lokale dekodierte Vertexkoordinaten**, vor der 180°-Drehung.

| Objekt/Mesh | Auszug aus echter Geometrie und Verknüpfungen |
| --- | --- |
| `AUDIAREA/MESH_CROWD/C_back1_C1-HardcoreHome` | `C_back1_C1-HardcoreHome.001`: 4.235 Vertices, 5.346 Dreiecke, UVs; x **13,50…63,00**, y **1,27…18,13**, z **−74,58…−41,27**. Material `audi_seat_mat` → tatsächliche 512²-DXT1-Textur `au_seat` (dekodiert). Nach 180°-Drehung liegt die Fläche bei x −63…−13,5 und z 41,27…74,58. Die **3.401** JSON-Sitze derselben Sektion liegen bei x **−62,6…−13,8**, y **1,4…17,9**, z **41,7…74,1**. Räumliche Zuordnung damit auf Sektionsebene bestätigt, ohne die Mesh-Vertices mit Sitzzentren gleichzusetzen. |
| `AUDIAREA/MESH_CROWD/C_back2_C1-HardcoreHome` | 2.152 Vertices, 3.402 Dreiecke; lokale x 15,75…63,50, y 19,88…36,69, z −92,75…−70,38. Nach derselben Drehung entspricht das den **2.739** JSON-Sitzen des Oberrangs (x −63,1…−16,0, y 20,1…36,6, z 70,7…92,7). |
| `SCARECROW/…/st051_sc2018_back_stand_8` | 4.752 Vertices, 5.408 Dreiecke, UVs; lokale x −62,40…61,33, y 1,68…3,59, z −45,60…−41,03. Material `m_st_coat_band.001` verweist nachweisbar auf `st_coat_band_2018Sig_bsm` plus Roughness-, Normal- und Specular-Texturen. Repräsentativer baulicher Streifen am Unterrang (nach Drehung z +41,03…+45,60). |
| `center3_13` / `.001` | 40.268 Vertices, 19.996 Dreiecke; x −115,80…119,06, y **28,29…43,09**, z −93,19…93,14; Dach-/Innenstruktur. Material `st051_irpl003_NC.006` verweist u. a. auf `st051_irpl003_bsm` (dekodierte 1024²-DXT5-Textur, gelblich). Allein dieser OBJ-Export belegt **4.116.287 Bytes**, ohne produktive Texturen/Materialkonvertierung. `center3_14` deckt mit 32.630 Vertices/16.036 Dreiecken ähnliche Maße ab. |
| `center3_21` / `.001` | 608 Vertices, 424 Dreiecke; x −133,57…137,07, y **34,33…68,73**, z −111,16…111,20. Material `st051_pllr001_NC.001` mit Basecolor-/Normal-/Specular-Texturen; hohe äußere Träger/Pylone, nicht bloß Dachfläche. |

Die Sitzdatei enthält **71.659 Einträge in 25 benannten Sektionen**. Alle 25 Namen tauchen als `AUDIAREA/MESH_CROWD/C_…`-Rendererpfade im separaten Lightmap-Index auf. Die räumliche Gruppierung der Sitzdaten korrespondiert mit den gleichnamigen extrahierten `C_…`-Crowd-Meshes; für zwei der Gruppen sind oben die dekodierten Vertexgrenzen ausdrücklich gegen die Sitze geprüft:

| Gleichnamige Crowd-/Sitzbereiche | Sektionen | JSON-Sitze | Lage in Unity-Weltkoordinaten nach Hierarchiedrehung |
| --- | ---: | ---: | --- |
| `C_back1_…` / `C_back2_…` | 3 / 4 | 8.645 / 12.494 | z positiv, Unterrang / Oberrang |
| `C_front1_…` / `C_front2_…` | 3 / 4 | 8.014 / 12.494 | z negativ, Unterrang / Oberrang |
| `C_left1_…` / `C_left2_…` | 1 / 2 | 6.466 / 8.141 | x negativ, Unterrang / Oberrang |
| `C_right1_…` / `C_right2_…` | 3 / 5 | 3.827 / 11.578 | x positiv, Unterrang / Oberrang |

`…1` liegt überwiegend bei y bis etwa 18 m, `…2` bei etwa 13–37 m. Die Pfadzuordnung für alle 25 Sektionen ist nachgewiesen; ein **punktweiser** Sitz-zu-Mesh-Test aller 25 ist nicht erbracht. Insbesondere ist ein `MESH_CROWD`-Flächenmesh weder die exakte Stuhlgeometrie noch ein Ersatz für `Stadium.capacity_total`. Die tatsächliche Wirtschafts-Kapazität bleibt das DB-Feld.

## Vergleich zur bestehenden Vorschau und den zwei Dortmund-Bildern

Die vorhandene `/stadion/dortmund/vorschau/` verwendet **120 modellierte Blöcke und 60 Dachsegmente** aus der separaten ZIP-Szene; ein prozeduraler geschlossener Ring wird für WebGL verwendet (Dach außen 41,03 m, innen 39,53 m, acht abstrahierte gelbe Pylone). Sie verwendet **keines** der hier extrahierten Unity-Meshes/Materialien. Der Größenbereich der äußeren Ringkontur (~±117 m in x, ~±97 m in z) und die Ränge bis ~36,6 m passen grob zu den realen Sitz-/Meshdaten. Das ist eine **Maßstabsplausibilität**, kein deckungsgleicher Silhouettenvergleich.

In `image_1790168106616.png` (Abend) und `image_1790168124756.png` (Tag) sind gelbe äußere Pylone, filigrane dreieckige Dachträger, die stark belegten zweistöckigen Tribünen, Gänge/Unterbrechungen, Banner und die breite Dachöffnung sichtbar. Die extrahierten `center3`-Meshbereiche reichen von der Dachzone bis 68,73 m und enthalten echte Details, welche die Vorschau mit flachem Ring und vereinfachten Pylonen nicht nachzeichnet; `back_stand` und `C_back1` belegen Unterrang-Streifen und Belegungsflächen. Einzelne visuelle Bauteile (z. B. die exakte Trägerfolge und farbige Banden) wurden **nicht** anhand einer aus allen Meshes gerenderten Ansicht eindeutig auf konkrete Mesh-IDs zurückgeführt. Crowd-Texturflächen sind auch nicht dasselbe wie 71.659 sichtbare einzelne Zuschauer. Die vom Nutzer gemeldete Verdeckung der Matchkamera durch das bestehende Dach bleibt ein eigenständiger Fehler der Vorschau, nicht durch diese Extraktion behoben.

## Browserkosten und Entscheidung

Der unveränderte Dortmund-UnityFS-Download ist schon **200 MiB**; zusammen mit Skybox und Lighting wären es ~519 MiB, bevor eine Web-App darüber verfügt. Vertex-/Indexpuffer allein sind ~85 MB und 1,08 Mio. Dreiecke; Materialvarianten, 912 Texturen und 292 Lightmap-Bilder treiben Bandbreite, Speicher und Draw-Calls weiter. Nicht alle Assets müssen in einer Browseransicht geladen werden: Gebäude-/Dach-Meshes auswählen und in glTF/GLB mit passenden Achsen/UVs konvertieren, Oberflächen atlasiert/reduziert bereitstellen, LOD/Culling vorsehen, Sitzmodell GPU-instanzieren und nur benötigte Lichtkarten dekodieren. Eine konkret erreichbare GLB-Größe oder Bildrate ist **noch nicht gemessen**; 200 MiB nicht als verbindliche Browsergröße ausgeben. Unity-Material-/Shader-Semantik, ReflectionProbes und Lightmap-UVs benötigen eine separate Übersetzung. Der große Bundle-Parse benötigte in dieser Umgebung etwa 19 s und ~1,7 GiB maximalen Prozessspeicher; daher Konvertierung offline, nicht pro Webanfrage.

| Weg | Gewinn | Risiko |
| --- | --- | --- |
| **Bestehenden Editor gezielt erweitern** | Gespeicherte 120-Block-Designs und bestehendes Kapazitäts-/RLE-Modell bleiben ohne Migration verwendbar; Dachkamera-Fehler separat behebbar. | Echte `center3`-Träger, Fassaden, Gänge und Materialdetails wären nur mit vielen neuen parametrischen Sonderfällen angenähert. Trotz Mehrarbeit keine Garantie für Übereinstimmung mit den Screenshots. |
| **Neue geometrische Stadionbasis, Editor als Designschicht** (**Empfehlung für einen separaten Prototyp**) | Echte extrahierte Hülle/Dachträger mit korrekten Sitzsektionen als feste Darstellung; Design-Layer steuert Farbe/Belegung/Branding, DB-Kapazität bleibt maßgeblich. | Block-IDs und RLE-Zellen der bestehenden Managerdesigns passen nicht 1:1 zu Unity-Meshes: explizites Mapping/Backup und Nutzerfreigabe erforderlich. Konvertierung, Rechteprüfung, LOD, UV-/Lightmap-Mapping und mobile Performance müssen erst in einer kleinen browserfähigen Probe nachgewiesen werden. |

**Empfehlung:** Nicht den bestehenden Editor auf Verdacht weiter verfeinern oder gespeicherte Designs umstellen. Wenn Stadiontreue Vorrang hat, zunächst **schreibgeschützt** nur ein Unterrang-/Oberrang-Segment, den benachbarten Dachträger und wenige Texturen als browserfähige Testszene konvertieren, Achsen/UVs und Tages-/Nachtbeleuchtung aus identischer Kamera gegen beide Referenzbilder prüfen sowie Ladegröße/FPS messen. Danach kann der Nutzer über neue Basis versus bestehendem Editor entscheiden. Bis dahin bleibt die bestehende Vorschau unabhängig, kein Import überschreibt gespeicherte Stadien.