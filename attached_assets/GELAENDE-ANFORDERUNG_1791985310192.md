# Geländeanschluss WWK ARENA (FMI 2238) — Befund an der Quelle und Anforderung an eine generische Renderer-Funktion

Status: **offen** — mit den verfügbaren Quellen ist kein belastbarer Anschluss ohne Renderer-Funktion möglich; das Paket liefert den Vorzustand (Kulisse ausgeschlossen, Umlauf steht über dem Umfeld) und diese Anforderung mit Vorher-/Zielbildern. Keine stillschweigende Bodenhöhenänderung, kein vereinsspezifischer Patch, keine anderen Stadien betroffen.

## 1 · Befund an der Quelle (`augsburg.bundle`, Modellkoordinaten, y = Höhe)
| Bauteil | Mesh | Hierarchie | Material | Bounds (x / y / z, m) | Funktion |
|---|---|---|---|---|---|
| Spielfeld | `st081_pitch_0/1` | PITCH2021 | 0002-Bayern, 000STADIUMLINE | ±37,9 / 0 / ±57,2; Linien ±34,1 / ±53,0 | Spielfeld bei **y 0** |
| Umlaufplatte | `center1_28` | MAIN/center1 | concrete_bare_01 | −76,0…77,8 / **7,70–7,72** / −96,7…97,5 (617 Dreiecke, mit Treppenöffnungen) | Umlauf zwischen Unter- und Oberrang = Eintrittsebene; äußerstes Bauteil des Stadionkörpers |
| Umlauftreppen | `center1_21` | MAIN/center1 | concrete_stair_tread | ±66,5 / 2,1–7,7 / ±86,9 (16 Dreiecke) | Treppen vom Umlauf hinab zur Unterrangebene |
| Außenwand Ost/Enden | `center1_4` | MAIN/center1 | concrete_bare_03 | −36,6…72,5 / **0,0–22,1** / ±92,6 | Außenwand, reicht bis zum Spielfeldniveau hinab (real unter Gelände) |
| Außenwand West unten | `center1_4.002` | MAIN/center1 | concrete_bare_03 | −66,5…−35,8 / 0,0–7,9 / ±86,9 | Sockelwand Haupttribüne |
| Außenwand oben | `center1_5` | MAIN/center1 | concrete_bare_01 | −76,0…72,5 / 7,7–22,1 / ±92,6 | Fassadenwand ab Umlaufniveau |
| Fassadenstützen | `front3_27`, `front3_27.001` | MAIN/center1, MAIN/front3 | concrete_bare_01 | ±72 / **7,7**–22,1 bzw. 26,2 / ±93 | Kolonnade, Fußpunkt auf Umlaufniveau |
| Rückwand Haupttribüne | `center1_4.001`, `center2_4.001`, `center2_1.001/1.002` | MAIN/front3 | concrete | −79,8…−33,8 / 7,7–22,1 / ±92,6 | Rückgebäude Haupttribüne, Fußpunkt 7,7 |
| Rangsubstruktur/Treppenhäuser | `center1_38/40/41/42/43` | MAIN/center1 | metal_galvanized | innerhalb der Tribünengrundrisse / 0–22 / … | innen, unter den Rängen |
| **Kulisse** Vorplatzplatten | `center2_1`, `center2_4` | MAIN/center2 | conc_cream, concrete_floor_brown | ±106…124 / **7,7** / ±129…135 bzw. ±97…102 / 7,7 / ±120…126 | Plaza-Platten, ausgeschlossen (hohe Kanten, verdecken OSM) |
| **Kulisse** Stadtboden/Wege/Bäume/Gebäude | `center2_0/2/3/5…10`, `new_tree01_color`, `simple_wood_cityskirt01_ctsk_color`, `tred_color`, `tree_oak_xquad_03_color`, `trees_skirt_b_color` | MAIN/center2 | … | bis ±417 / 7,7 (Boden) | ausgeschlossen |

Außerhalb der Umlaufplatte gibt es **kein** Stadionbauteil (Prüfung: alle Meshes außer Crowd/Dach; nur `center2_4.001` ragt 2 m über die Platte hinaus). Zwischen y 0 und 7,7 liegen außen nur die Sockelwände `center1_4`/`center1_4.002` — im Original durch die Kulissenplatten verdeckt, real unter Gelände. **Reale Lage:** „the playing field is 8 metres lower than the original terrain" (Titus Bernhard Architekten, architizer.com/projects/wwk-arena) — die Quelle (7,7 m) ist damit konsistent; Eingänge liegen real auf Vorplatzniveau = Umlauf.

