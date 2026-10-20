# HSV: quellgebundene Nachtkalibrierung

## Status und Versionierungsgrenze

### Aktuell: freigegebene Kombination in der Arbeitskopie aktiviert

Die ursprüngliche Aktivierung wurde **nicht ins Hauptprojekt übernommen**:
dort wurde zwischenzeitlich die neue Sitzgrafik registriert. Wegen des
abweichenden Ausgangshashes wurde die Zusammenführung abgebrochen.
Nach erneuter Prüfung und direktem Bildvergleich hat der Nutzer ausdrücklich
auch die Aktivierung des kombinierten Kandidaten freigegeben.

| Erneute Prüfung | Version / SHA256 |
|---|---|
| Hauptprojekt mit neuer Sitzgrafik | `26bbf1d9b445d255` |
| Erwarteter neuer Ausgangshash | `8736869c7f78320ead82226281cbe99e67154456b4549166c37cc3daa20357f4` |
| Aktivierte kombinierte Version | `fdea273ea50e8748` |
| Kombiniertes Kandidatenmanifest | `efa5689a0da72e0f1cad21b6b809bb9e74cf4b6209a588287eb399944a07a7d0` |

Alle 57 Assets wurden aus dem dauerhaften Speicher der Sitzgrafik-Version
heruntergeladen und gegen deren Manifest geprüft. Der kombinierte Kandidat
übernimmt sämtliche Texturhashes und `seatingArtworkRevision` unverändert.
Die drei Lichtquellen stimmen exakt mit dem zuvor freigegebenen Nachtkandidaten
überein. Nur `fixtures`, `lightingRevision` und `assetVersion` ändern sich
gegenüber dem Sitzgrafik-Ausgangsmanifest.

Acht neue Browseraufnahmen prüfen die unveränderte Kamera, Dach, Exposure
und Tag/Nacht × Flutlicht an/aus. Die Bilder bei ausgeschaltetem Flutlicht
sind byteidentisch; nachts mit Flutlicht beträgt der Helligkeitsfaktor des
Prüfausschnitts erneut 3,0415. Keine Browserfehler. 31 gezielte Tests bestanden.
Der erneute Prüfzyklus war vollständig lesend. Erst nach der anschließenden
Aktivierungsfreigabe wurden alle 57 Assets unter der neuen Version dauerhaft
gespeichert und vollständig mit SHA256-Prüfung zurückgelesen. Die 57 Assets der
Sitzgrafik-Ausgangsversion wurden vor und nach dem Ablegen vollständig geprüft:
unverändert. Beide exakten Manifestdateien wurden separat unter
`stadium-model-revisions/947/<assetVersion>/manifest.json` archiviert.
Auch die ursprünglichen Pakete bleiben erhalten. Keine DB- oder
Ökonomieänderungen und kein Produktionsdeployment.

Vor der Aktivierung wurde ausschließlich die Arbeitskopie vom dort zuvor
aktivierten ursprünglichen Nachtpaket auf den exakt gehashten, inzwischen
aktuellen Hauptprojekt-Ausgangsstand mit Sitzgrafik synchronisiert. Dabei
wurden sowohl der erwartete lokale Hash als auch die Übereinstimmung des
Hauptprojekt-Manifests mit der geprüften Baseline kontrolliert. Der anschließende
Aktivierungsbefehl prüfte den neuen Ausgangshash erneut vor Speicherzugriffen
und unmittelbar vor dem atomaren Registry-Wechsel.

Nach dem kombinierten Wechsel wurden `Start application` und `Import pilot`
neu gestartet; beide Django-Systemchecks sind fehlerfrei. Die laufende
Hauptanwendung liefert exakt das freigegebene Manifest sowie alle 57 Assets
der kombinierten Version über HTTP mit den erwarteten SHA256-Hashes aus.

Belege: `generated-artifacts/hsv-seating-night-reviewed/` mit eigenständigem
Bildbericht, vollständigem Paket und exaktem Ausgangsmanifest
`baseline-registry.json`. Die Dateien sind aus Git und Deployment ausgeschlossen.

