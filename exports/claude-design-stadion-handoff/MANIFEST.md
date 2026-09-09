# Manifest: Claude-Design-Stadionpaket

## Verbindlich

| Paketpfad | Zweck |
|---|---|
| `CLAUDE_DESIGN_BRIEF.md` | Auftrag, Prioritäten, Gestaltungsrichtung und Abnahmekriterien |
| `data/stadion-live-scene.json` | Autoritative BVB-Runtime-Scene mit 52 Blöcken und expliziten Dachsegmenten |
| `contracts/LIVE_SCENE_CONTRACT_CURRENT.txt` | Fachlicher Live-Scene-Vertrag; dieses Dokument gilt vor allen Legacy-Quellen |

## Aktuelle technische Ausgangslage

| Paketpfad | Zweck |
|---|---|
| `current-live-mode/live_mode.html` | Eigenständige Django-Seite und minimales Runtime-Markup |
| `current-live-mode/live_mode.css` | Aktuelle dunkle Stadionansicht und UI-Zustände |
| `current-live-mode/live_mode.js` | Scene-Validierung, RLE-Dekodierung, Quadprojektion, Dach- und Canvas-Renderer |
| `match-report-context/match_report.html` | Aktuelle Spielberichtseite mit eingebetteter Heimstadion-Scene |
| `match-report-context/match_report_v2.css` | Abmessungen und responsive Einbettung der Stadionansicht |

## Editor- und Datenreferenz

| Paketpfad | Zweck |
|---|---|
| `editor-reference/editor.html` | Aktuelle Editor-Oberfläche; nur UI-/Workflow-Referenz |
| `editor-reference/editor.js` | Top-/3D-Editorrenderer und historische Quadverarbeitung |
| `editor-reference/bvb_blocks_v2.json` | Historische pitch-rotierte BVB-Blueprintgeometrie; nicht direkt im neuen Prototyp rendern |
| `editor-reference/stadion-editor-export.json` | Design-V2-Vertrag ohne Raumgeometrie |
| `editor-reference/bvb-stadioneditor-design.json` | Ältere BVB-Design-/RLE-Referenz; nicht autoritativ für Rastermaße |
| `editor-reference/stadion-editor-prototyp.html` | Ursprünglicher eigenständiger Editorprototyp |

## Visuelle Referenzen

| Paketpfad | Zweck |
|---|---|
| `visual-references/bvb-live-scene-current.jpg` | Screenshot des aktuell funktionierenden Livemodus |
| `visual-references/reference-small.png` | Gelieferte visuelle Detailreferenz |
| `visual-references/reference-wide.png` | Gelieferte breite Stadionreferenz |

## Legacy und Vorgeschichte

| Paketpfad | Zweck |
|---|---|
| `legacy-reference/STADIUM_JSON_CONTRACT_LEGACY.txt` | Frühere aggregierte Vertragsidee; nur zur Problemhistorie, nicht implementieren |

## Integritätsdatei

`CHECKSUMS.sha256` wird beim Erzeugen des ZIPs automatisch angelegt und enthält
SHA-256-Prüfsummen für alle Paketdateien außer sich selbst.

## Autoritätsregel

Bei jedem Widerspruch gilt:

```text
stadion-live-scene.json
  > CLAUDE_DESIGN_BRIEF.md
  > LIVE_SCENE_CONTRACT_CURRENT.txt
  > aktueller Renderer
  > Spielbericht-Kontext
  > visuelle Referenzen
  > Editor-Referenzen
  > Legacy-Dokumente
```

Die Editor- und Legacy-Dateien dürfen niemals verwendet werden, um fehlende
Live-Scene-Geometrie zu erfinden oder die aktuelle Scene umzuschreiben.