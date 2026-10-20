# HSV: quellgebundene Nachtkalibrierung

## Status und Versionierungsgrenze

Die bestehende Registrierung `stadium_editor/blueprints/v2/models/947.json`
bleibt **unverändert**. Auch `generated-artifacts/hsv-study` bleibt unangetastet.
Das vorhandene `register_stadium_model.py` lehnt das automatische Ersetzen
einer Registrierung ab. Daher entsteht ein separates Prüfpaket, kein
stillschweigendes Update des abgenommenen Pakets.

| Stand | Asset-Version |
|---|---|
| Registrierter Ausgangsstand | `51bbcc74241c6795` |
| Geprüfter Nachtkandidat | `1b96815599cec644` |

Keine Registry-, Storage- oder Datenbankschreibzugriffe; kein Publishing.
Eine Aktivierung ist eine separate, ausdrücklich freizugebende Revision:
neue Version vollständig dauerhaft ablegen und prüfen, alten Assetbestand
erhalten, erst danach den Registry-Verweis ändern und Worker neu starten.
Den Schutz des bestehenden Registrierbefehls nicht durch dessen Aufruf
mit einem veränderten Paket umgehen.

## Befund

Das Originalbundle enthält 416 aktivierte Spotlight-Komponenten. Der bisherige
Export akzeptiert 19 und wählt neun Repräsentanten. Der ursprüngliche Filter
prüft Höhe ≥18 m, Richtung Y <−0,05, Lampenabstand ≤2 m sowie den
Achsen-Bodenschnitt innerhalb ±40 m X / ±60 m Z. Das ist der historische
Prüfbereich, **nicht** die exakte 105×68-m-Spielfeldgrenze.

Die erneute Prüfung verwendet dieselben unveränderten Quellpositionen und
Welttransformationen. Lampenbeleg bleibt das bereits geprüfte Material `56`
(`tex_bm_56`) auf Mesh `center3_6`, Path-ID `-3439041506061313772`.
Die 360 Dreiecke werden mit ihren tatsächlichen Indizes ausgewertet,
nicht als Bounding-Box, konvexe Hülle oder unendliche Ebene.
Die Mindestdistanz berücksichtigt Flächeninneres, geschlossene Kanten
und degenerierte Dreiecke.

| Entscheidung | Anzahl |
|---|---:|
| Angenommen, Vertex- und Flächenprüfung | 19 |
| Nur Lampenabstand >2 m | 293 |
| Lampenabstand >2 m **und** Achse außerhalb Prüfbereich | 104 |
| Weitere durch Flächenprüfung gewonnene Kandidaten | 0 |

Die 104 sind eine Teilmenge der 397 wegen Lampenabstand abgewiesenen Quellen.
Keine Quelle scheitert hier an Mindesthöhe oder Abwärtsrichtung.
Die größte Abstandsverbesserung durch die Flächenprüfung ist nur
0,005966 m. Der knappste verworfene Kandidat bleibt 2,220270 m entfernt.
Eine Aufweitung der Toleranz, eine Verschiebung von Quelllichtern oder die
Umdeutung des Dachs zu Lampengeometrie ist deshalb keine belegte Korrektur.
Der generische Exporter bleibt unverändert, ebenso andere Stadionmanifeste.

## Gewählte Kalibrierung

- Drei echte Originalpositionen auf WEST repräsentieren sämtliche 19
  zulässigen Unity-Komponenten. Gruppierung ist deterministisch,
  vollständig und disjunkt; höchstens drei Positionen je Seite,
  höchstens zwölf gesamt. Keine Mittelwertpositionen.
- Koordinaten, Richtungen, Öffnungswinkel, Farbe und Reichweite bleiben
  exakt quellgebunden. Jedes Fixture enthält den nächsten Punkt,
  das Dreieck, die Quellindizes, Mesh-ID und das Material als Beleg.
- HSV-Exportfaktor **8**, ausschließlich im neuen Modellmanifest:
  `sourceIntensity=60`, `intensity=480`, `browserIntensityScale=8`.
  Die vorhandene Browserformel
  `intensity * 8 * min(4, sqrt(representedIds.length))` bleibt unverändert.
- Die Kalibrierung liest immer `sourceIntensity`, nicht einen bereits
  multiplizierten Exportwert. Erneutes Anwenden ergibt denselben Wert.
- Teststufe 16 hellt den Vordergrund deutlich stärker auf und wurde nicht
  gewählt. Ambient, Belichtung, Himmel und Materialemission bleiben unberührt.
