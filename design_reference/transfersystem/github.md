# GitHub-Anbindung

repo: Mark123179/Websoccer
branch: main

## Last sync

date: 2026-07-25T18:14:45Z

### Updated in this project
- Transfersystem-Prototyp (`Transfersystem.dc.html`) gebaut — Transfermarkt, Leihmarkt, Meine Deals, Kader anbieten, Historie
- Standalone-Export `Transfersystem-standalone.html` für die Übergabe an Replit erstellt
- `TRANSFERSYSTEM_SPEC.md` als verbindliche 1:1-Bauanleitung geschrieben (Regeln, Datenmodell, Cronjobs, Abnahme-Checkliste)
- `README_REPLIT.md` als Übergabe-Anleitung ergänzt

## Screen map

| Bereich im Prototyp | Quellen im Repo |
|---|---|
| Design-Tokens, Panels, Farben | `game/static/game/css/global-dashboard/*`, `game/templates/base.html` |
| Reiter-Leiste / Management-Shell | `game/templates/game/management/*` |
| Wappen, Spielerfotos, Wettbewerbslogos | `game/static/game/images/crests/`, `.../players/`, `.../competitions/` |
| Nationalflaggen (im Nachbau) | `staticfiles/assets/flags/<asset_id>.png`, Zuordnung via `.agents/memory/nation-badge-id-calibration.md` |
| Spielstärke-/Positionslogik (HP/NP) | `SPIELSTAERKEMODELL.md` |
| Gerüchte-Quelle | Vereinsnews (`game/templates/game/.../vereinsnews*`) |
