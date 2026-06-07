---
name: Asset-ID-System (fm_inside_id)
description: Canonical ID system for mapping clubs/players to local image assets.
---

## Rule

All club and player images are keyed by `fm_inside_id` (Football Manager / FMInside numeric ID), NOT the Django primary key. Django PKs can change on DB resets; `fm_inside_id` is stable.

## Static file paths

```
game/static/game/images/crests/<club_fm_inside_id>.png
game/static/game/images/kits/<club_fm_inside_id>_home.svg
game/static/game/images/kits/<club_fm_inside_id>_away.svg
game/static/game/images/players/<player_fm_inside_id>.svg   ← SVG wrapping a PNG
game/static/game/images/flags/<nation_id>.svg
game/static/game/images/nations/federations/<nation_id>.png
game/static/game/images/trophies/<trophy_asset_id>.png
game/static/game/images/competitions/<slug>.png
```

## Known IDs

| Entity | fm_inside_id / asset_id |
|--------|------------------------|
| FC Bayern München (club) | 915 |
| Borussia Dortmund (club) | 907 |
| Harry Kane (player) | 28049320 |
| 1. Bundesliga | 22 |
| DFB-Pokal | 1301410 |
| Champions League | 1301394 |
| Supercup | 1301397 |
| England (nation) | 765 |
| Deutschland (nation) | 771 |
| Irland (nation) | 789 |

## Missing asset fallback

- Players: `game/static/game/images/default_player.svg`
- Crests: show abbreviation or blank
- Code should build the path from `fm_inside_id` and check existence; never hard-code fallback URLs.

**Why:** Asset files come from a local Football Manager image pack. Using `fm_inside_id` as the filename makes bulk-import trivial and avoids manual rename steps.
