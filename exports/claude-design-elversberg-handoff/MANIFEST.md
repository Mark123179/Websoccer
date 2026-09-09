# Manifest: Claude-Design-Paket Elversberg

## Verbindliche Dateien

| Paketpfad | Rolle | Zweck |
|---|---|---|
| `CLAUDE_DESIGN_BRIEF.md` | authoritative | Auftrag, Quellenpriorität und Elversberg-Regeln |
| `data/elversberg-live-scene-demo.json` | authoritative | Pitch-zentrierte Runtime-Scene mit 52 Blöcken und 14.643 Rasterplätzen |
| `contracts/LIVE_SCENE_CONTRACT_CURRENT.txt` | authoritative | Fachlicher Vertrag für den serverautoritativen Livemodus |

## Aktuelle Implementierungsreferenz

| Paketpfad | Rolle | Zweck |
|---|---|---|
| `current-live-mode/live_mode.html` | implementation-reference | Minimale Django-Hülle des Livemodus |
| `current-live-mode/live_mode.css` | implementation-reference | Aktuelle Styles und UI-Zustände |
| `current-live-mode/live_mode.js` | implementation-reference | Canvas-Renderer, Kamera, RLE, Culling und Dächer |
| `match-report-context/match_report.html` | implementation-reference | Aktuelle Einbettung des Heimstadions im Spielbericht |
| `match-report-context/match_report_v2.css` | implementation-reference | Responsive Größen der Spielbericht-Einbettung |

## Elversberg-Quellmaterial

| Paketpfad | Rolle | Zweck |
|---|---|---|
| `source-material/elversberg_blaupause.png` | visual-reference | Gelieferte Draufsicht und Blockaufteilung |
| `source-material/stadium_elversberg.js` | historical-reference | Gelieferte Rohgeometrie, Umfelddaten und Ausbauangabe |
| `source-material/TRANSFORMATION_NOTES.md` | implementation-reference | Dokumentiert die verlustfreie Überführung in den Live-Scene-Vertrag |

## Funktionierender Dortmund-Vergleich

| Paketpfad | Rolle | Zweck |
|---|---|---|
| `comparison-dortmund/stadion-live-scene.json` | comparison-reference | Bereits funktionierende BVB-Runtime-Scene |
| `comparison-dortmund/bvb-live-scene.jpg` | visual-reference | Screenshot des funktionierenden BVB-Renderers |
| `comparison-dortmund/CLAUDE_DESIGN_BRIEF_BVB.md` | comparison-reference | Briefing des erfolgreichen Dortmund-Pakets |

## Integrität

`CHECKSUMS.sha256` enthält SHA-256-Prüfsummen aller Paketdateien außer sich
selbst.

Das vollständige Verzeichnis und das herunterladbare ZIP werden mit
`python scripts/build_elversberg_handoff.py` erzeugt. Dabei werden Runtime-Scene,
Renderer, Spielbericht-Kontext und Dortmund-Vergleich vor jeder Paketierung aus
ihren kanonischen Projektquellen aktualisiert.

## Wichtiger Datenhinweis

Die Elversberg-Live-Scene ist ein Demonstrationsstand des laufenden Ausbaus:

- Projekt-Datenbank: 10.000 Plätze
- gelieferte Geometrie: 14.643 Rasterplätze
- dieses Paket: 14.643 Rasterplätze

Das Paket nimmt keine Änderung an der produktiven Stadionkapazität vor.
