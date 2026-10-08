# Bildbasiertes Stadionumfeld im Admin-Test

## Umfang

Die Ansicht unter `/live/test/` ersetzt das verworfene modellierte Umfeld durch
die zwei gelieferten Dortmunder Bilder. Stadion, Spielfeld und Dach bleiben
3D. Die Ansicht ist weiterhin eine unabhängige Dortmund-Kamerastudie, nicht
das Stadion der gewählten Testspiel-Mannschaften. Der produktive Neon-Editor,
Simulation, Ticker-Geschichten und Zeitbudget werden nicht verändert.

Die vorherige Dokumentation für natürliche Modellpakete beschreibt den
alten Ansatz und ist keine Assetanforderung für diesen Bildmodus.

## Bilder und Vereinszuordnung

Die Zuordnung verwendet die kanonische FM-Vereins-ID. Dortmund hat ID 907.
Weitere Vereine benötigen eigene gelieferte Bilder, eine passende
Stadiongeometrie und eine eigene geländebezogene Registrierung. Fehlende
Zuordnungen liefern einen ausdrücklichen Fehler, niemals Dortmund als Ersatz.
Eine neue Creator-Upload-Oberfläche oder ein produktiver Rollout sind nicht
Teil dieses Admin-Test-Auftrags.

| Profil | Geliefertes Original | Auflösung | Ausgelieferte Datei | Bytes |
|---|---|---|---|---:|
| Tag | `attached_assets/image_1791444890810.png` | 2688×1344 | `stadium_editor/image_backgrounds/907/day.webp` | 4.471.996 |
| Nacht | `attached_assets/image_1791444883477.png` | 1568×784 | `stadium_editor/image_backgrounds/907/night.webp` | 882.502 |

Die beiden WebP-Dateien sind verlustfrei und ihre RGB-Pixel wurden gegen die
Originale verglichen. Es gab keine Generierung, Retusche, Neuskalierung oder
Inpainting. Originaldateien bleiben erhalten.

## Registrierung

Die vier weißen Feld-Eckpunkte liegen im Referenzformat 1024×512 bei
`(421,245)`, `(604,245)`, `(621,358)`, `(403,358)`.
Sie sind keine Stadion-Bounding-Box. Die tatsächlichen weißen Linien des
Originalmodells haben die Halbmaße 34,080013×52,950012 Meter und liegen bei
Y≈0,008346. Die äußere originale Grasfläche bleibt ebenfalls erhalten.

Aus Nah-/Fernbreite und Feldtiefe wird eine feste perspektivische Kamera
berechnet. Für diese Zuordnung beträgt die symmetrische Restabweichung
0,25 Referenzpixel; die Neigung ergibt sich zu ungefähr 61,12°, nicht den
alten ungeprüften 50°. Bei Größenänderungen teilen Foto und Canvas denselben
2:1-Viewport, dieselbe Skalierung und dieselbe Projektionsverschiebung.
Unvereinbare Eckpunkte werden zurückgewiesen, nicht durch deformierte
Stadiongeometrie ausgeglichen.

Der Nutzer hat die feste Kamera bestätigt. Der Höhenregler entfällt in
diesem Modus. Kamera und Bildwahl hängen weder an Kapazität noch an
veränderten Tribünen-Bounds. Der vorhandene Ausbau-Updatepfad verwendet
dieselbe Registrierung; das Bild muss nicht neu erstellt werden.

## Darstellung und Fehler

Ein DOM-Bild liegt hinter dem transparenten WebGL-Canvas. Dieser Modus lädt
keine geografischen Umfeldmodelle, Impostors, Bodenmaterialien oder HDRIs.
Tag/Nacht aktualisiert erst nach erfolgreichem Bild-Decoding gleichzeitig
Bild und Stadionlicht. Ein fehlgeschlagener Wechsel behält das bisherige
Bild und Licht; derselbe Profilbutton erlaubt einen erneuten Versuch.
Überholte Wechsel und entfernte Szenen können nicht nachträglich committen.

Das Tageslicht erzeugt Schatten auf der echten Stadiongeometrie. Die
geöffnete Vorderseite wird auch aus dem Schattenwurf ausgeschnitten.
Nacht verwendet sechs nach innen gerichtete, unter dem Dach platzierte
Stadionlichter und zurückhaltendes Außenlicht. Die Lichtpositionen sind eine
grafische Beleuchtungsannäherung aus den vorhandenen Dach-/Feldmaßen, kein
Nachweis realer Lampenpositionen. Es werden keine Umfeldobjekte erfunden.

## Nachweise

`docs/stadium/image-background-review/` enthält echte angemeldete Aufnahmen
von Tag/Nacht, Dach an/aus, Mobilansicht und einer browserseitigen
Ausbau-Vorschau. Die Prüfaufnahme benutzt nur im Browser einen erhaltenen
Zeichenpuffer und auslesbare Kamera; diese Hilfen sind nicht im App-Code.
Die Ausbauprüfung verändert ausschließlich die temporäre Browsergeometrie,
keine Stadiondaten oder Kapazitäten.

Der Bericht prüft Profilwechsel einschließlich einmal absichtlich
abgebrochenem Nachtbild-Download und erfolgreichem Wiederholen,
unveränderte Projektionsmatrix beim Ausbau, keine zusätzlichen Bilder beim
Ausbau, keine Umfeld-Assetdownloads, keine Seitenfehler und kein Überlaufen.
Software-WebGL-Zeiten einschließlich erster Shader-Kompilierung sind keine
Hardware-FPS und keine Ladezeitgarantie.

Der unveränderte Originalmodell-Satz einschließlich Manifest und Texturen
umfasst 17.799.899 Bytes. Zusammen mit dem Tagesbild sind das 22.271.895 Bytes
statischer Modell-/Bilddaten; der erste Nachtwechsel ergänzt 882.502 Bytes.
JavaScript, CSS, HTTP-Kompression und Browsercache sind darin nicht enthalten.
Die Bestandsszene meldet 454.510 Dreiecke und 331 Draw Calls bei geschlossenem
Dach; dem modellierten Umfeld sind im neuen Modus null Dreiecke zugeordnet.
Beim ersten Nachtwechsel benötigte die Software-Aufnahme rund fünf Sekunden
für den Renderaufruf mit neuen Shader-Varianten. Spätere Nacht-Aufrufe lagen
bei ungefähr 7–19 ms; daraus lässt sich keine Endgeräte-FPS ableiten.

Gezielte Prüfungen:

```sh
python manage.py test game.tests.test_stadium_image_backgrounds game.tests.test_live_story_admin_test --keepdb
node --test stadium_editor/static/stadium_editor/image_background_camera.test.mjs stadium_editor/static/stadium_editor/image_background_scene.test.mjs
```

Grüne technische Prüfungen ersetzen keine optische Nutzerabnahme.
