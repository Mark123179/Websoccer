---
name: Player source attribute pipeline
description: How per-attribute columns on PlayerSourceRating are sourced separately from FMInside and SoFIFA, plus the non-obvious mapping/pinning decisions.
---

# Player source attribute pipeline (PlayerSourceRating)

Single attributes (0-99) live as nullable columns on `PlayerSourceRating`, one ROW
per source (`source=SOURCE_FM` for FMInside, `source=SOURCE_EA` for SoFIFA). Sources
are **never merged** — each row holds only its own source's values; columns a source
does not provide are explicitly written NULL on that row (`store_source_rating` resets
all `ALL_ATTR_COLUMNS` every write). FMI-only columns (technik, teamwork, ecken,
tw_eins_gegen_eins) therefore stay NULL on the EA row.

Scraped + stored by `import_player_source_ratings` (extended). `--player-id N` pilots
one player; the player's club must be in `SOURCE_CLUBS` (only 2 clubs configured →
rollout to all 18 BL squads needs more club URLs added there).

**Why:** the user wants distinct, comparable source data, not a blended number.

## Non-obvious decisions
- **FM26.2 pinning:** FMInside serves the active DB version. Rewrite any player URL to
  prefix `7-fm262` (`fm_inside_detail_url`) to force the FM26.2 dataset; the active
  version label is read back from `<li class="active">…FM26.2</li>` and stored as
  `source_version` ("FMInside FM26.2"). `7-fm-26` currently redirects to FM26.2 too.
- **SoFIFA "Stellungsspiel" → `defensivstellung`:** SoFIFA English label is
  "Attack position" (German "Stellungsspiel"), which is *attacking* positioning, NOT
  the defensive sense of FMI's `positioning`/Defensivstellung. Mapped together per
  explicit user instruction (by German name). Semantically loose — flag if revisited.
- **GK vs outfield:** separate maps (FMI_GK_MAP / SOFIFA_GK_MAP) keyed off
  `player.position == 'TW'`. GK rows fill only the 5 tw_* columns.

## Reference (Olise pilot, verified)
FMInside FM26.2: rating 88 / pot 93, 16 attrs. SoFIFA: 89 / 91, 13 attrs.
SoFIFA has no one-on-ones → tw_eins_gegen_eins always NULL on EA rows.