## 2 · Vorzustand im Replit-Renderer
`dortmund_surroundings.js` legt den Umfeldboden fest auf **y −0,35** (`ENV_GROUND`), Straßen bei −0,12, Grün −0,18, Gebäude ab 0; keine Höhenfunktion („No terrain elevation is present in the 2D data: do not invent relief."). Folge nach Ausschluss der Kulisse: Umlaufplatte und Fassadenfußpunkte schweben 7,7 m über dem Umfeld, die Sockelwände 0…7,7 m sind sichtbar (Bilder `bilder/gelaende/vorher-*.png`, vier Seiten tief + Übergänge nah).

## 3 · Anforderung (generisch, optional, je Stadion deklariert)
Zwei optionale Felder in `presentation.surroundings` (nicht im Modellmanifest; Standardwerte = heutiges Verhalten, kein Stadion ändert sich ohne Deklaration):

```json
"surroundings": {
  "groundLevel": 7.7,
  "groundCutout": [[-43.9,-96.3],[-34.0,-96.7],[20.7,-96.7],[34.0,-96.7],[43.9,-96.3],[53.9,-92.4],[62.8,-86.9],[66.5,-83.2],[71.9,-74.9],[76.0,-65.4],[77.8,-54.9],[77.8,25.9],[77.8,54.9],[76.0,65.4],[71.9,74.9],[66.5,83.2],[62.8,86.9],[53.9,92.4],[43.8,96.3],[32.9,97.5],[2.2,97.5],[-2.2,97.5],[-32.9,97.5],[-43.9,96.3],[-53.9,92.4],[-62.8,86.9],[-66.5,83.2],[-71.9,74.9],[-74.7,65.0],[-75.5,54.4],[-76.0,-54.4],[-76.0,-65.4],[-71.9,-74.9],[-66.5,-83.1],[-62.8,-86.9],[-53.9,-92.4]]
}
```

- **`groundLevel`** (Meter, Standard 0): die gesamte Umfeldgruppe (`EDITOR_SURROUNDINGS_3D`: Boden, Grün, Wasser, Straßen, Gebäude, Bäume) wird um diesen Betrag angehoben (`group.position.y = groundLevel`). Spielfeld, Sitzpositionen, Kameras und Stadionmodell bleiben unverändert bei y 0 — ihre gemeinsame Lage ist nicht betroffen.
- **`groundCutout`** (Polygon in **Modellkoordinaten x,z**, Standard keins): der Umfeldboden erhält innerhalb des Polygons eine Aussparung (ShapeGeometry mit Loch; lokale Shape-Koordinaten `(x, −z)` wegen `rotation.x = −π/2`), und Umfeldflächen, die **vollständig** im Polygon liegen, entfallen (hier `bg.green[3]` = das OSM-Spielfeldpolygon way 181899832, x ±34 / z ±53 — sonst läge es nach dem Anheben als grüne Fläche über dem Spielfeld). Straßen/Gebäude mit Punkten im Polygon: hier keine (geprüft, 0 Treffer); Vorschlag: unverändert zeichnen und im Umfeldbericht melden.
- Quelle des Polygons: konvexe Hülle der Umlaufplatte `center1_28` (`quellbelege/gelaende_umlaufplatte.json`); innerhalb liegt ausschließlich Stadionkörper. Der Rand der Aussparung fällt mit der Plattenkante zusammen, Straßen/Parkflächen/Gebäude außerhalb werden weder verdeckt noch abgeschnitten (Bilder `bilder/gelaende/ziel-*.png`).
- Validierung (Registry/`validate_surroundings`-Analogon): `groundLevel` endlich, |h| ≤ 30; `groundCutout` ≥ 3 Punkte, endlich, keine Selbstüberschneidung; ohne `groundLevel` wird `groundCutout` ignoriert.
- Nicht Teil der Anforderung: Böschungen, Rampen oder Abdeckplatten — die Quelle enthält keine; der Übergang ist die Plattenkante (7,7 m) gegen den angehobenen Umfeldboden (7,35 m), 0,35 m Versatz wie bisher gegen das Spielfeld.

## 4 · Zielbild-Mock (nur Harness)
`werkzeuge/render/mock_gelaende/` = Kopie des Replit-Stands mit genau diesem Zusatz in `dortmund_surroundings.js` (Block „MOCK"); `unity_stadium_scene.js` unverändert (Diff-Nachweis). Aufruf `harness.html?r=mock_gelaende&p=presentation_ab_v2_mock.json`. **Kein Renderer-Patch für Replit**; die Umsetzung bleibt ein gesonderter Auftrag.

## 5 · Bilder
`bilder/gelaende/vorher-<ansicht>.png` (Replit-Renderer, Vorzustand) und `bilder/gelaende/ziel-<ansicht>.png` (Mock) aus identischen Kameras: `nord_tief`, `sued_tief`, `ost_tief`, `west_tief` (vier Seiten, el 10°, d 340), `editor`, `top`, `gegenseite`, Übergänge nah (`uebergang_nw`, `uebergang_so`, `uebergang_west_nah`, `uebergang_ost_nah`, d 190, el 6–8°); Gegenüberstellung `bilder/gelaende/vorher-ziel.jpg`.