- Die einseitige belegte Quelllage wird ausdrücklich nicht als vollständige
  oder photometrisch gleichmäßige Stadion-Flutlichtrekonstruktion ausgegeben.

## Verifikation

Acht frische Aufnahmen durch den vorhandenen `unity_stadium_scene.js`:
Ausgangsstand und Kandidat, jeweils Tag/Nacht × Flutlicht an/aus.
Je Variante werden die vier Zustände **in derselben Szene** umgeschaltet.
Alle Kamera- und Projektionsmatrizen sind identisch; Dach an, Exposure 1,2.
Tag ohne Flutlicht und Nacht ohne Flutlicht sind zwischen beiden Varianten
byteidentisch. Tatsächliche Browser-SpotLight-Positionen, Ziele, Winkel,
Reichweiten, Einschalt- und Laufzeitintensitäten stimmen mit dem jeweils
gehashten Manifest überein. Keine Browserfehler.

Mittlere sRGB-Bildhelligkeit im unveränderten inneren Bildausschnitt
`[320,380,900,600]`: nachts mit Flutlicht von **36,57 auf 111,22**,
etwa **3,04×**. Keine Pixel der gewählten Nachtansicht erreichen in allen
drei Kanälen gleichzeitig 250. Diese Diagnose beschreibt das tonemappte
Bild, **keine Luxmessung**, Uniformitätszertifizierung oder Geräte-FPS.

Geometrie/Texturen und Spielfeld bleiben unverändert:

```text
Bundle SHA256:
9e5fa69aeee5057f4ed1b654bbd167c045f73d22c2373b95cf9163e4e78e2065
Geometrie SHA256:
479d2dd7b0408fcc9798e3a2a885b6ef5c45d4032f53b174407f1b31c3540d2b
Ausgangsregistry SHA256:
bd6bbc2b490744895dc731bce149b155622542dddb8bef4c647a186ae19ec7c6
```

## Reproduktion und Belege

```sh
# Neue Ausgabe wählen: der Auditor verweigert existierende Ausgabeverzeichnisse.
python scripts/audit_hsv_lights.py \
  --browser-scale 8 --out generated-artifacts/hsv-night-reviewed
node scripts/capture_hsv_lights.mjs generated-artifacts/hsv-night-reviewed
python -m scripts.report_hsv_lights generated-artifacts/hsv-night-reviewed

python -m unittest stadium_editor.test_hsv_light_audit \
  stadium_editor.test_export_stadium_model
```

Der Auditor verifiziert zuerst Bundle-Hash, sämtliche unveränderten
Geometrie-/Texturhashes und die vollständige Rekonstruktion der bisherigen
19 angenommenen Quellen. Er bricht bei Abweichung ab.
Die generierten Dateien bleiben aus Git und Deployment ausgeschlossen.

Ausgaben im neuen Verzeichnis:

- `light-audit.json` / `.csv`: alle 416 Entscheidungen, Originalwerte,
  Vertex-/Flächenabstand und individuelle Ablehnungsgründe.
- `manifest.json` und `package/`: neue Version mit vollständigen Assets.
- `baseline-manifest.json`: unveränderter inhaltlicher Ausgangsstand.
- `views/`: acht Bilder und Manifest-/Bildhashes, tatsächliche Licht-
  und Kamerazustände in `render-evidence.json`.
- `measurements.json`, `vergleich.jpg`, `pruefbericht.html`:
  Einzelmessungen, Übersicht und eigenständig lesbarer Bildbericht.
- `hsv-nacht-pruefpaket.zip`: vollständige Übergabe einschließlich Assets
  und Einzelbelegen, ohne Anwendungscode.

Die aktuell vorhandenen HSV-Quellexporte waren vollständig und hashgültig;
ein Neuaufbau war deshalb nicht erforderlich. Fehlen sie später, nicht
alte Bildbelege übernehmen: aus `attached_assets/volksparkstadion*.bundle`
mit `export_stadium_model.py`, `--lamp-material 56` und der bestehenden
HSV-Kalibrierung in ein **neues** Verzeichnis exportieren. Die drei zugehörigen
JSON-Dateien explizit über `--evidence` angeben, danach die registrierten
Assethashes vergleichen. Fehlende OSM-Präsentation separat anhand der
vorhandenen HSV-Vorbereitung neu erstellen; keine Kamerakalibrierung ersetzen.
Der Auditor benötigt diese geprüften Eingaben am dokumentierten
`hsv-study`-Eingabeort; vorhandene geprüfte Pakete nicht überschreiben.
