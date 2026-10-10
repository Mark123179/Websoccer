# Dortmund: feste Orthofoto-Vorlage — Machbarkeitsprüfung

## Umfang

Nur eine deterministische Bildprobe, keine KI-Generierung, kein produktiver
Einbau und keine Änderungen an Stadionmodell, Spieldaten oder Studienkamera.

## Quellen

- Geobasis NRW, WMS NW DOP, Layer `nw_dop_rgb`, EPSG:3857.
- Dienst: https://www.wms.nrw.de/geobasis/wms_nw_dop
- Datensatz/Lizenz:
  https://open.nrw/dataset/56fb584b-10cf-4009-a405-0bef06bb3e00
- Datenlizenz Deutschland – Zero – Version 2.0:
  https://www.govdata.de/dl-de/zero-2-0
- Örtlicher OSM-Auszug: © OpenStreetMap contributors, ODbL.
- Reales Spielfeld: OSM-Way 17235988; Stadiongrundriss: Way 17235929.

Der Aktualisierungsstand des Dienstes ist nicht das Aufnahmedatum dieses
Luftbildes. Das konkrete Bildflugdatum wurde noch nicht festgestellt.

## Registrierung und Achsenprüfung

Die bestehende georeferenzierte Pitch-Metadatenquelle und das reale OSM-Feld
haben denselben Mittelpunkt. Die Kartenrotation beträgt rund −82° für die
positive Tor-zu-Tor-Achse (Süd). Die feste Studienkamera blickt von Westen.

Im isolierten Draufblick ohne Dach liegt die durchgehende große Terrasse
rechts (+Szenen-X), die gegliederte zweirangige Gegenseite links. Diese
physische Eigenschaft stützt die Zuordnung Süd rechts/Nord links unabhängig
von bloßen Unity-Meshnamen. Die Modellabbildung lautet Szenen-X = Karten-u,
Szenen-Z = −Karten-v. Dies ist eine visuelle Seitenprüfung, keine geodätische
Vermessung des Unity-Assets.

Die inverse Projektions-/Viewmatrix der unveränderten Kamera wird pro Pixel
mit einer horizontalen Bodenebene geschnitten. Daraus entstehen eindeutig
bestimmte Raster-Abtastpositionen; die KI hat keine Rolle in dieser Abbildung.
Alle vier projizierten Feldpunkte werden gegen die bestehende exportierte
Kameravorlage auf Gleichheit geprüft.

## Ergebnis

Die Kamerabodenfläche liegt fast vollständig innerhalb des echten
Stadiongrundrisses. Nur rund 2,11 % der gesamten Bildfläche zeigen in der
flachen Bodenprobe Fläche außerhalb dieses Grundrisses (ohne das Spielfeld).
Die gerenderte Modell-Silhouette verdeckt diese Flächen praktisch vollständig.

Die Silhouette belegt bei diesem Zustand etwa 77,12 % der Nicht-Feldfläche.
Die verbleibende freie Fläche ist überwiegend die echte, im Schnitt
ausgeblendete kameraseitige Stadionfläche — kein freier Stadtvorplatz.

Die Bodenprobe neutralisiert den fotografierten Stadiongrundriss mit
Schraffur. Sie behauptet nicht, den unbekannten Boden unter dem Stadion
fotografisch rekonstruiert zu haben. Das Spielfeld bleibt pixelgenau aus der
Kameravorlage erhalten. Das Modellvergleichsbild verwendet den tatsächlichen
Studienrender und dessen sichtbare Silhouette; es ist ein deterministisches
Bildcompositing, kein in die App eingebauter Hintergrund.

## Grenzen und Entscheidung

- Orthofoto-Gebäude und Baumkronen sind auf eine Bodenebene projiziert.
  Aufrechte Fassaden und korrekte Höhenparallaxe fehlen.
- Stadionschatten außerhalb des Grundrisses sind nicht retuschiert.
- Schraffur und harte Diagnosemasken sind nicht fotorealistische Endbilder.
- Das Verhältnis wurde für die bestehende Schnittkamera und den geprüften
  Modellzustand ermittelt; es ist keine Aussage über alle möglichen Kameras.

Eine Originaldaten-Vorlage ist technisch möglich. Eine deutlich erkennbare
große Ortskulisse ist mit dieser unveränderten nahen Bildkomposition aber
nicht erreichbar, indem man nur den Hintergrund austauscht.

Vor weiterer Bildbearbeitung braucht es eine Nutzerentscheidung:
entweder den engen feldzentrierten Ausschnitt mit sehr zurückhaltendem Umfeld
beibehalten oder eine neue gemeinsame feste Kamera für alle Vereine prüfen.
Eine neue Kamera dürfte das Feld nicht vereinsabhängig einpassen und benötigt
eine neue gemeinsame Bildregistrierung. Das ist hier nicht umgesetzt.

## Reproduktion

Die Rasterquelle samt BBOX steht im ignorierten
`generated-artifacts/dortmund-site-study/source.json`.
Nach Bereitstellung dieses Rasters:

1. `node scripts/export_dortmund_geo_probe.mjs`
2. `python scripts/build_dortmund_geo_probe.py`

Die generierten Bildbelege und numerischen Prüfungen bleiben unter
`generated-artifacts/`, nicht in Git oder im produktiven Deployment.
