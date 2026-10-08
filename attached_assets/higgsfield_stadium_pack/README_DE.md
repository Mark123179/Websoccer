# Higgsfield: Dortmund und Elversberg

## Ziel

Vier Umfeldbilder: Dortmund Tag/Nacht, Elversberg Tag/Nacht.
Stadion und Spiel bleiben echte 3D-/2D-Ebenen. Hintergrundbilder enthalten
**nicht das jeweilige Hauptstadion**. Alle Dateien gehören zur empfohlenen
Schnittansicht: 1880 × 940 px, 105 × 68 m, Kamerahöhe 98 m, Abstand 76 m
hinter der Seitenlinie, Neigung 44°. Keine Kameraverstellung zur Bildanpassung.

Das Paket enthält Vorlagen, **keine bereits generierten Hintergrundbilder**.
Die Paketbilder wurden mit dem tatsächlichen Studienrenderer exportiert.
Es wurden keine App-Ansichten, Authentifizierung oder Spieldaten verändert.

## Dateien pro Verein

1. `01_camera_reference.png`: echtes Stadion in der Zielkamera, keine Demofiguren.
   Nur als geometrische Zusatzreferenz benutzen. Stadion nicht nachzeichnen.
2. `02_stadium_silhouette.png`: weißes Stadion auf Schwarz. Zeigt gerenderte
   sichtbare Bauteile, nicht das komplette vermessene Boden-Baufeld.
3. `03_empty_site_camera.png`: **primäres Eingangsbild**. Dieselbe Kamera,
   nur das registrierte Feld; Stadion, Tore und Figuren entfernt.
4. `04_keep_pitch_mask.png`: Weiß = geschütztes Spielfeld. Nicht mit einer
   Bearbeitungsmaske verwechseln.
5. `05_environment_edit_mask.png`: Weiß = Umfeld bearbeiten, Schwarz = Feld
   schützen. Die Maskenbedeutung des gewählten Werkzeugs vorher prüfen.
6. `06_pitch_registration_guide.png`: Ecken A–D als sichtbare Kontrollpunkte.
   Nur zur Prüfung, nicht als Bildstil oder fertigen Hintergrund verwenden.
7. `07_local_osm_reference.png`: reale Ortslage aus vorhandenem OSM-Auszug,
   Norden oben. Der vorhandene Auszug enthält hauptsächlich Gebäude;
   fehlende Wege/Waldflächen bedeuten nicht, dass dort eine leere Freifläche
   liegt. Keine fotografische Textur und keine vermessene Kameraansicht.
8. `camera.json`: exakte Feldpixel, Projektionsmatrix und Referenzmaße.
9. `PROMPT_DAY.txt` / `PROMPT_NIGHT.txt`: kopierfertige englische Prompts.

## Schrittfolge

1. Öffne https://higgsfield.ai/ai-image-editor und die Bildbearbeitung /
   Image-to-image-Funktion deines verfügbaren Modells.
   Die offizielle Seite beschreibt Referenzbilder und selektive Pinselbearbeitung;
   Funktionen und Modellzugriff können vom Konto abhängen. Keine Video-, Orbit-
   oder Text-to-image-Neugenerierung ohne die Kameravorlage verwenden.
2. Primär `03_empty_site_camera.png` hochladen. Kamerareferenz und Ortskarte,
   wenn möglich, als zusätzliche Referenzen anhängen. Keine Stadion-Silhouette
   als Aufforderung zum Bau eines Stadions interpretieren.
3. Den Bereich außerhalb des Felds bearbeiten. Wenn der Editor keine Maskendatei
   übernimmt, mit dem Pinsel nach `05_environment_edit_mask.png` auswählen.
   Schwarz/Weiß ggf. invertieren, wenn das Werkzeug umgekehrte Bedeutung nutzt.
4. Tag-Prompt einfügen. Die gesamte Hauptstadionfläche bleibt ohne Ränge, Dach,
   Flutlichter oder hohe Bauten. Auch der ausgeblendete kameraseitige Rang darf
   im Hintergrund nicht wieder auftauchen.
5. Die Bildreferenz bestimmt Perspektive und Zuschnitt, nicht ein Modellname.
   Die öffentliche Higgsfield-Modellauswahl garantiert nicht in jedem Modus 2:1.
   Falls 2:1 fehlt: Inhalt in eine 2:1-Leinwand erhalten und leere Ränder per
   Outpainting ergänzen. Keine Variante einfach auf 2:1 beschneiden oder
   ungleichmäßig strecken. Zusätzliche Leinwand verändert die Referenzregistrierung:
   die ursprünglichen Feldpixel im finalen 1880×940-Koordinatenrahmen erhalten.
