# Elversberg: bedingte Höhen- und Sichtprüfung

## Ergebnis und Einordnung

Separate Prüfung der unveränderten bestätigten Nordostkamera, 1880 × 940,
Haupttribüne hinten, beide Dachzustände. Kein produktiver Einbau, keine
KI-Bilder, keine Änderung von Feldprojektion oder Originalstandorten.

Die ursprüngliche Bodenprüfung wurde aus den aktuellen Studienmodulen neu
exportiert, weil der ignorierte `geo_verification.json`-Beleg im Workspace
fehlte. Kameramatrizen und Feldpunkte wurden gegen die bestätigte 75%-Probe
geprüft; alte Masken wurden nicht übernommen.

Der amtliche INSPIRE-LoD2-Dienst des Saarlands liefert gemessene
Gebäudehöhen. Zugeordnete Komponenten:

| OSM-Grundriss | Amtliche Höhen | Hauptkörper-IoU | Einordnung |
|---|---|---|---|
| Wasgau 30887518 | 9,314 / 9,379 m | 73,24 % | bedingt zugeordnete Höhenhülle |
| TVE-Halle 53864244 | 14,204 / 11,002 m | 73,41 % | mehrteiliger Bau, konservative Hülle |
| Lidl 53864241 | **unbekannt** | 3,33 % | Zuordnung verworfen; keine Ersatzhöhe |

Die amtlichen Höhenreferenzen sind nicht vollständig beschrieben:
`HeightStatus=measured`, `lowReference=unknown`, `heightReference=nil`.
Version 05.03.2024 ist kein belegtes Foto-/Vermessungsdatum.

Die unveränderten OSM-Grundrisse wurden auf dem bestehenden gemeinsamen
flachen Bezugsniveau bis zur größten zugeordneten Komponenten-Höhe extrudiert.
Ein echter WebGL-Tiefenpuffer prüft Dach-/Wandpixel gegen das aktuelle
Stadion und 158 zugeordnete Nachbargrundrisse. Das sind bewusst vereinfachte
Höhenhüllen, **nicht** die amtlichen Dachgeometrien oder Originalfassaden.

Wasgaus Hüllwände bleiben mit 18.806 Pixeln sichtbar. Bei TVE bleiben nach
Nachbarverdeckung 12.160 Wandpixel; 9.142 Dach-/Wandpixel werden von
Nachbarhüllen verdeckt. Das gilt in beiden geprüften Stadiondachzuständen.
Die eigene Stadiongeometrie verdeckt diese beiden Hüllen hier nicht.

Von 70 ursprünglich bodensichtbaren Gebäuden konnten 43 höhenmäßig
zugeordnet werden; 27 bleiben offen. Lidl wurde nur mit ausdrücklich
angenommenen 3/6/9/12 m als Sensitivität geprüft, nicht als reale Höhe.
Das kommunale Sportstättenkonzept von 2017 enthält auf PDF-Seite 24 ein
historisches Originalfoto der TVE-Fassade und ein Luftbild. Es belegt Form
und Material, nicht Höhe oder den heutigen Zustand. Die offizielle
Lidl-Filialseite bestätigt den Standort, liefert aber kein geeignetes
Gebäudefoto; die Bildsuche lieferte nur Prospekte.

**Keine Freigabe für eine ortsverifizierte Fotokulisse:** Gelände relativ
zum Spielfeld, echte Dachformen, nicht zugeordnete Gebäude und Baumkronen
fehlen als vollständige Verdeckungsquellen. Sichtbare Hüllwände sind kein
abschließender Nachweis unverdeckter Originalfassaden.

## Quellen

- [Amtlicher INSPIRE-WFS SL Gebäude – 3D LoD2](https://geoportal.saarland.de/spatial-objects/407)
- WFS: `https://geoportal.saarland.de/gdi-sl/inspirewfs_Gebaeude_3D_LoD2`
- [Sportstättenkonzept Gemeinde Spiesen-Elversberg, 15.12.2017, PDF-Seite 24](https://www.spiesen-elversberg.de/fileadmin/user_upload/Spiesen-Elversberg/PDF/Sportstaettenkonzept.pdf#page=24)
- [Offizielle Lidl-Filiale Lindenstr. 3b](https://www.lidl.de/s/de-DE/filialen/spiesen-elversberg/lindenstr-3b/)
- Lokaler Original-OSM-Auszug: Stand 15.09.2026.
- ©LVGL 2022, dl-de/by-2-0, www.lvgl.saarland.de.
- © OpenStreetMap contributors, ODbL 1.0.

Recherche am 10.10.2026. Im Quellenpaket bleiben auch die fehlgeschlagenen
BuildingPart- und GeoJSON-Abfragen erhalten; sie sind keine Höhenbelege.

## Ausgabe

Unter `generated-artifacts/elversberg-height-visibility/`:

- `report.html`: eigenständiger deutscher Bericht mit eingebetteten Bildern.
- `height_visibility.json`: Dach-/Wandzahlen, Verdeckung, Grenzen, SHA-256.
- `height_inputs.json`: Grundrisse, amtliche IDs/Höhen und Zuordnungsqualität.
- `render_verification.json`: Kamera-/Feldpunkte, ID-Pässe, Dachzustände.
- `height_envelopes_{roof,no_roof}.png`: gemessene Höhenhüllen.
- `lidl_assumed_6m_{roof,no_roof}.png`: ausdrücklich unbewiesene Sensitivität.
- `comparison.jpg`, `README.md`, Rohpässe und unveränderte Quellenantworten.
- `elversberg-height-visibility.zip`: Bericht und vollständige Belege.

Alle 416.792 geschützten Feldpixel sind in allen Vollbildern exakt aus dem
jeweiligen Originalrender erhalten. Die nicht antialiasierte ID-Belegung
weicht an den Stadionkanten um 1.904 bzw. 2.352 Pixel von der frischen
antialiasierten Schwellwert-Silhouette ab; diese methodische Differenz ist
separat ausgewiesen und nicht als neue Stadiongeometrie interpretiert.

## Reproduktion

Voraussetzungen: vorhandene bestätigte Probe, lokaler OSM-Auszug,
aktuelles Stadionmodell, laufender Django-Workflow, vorhandenes
Playwright-Core/Chromium, NumPy, Pillow und Shapely.
Die GML-Quellen liegen im ignorierten Quellenpaket, nicht im Git-Repository.
Abfrageparameter einschließlich BBOX/Seiten stehen in `height_inputs.json`.
Fehlende Belege führen zu einem ausdrücklichen Fehler.

```sh
# Nur wenn der aktuelle Bodenbeleg fehlt oder das Modell geändert wurde:
node scripts/export_stadium_frame_probe.mjs --middle --main-stand-back
node scripts/export_dortmund_geo_probe.mjs
python scripts/build_dortmund_geo_probe.py

# Quellen-GML mit den dokumentierten WFS-Parametern bereitstellen:
python scripts/prepare_elversberg_height_probe.py
node scripts/export_elversberg_height_probe.mjs
python scripts/build_elversberg_height_report.py
python scripts/test_elversberg_height_probe.py
```

Der WFS begrenzt Seiten auf 200 tatsächliche Gebäude. Für den geprüften
Ausschnitt folgen 20 weitere; beide Seiten werden auf Eindeutigkeit geprüft.
Das fehlerhafte Antwortattribut `numberReturned=0` wird nicht als leerer
Datensatz interpretiert. Die erfolgreiche Prüfung zählt tatsächliche
Gebäudeelemente und verlangt eine kurze letzte Seite.