Der Auditor unterstützt für diese lesende Wiederholung `--baseline`,
`--expected-baseline-sha256` und `--assets`; der Bildbericht `--baseline`.
Der Browser lädt die Texturen immer aus dem geprüften Paket, nicht aus einem
möglicherweise älteren Quellexport. Die aktive Registry muss dafür nicht
zurückgestellt werden. Der Aktivierungsbefehl ist jetzt ausschließlich auf das
erneut freigegebene kombinierte Paar begrenzt; ein anderer Ausgangshash bleibt
ein harter Abbruch. Die ursprüngliche Freigabe ist keine Erlaubnis, eine
zwischenzeitlich geänderte Sitzgrafik zu verwerfen.

### Historisch: ursprüngliche Aktivierung nur in der Arbeitskopie

Nach ausdrücklicher Nutzerfreigabe ist der Nachtkandidat jetzt in der
Arbeitskopie registriert. **Kein Produktionsdeployment.** Die ursprüngliche
Studie und die alten 57 dauerhaft gespeicherten Assets bleiben unverändert.

| Aktivierung | SHA256 / Ergebnis |
|---|---|
| Erwartetes Ausgangsmanifest | `bd6bbc2b490744895dc731bce149b155622542dddb8bef4c647a186ae19ec7c6` |
| Neues aktives Manifest | `e9f022dd47f8b1679a538f19fc5ca2cbb258aac5ae358c7a288c653df7f95d52` |
| Neue Assets vollständig aus dauerhaftem Speicher zurückgelesen | 57 / 57 hashgültig |
| Alte Assets vor und nach dem Ablegen geprüft | 57 / 57 unverändert |
| Frische Quellenprüfung und Browservergleich | 416 Quellen, 19 zulässig, 3 Repräsentanten, 8 Zustände |
| Nach Neustart über die laufende Anwendung geprüft | Manifest-Hash und alle 57 Asset-Hashes stimmen |

Die Entwicklungsprozesse `Start application` und `Import pilot` wurden nach
dem Wechsel neu gestartet; beide melden fehlerfreie Django-Systemchecks.
Kamera und Kalibrierung sind unverändert. Tag/Nacht und Flutlicht an/aus
wurden pro Variante in derselben Szene geprüft. Die unabhängigen Prüfungen
umfassen 20 Quellen-/Exporttests und neun Aktivierungs-Schutztests.

Beide exakten Manifestdateien sind zusätzlich dauerhaft unter
`stadium-model-revisions/947/<assetVersion>/manifest.json` archiviert.
Die Assets liegen jeweils getrennt unter
`stadium-models/947/<assetVersion>/`. Der ältere Versionspfad wird nicht
überschrieben oder gelöscht.

Die einmalige, ausschließlich auf diese beiden HSV-Manifest-Hashes begrenzte
Aktivierung erfolgt durch `scripts/activate_hsv_night.py --study <Prüfverzeichnis>
--approved`. Der Befehl prüft die ausdrückliche Freigabe, Ausgangshash,
Kandidatenhash, Quellen- und acht Bildbelege vor Speicherzugriffen und prüft
den Ausgangshash unmittelbar vor dem atomaren Wechsel erneut. Wiederholtes
Aktivieren oder ein anderer Ausgangsstand wird abgewiesen. Keine ORM-Zugriffe.

### Historischer Prüfstand vor der Freigabe

Während der separaten Prüfung blieb die Registrierung unverändert.
Das vorhandene `register_stadium_model.py` lehnt das automatische Ersetzen
einer Registrierung weiterhin ab; dieser Schutz wurde nicht verändert.

| Stand | Asset-Version |
|---|---|
| Erhaltener Ausgangsstand | `51bbcc74241c6795` |
| Freigegebene neue Registrierung | `1b96815599cec644` |

Die ursprüngliche Prüfung hatte keine Registry-, Storage- oder
Datenbankschreibzugriffe und kein Publishing. Eine Aktivierung ist eine
separate, ausdrücklich freizugebende Revision:
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
  stadium_editor.test_export_stadium_model stadium_editor.test_activate_hsv_night
```

Die obige Auditor-Reproduktion beschreibt den historischen Ausgangsstand.
Nach Aktivierung verwendet der Auditor sonst das neue Manifest als Baseline;
das wäre keine Reproduktion des freigegebenen Versionswechsels.
Für dessen Wiederholung in einer isolierten Arbeitskopie zunächst das
archivierte Ausgangsmanifest mit dem oben genannten SHA256 bereitstellen.
Die aktive Registry nicht für eine Studie zurückstellen.

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
