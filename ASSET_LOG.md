# Asset Log

## Sidebar Iconset

- Quelle: selbst erstellt im Projekt
- Lizenz/Nutzungsstatus: eigenes Projektasset
- Lokaler Pfad: `game/static/game/images/icons/sidebar/*.svg`
- Einsatzort: geplante Sidebar-Navigation
- Uebernommen am: 2026-05-11
- Hinweise: 13 konsistente 24x24 SVG-Icons mit `currentColor`, ohne Fremdassets

## TCM Logo-Pack

- Quelle: `C:\Users\mashu\Documents\Codex\Websoccer\Images\Logos`
- Lizenz/Nutzungsstatus: lokaler Projekt-Assetbestand, vor weiterer Veroeffentlichung final klaeren
- Lokale Zielpfade:
  - Club-Wappen: `game/static/game/images/crests/<fm_inside_id>.png`
  - Nationalitaets-/Verbandslogos: `game/static/game/images/nations/federations/<nation_id>.png`
  - Wettbewerbslogos: `game/static/game/images/competitions/*.png`
- Einsatzort: Vereinsseiten, Spielerprofil, Transferhistorie, Saison-/Karriereleistungen
- Uebernommen am: 2026-05-13
- Hinweise: Der alte Ordner `Images\Wappen` ist nicht mehr fuehrend. Aktuell eingebunden sind Borussia Dortmund `TCM1_907.png`, FC Bayern `TCM1_915.png`, Bundesliga `TCM2_22.png`, DFB-Pokal `TCM2_1301410.png`, Champions League `TCM2_1301394.png` und Supercup `TCM2_1301397.png`.

## FM Trophy-Pack

- Quelle: `C:\Users\mashu\Documents\Codex\Websoccer\Images\Trophies`
- Lizenz/Nutzungsstatus: lokaler Projekt-Assetbestand, vor weiterer Veroeffentlichung final klaeren
- Lokaler Zielpfad: `game/static/game/images/trophies/<trophy_asset_id>.png`
- Einsatzort: Spielerprofil, Auszeichnungen & Titel
- Uebernommen am: 2026-05-13
- Hinweise: `PlayerAwardTitle.trophy_asset_id` verweist auf die FM-ID ohne Dateiendung. Harry-Kane-Dummy nutzt aktuell `22`, `1301410`, `1301394` und `1301397`.
