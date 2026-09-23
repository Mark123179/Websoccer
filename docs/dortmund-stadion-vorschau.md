# Signal Iduna Park — prüfbare Vorschau

**Aufruf:** `/stadion/dortmund/vorschau/` (Link zur bisherigen Ansicht oben links).
Die Vorschau liest ausschließlich die geprüfte Szene `scenes/bvb_v2.json` aus
`attached_assets/stadium_stage_replit_paket_1790159390136.zip`. Sie schreibt weder
`StadiumGeometry` noch `StadiumDesign`; der normale Live-Modus bleibt unverändert.
Fehlt die ZIP-Datei oder ändert sich ihr SHA-256 für diese Szene, erscheint ein
expliziter Fehler statt einer stillen Rückkehr zur alten Geometrie.

## Quellen und Entscheidungen

- Die jüngere ZIP-Szene liefert 120 unterschiedliche Blöcke, Unter- und Oberrang
  auf allen Seiten, 60 Dachsegmente sowie einen gesonderten geschlossenen
  Dachkranz mit achteckiger Feldöffnung. Die Maße im ZIP-Steckbrief stammen aus
  dem gelieferten Sitzdatensatz; die Südtribüne hat in dieser Fassung **auch
  einen Oberrang**. Der ältere eingecheckte BVB-V2-Generator hat lediglich
  die vereinfachte Einrang-Südtribüne und getrennte Dachplatten. Deshalb wurde
  weder sein geprüfter Referenz-JSON noch sein Importpfad still ersetzt.
- Die zwei gelieferten UnityFS-Bundles sind bytegleich (SHA-256
  `b626002f437097d92e914b93e7036257e63b9574c0d2a8f4fa8592407b2bad66`),
  je 209 MB. Hier gibt es keinen UnityFS-Extractor; Mesh-, Material- und
  Lightmap-Pixel lassen sich deshalb nicht sicher auslesen oder performant
  als Browser-Assets ausliefern. Die Objektliste (681 Renderer) enthält Namen,
  aber keine Geometrie. Lightmap-JSON (146 Karten) enthält Zuordnungen, nicht
  die Texturpixel; die 140 Lightprobes enthalten Positionen/SH-Koeffizienten,
  jedoch keine zugehörigen Renderer-Meshes. Keine der Dateien wird ignoriert
  wegen ihrer Herkunft, sondern wegen der fehlenden ausführbaren Asset-Kette.
- Der separate Sitzdatensatz hat 71.659 generierte Unity-Sitze mit Y als Höhe,
  X/Z als Grundriss und Rotationen; er wurde zur Maßableitung genutzt, **nicht**
  als wirtschaftliche Kapazität oder als 71.659 Einzelobjekte im Browser.
  Das physische Raster der Szene hat 86.690 Zellen; die verbindliche Zahl
  kommt weiterhin ausschließlich aus `Stadium.capacity_total` (hier 81.365).
  Eine spätere direkte Unity-Übernahme müsste Achs-/Yaw-Umrechnung an einem
  eindeutig identifizierten Block prüfen und die Daten instanziert laden.

## Visueller Vergleich

Verglichen bei gleicher Standardkamera: die bisherige Dortmunder Live-Ansicht,
die neue Vorschau und `out/bvb_ref_views.png`, `out/bvb_blockplan.png` sowie
`attached_assets/dortmund_ringdach_1790159390137.png`. Im 3D-Browser wurden
Orbit und Sitz jeweils am Tag und nachts (mit Flutlicht) geöffnet.

