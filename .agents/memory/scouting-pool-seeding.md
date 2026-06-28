---
name: Scouting-Pool seeding
description: How to make countries actually scoutable by filling the clubless player pool, and the traps involved.
---
A country only flips from "building" to "scoutable" when its clubless SCOUTABLE
pool players (primary nationality) reach COUNTRY_THRESHOLD (50). The dev pool is
otherwise empty (0), so every country shows "Netzwerk im Aufbau".

`game/management/commands/seed_scouting_pool.py` generates placeholder pool
players: `club=None`, `pool_status=SCOUTABLE`, unique `wsc_player_id` prefix
`POOLSEED-<ISO>-` (so `--reset` only deletes seeds, never real imports).

**Why these constraints:**
- Each pool player MUST get its own `PlayerStrengthProfile` — `draw.player_base_strength` reads `player.strength_profile.base_strength`; without it the player is strength 50.
- Keep `base_strength < 84` (TOP_STAR_STRENGTH) and potential <= 85, else `draw.is_top_reserved()` marks them as Top-Star/Top-Talent and they are NEVER offered via scouting search (`eligible_players` excludes them).
- GB trap: COUNTRIES['GB'] name is "England", but `geo.nationality_to_iso2('England')` returns `GB-ENG`, not `GB`. Use a flag-asset name that reverse-maps to the map ISO (for GB: "Vereinigtes Königreich"). `_nationality_for_iso()` handles this generically.

**How to apply:** `python manage.py seed_scouting_pool --countries DE,TR,BR --per-country 60`. `--per-country=0` only allowed with `--reset` (pure cleanup). Verify with `coverage.map_data()` status + `draw.eligible_players('country','DE')`.