6. Eine gute Tagansicht auswählen. Erst dann dieses Tagbild als neue Basis
   hochladen und `PROMPT_NIGHT.txt` anwenden. Nicht Nacht separat aus Text
   erzeugen; sonst ändern sich Häuser, Straßen und Bäume.
7. Fertige Bilder ohne Texte, Rahmen, Quellenkarten oder Vorlagemarkierungen
   zurückgeben: `dortmund_day.png`, `dortmund_night.png`,
   `elversberg_day.png`, `elversberg_night.png`.

## Ortsbezug und Grenzen

Dortmund: realer Sport-/Messebereich, Stadion Rote Erde östlich, Westfalenhalle
und Messeflächen nördlich/nordöstlich. Diese Nachbaranlagen nur zeigen, wenn
die tatsächliche Blickrichtung sie im engen Ausschnitt trägt; nicht alle
Sehenswürdigkeiten dekorativ hinter die Tribüne setzen.

Elversberg: Kaiserlinde, Lindenstraße 5, kleinstädtische Bebauung, lokale
Zufahrten/Parkflächen und Wald. Keine fremden Dortmunder Messehallen,
Großstadtsilhouette oder erfundenen hohen Berge. Der lokale vorhandene
OSM-Auszug ist zeitgebunden, nicht als aktuelle Bauabnahme ausgeben.

**Wichtig:** Der gemeinsame Renderer fixiert die Feldkamera exakt. Die absolute
Kompasszuordnung des Dortmunder Unity-Modells zum Nord-up-Plan ist hingegen
nicht unabhängig vermessen. Die Ortskarte belegt Orte und Nachbarschaften,
nicht eine bereits garantierte Linke-/Rechte-Anordnung im Zielbild.
Eine exakte geografische Registrierung erfordert zusätzlich eine überprüfte
Modell-/Kartennord-Ausrichtung. KI-Ergebnisse bleiben referenzgestützte
Illustrationen, keine vermessenen Luftbilder.

Insbesondere bei Dortmund bedeckt die nahe Spielkamera einen großen Teil
des Bildes mit dem echten Stadion. Die Silhouette zeigt diese Verdeckung:
Ortskulisse wird nur in den tatsächlich freien Bildbereichen sichtbar.
Für mehr sichtbare Umgebung nicht eigenmächtig das Feld verkleinern oder
die Kamera zurückziehen.

Die ausgeblendete kameraseitige Tribüne ist kein realer Abriss.
Keine Stadionreste in den Hintergrund hineinmalen. Die sichtbare
Stadion-Silhouette ist nicht gleichbedeutend mit der ganzen Baufläche:
auch verdeckte/ausgeblendete Hauptstadionteile müssen aus dem Bild fehlen.
Geplante Ausbauten dürfen nicht als bestehende Ortsbauten erscheinen.

Nachtlicht des Stadions kommt später aus der deklarierten Laufzeitanlage,
nicht aus dem Hintergrund. Insbesondere keine vermeintlich belegten
Elversberger Eckmasten erfinden; der Nutzer liefert diese Nachweise nach.

## Kontrolle vor Rückgabe

- Beide Bilder eines Vereins: dieselben Pixelkanten von Feld, Gebäuden,
  Straßen und Bäumen; keine Verschiebung zwischen Tag und Nacht.
- 1880 × 940, keine Rahmen/Watermarks, kein veränderter Ausschnitt.
- Ecken A–D müssen mit `camera.json` / der Kontrollvorlage übereinstimmen.
- Kein Hauptstadion, Ränge, Dach, Flutlichtmasten, Zuschauer oder Spieler.
- Hauptstadionstandort bleibt frei: keine Gebäude/Waldgruppen unter dem
  späteren echten Stadion oder an der ausgeblendeten Vordertribüne.
- Keine neue Sky-/Horizontleiste; der steile Blick zeigt Gelände.
- Ortsmerkmale gegen offizielle Quellen / OSM prüfen, Unklarheiten kennzeichnen.
- Nach Lieferung prüfen wir die Bilder zuerst über dem echten Modell in der
  geschützten Studie. Kein produktiver Rollout allein aufgrund der KI-Vorschau.

## Quellen

- Higgsfield: https://higgsfield.ai/ai-image-editor
- Higgsfield Bildbearbeitung: https://higgsfield.ai/image-editing
- BVB Anreise / offizielle Umfeldkarte:
  https://www.bvb.de/de/de/signal-iduna-park/stadionbesuch/anreise.html
- SV Elversberg / Standort:
  https://sv07elversberg.de/ursapharm-arena/stadionordnung/
- OSM Dortmund: https://www.openstreetmap.org/way/17235929
- OSM Elversberg: https://www.openstreetmap.org/way/1154632806
- Karten: © OpenStreetMap contributors, ODbL,
  https://www.openstreetmap.org/copyright