| Ansicht | Beobachtung |
| --- | --- |
| Orbit außen | Die alte Version zeigt einzelne helle Platten mit sichtbaren Fugen; die Vorschau hat den geschlossenen, dunkelgrauen Dachring mit Feldöffnung und acht gelben Pylonen wie das Ringdach-Bild. Die Seitenblöcke sind anders unterteilt. |
| Sitz innen | Zwei unterschiedlich geneigte Ränge und die schmale umlaufende Dachöffnung sind sichtbar. Die Frontdetails und das exakte Vereinsmotiv der alten Managergestaltung erscheinen nicht, weil die neue Vorschau bewusst das gelieferte Standardmuster benutzt und keine alten RLE-Zellen auf neue Blöcke projiziert. |
| Tag/Nacht | Stadionkörper und Dach sind bei Tag erkennbar; die Pylone, Sitzfarben, Spielfeld und Dachkontur bleiben nachts unterscheidbar. Der Gelbton der Sitzschalen ist absichtlich browserseitig stabil. |

Die Vorlage ist ein schematischer OSM-/Sitzdatenabgleich, **kein** vollständiges
Unity-Mesh. Fassadendetails, Treppen, Werbeflächen, Bewehrung, originale
Lightmaps/Reflexionen und exakte Sitzreihen-Unterbrechungen fehlen. Außerdem
weicht die bisher gespeicherte Managergrafik sichtbar vom gelben
Standardmuster ab. Der 2D-Rückfall bei fehlendem WebGL zeigt nur eine
vereinfachte Ansicht, nicht die acht Pylone oder eine echte Sitzkamera.

## Validierung und spätere Übernahme

Die Vorschautests prüfen eindeutige Block-/Dach-IDs, gültige Quads, positive
Höhen, vollständige RLE-Ströme, eine gültige geschlossene Dachöffnung außerhalb
des 105 × 68-m-Felds, acht Pylone, die DB-Kapazität im Endpoint und das
unveränderte Persistenzpaar. Der Renderer bevorzugt `roof.ring`, ansonsten
bleiben die bisherigen expliziten Dachsegmente in Benutzung. Der Kranz fällt
von 41,03 m außen auf 39,53 m innen ab; die 1,2-m-Innenblende endet bei
38,33 m. Ein eigener Renderer-Vertragstest prüft diese Höhen, und im
WebGL-Browser wurden beide Mesh-Kanten nachgemessen. N-eckige
Referenzsegmente akzeptiert nur diese Ringdach-Vorschau (wo der geschlossene
Kranz statt der Segmente gerendert wird), nicht der generelle Einzelplattenpfad.

**Noch nicht importieren:** `import_stadium_blueprint_v2 --club-id 3 --apply
--confirm` importiert *die alte* eingecheckte V2-Referenz und setzt das
gespeicherte Design zurück. Das wäre nicht die hier gezeigte Vorschau.
Erst nach ausdrücklicher Sichtfreigabe:

1. Das aktuelle `StadiumGeometry`- und `StadiumDesign`-Paar mitsamt Steckbrief,
   Schema, Quelle und Blickrichtung sichern (der vorhandene V2-Importer zeigt
   das Backupformat und erzeugt vor seinem Schreibschritt eine Datei mit
   exklusivem Dateinamen und Modus `0600`).
2. Die neue ZIP-Szene zu einer geprüften Importreferenz machen; n-eckige
   Dachsegmente müssen für den Editor-/Live-Scene-Vertrag in gültige Quads
   zerlegt werden, oder der Import übernimmt explizit den validierten
   Ringdach-Vertrag. Einen Dry-Run mit der **neuen** Quelle und der echten
   `Stadium.capacity_total` ausführen.
3. Vor der Übernahme eine Zuordnung alter zu neuer Block-IDs samt
   RLE-Reprojektion bewerten. Ohne diese Zuordnung kann das bestehende
   Managerdesign nicht verlustfrei erhalten werden; dann nur nach
   gesonderter Zustimmung mit Standarddesign ersetzen.
4. Bei Fehler oder Widerruf die gesicherten JSON-Felder in einer Transaktion
   auf dieselben Stadionzeilen zurückspielen; erst danach Live-Szene und
   Editor erneut prüfen. Die Preview-URL bleibt als unabhängiger Vergleich
   erhalten.