---
name: Freshness Model V1
description: Architecture decisions and field-location gotchas for the V1 Frische/Belastungsmodell.
---

## Key rules

- **ausdauer** lives on `PlayerSourceRating` (not on `Player`). Query via `PlayerSourceRating.objects.filter(player_id__in=pids, ausdauer__isnull=False)`. EA source preferred; fall back to FM if EA absent. Missing → neutral (70 ≡ factor 1.0).
- **training_level / medizin_level** live on `Stadium` (OneToOneField to Club). Access via `_stadium_level(club, 'training_level')` from `freshness_service.py`. Never pass these to `Club.objects.create()`.
- **PlayerStrengthProfile.freshness** is the canonical store (Decimal 0–100). `apply_match_freshness_losses` and `apply_daily_recovery` update it via `bulk_update`.

## V1 constants (frozen 2026-06-12)
- `BASE_MATCH_FITNESS_LOSS = 9.0`
- `BASE_DAILY_RECOVERY = 4.0`
- `BASE_INJURY_RISK_PER_90 = 0.009`

Changes require ≥50-season evidence + explicit user sign-off (same freeze rule as Match Engine V2).

## Test fixture gotchas
- `Player.objects.create()` requires `age` (NOT NULL, no default).
- `Stadium.objects.create()` requires `name` and `city`.
- `League.objects.get_or_create()` only needs `name` + `country` (no `short_name`, no `level`).

**Why:** These were discovered during test-fix iterations; saves re-debugging when adding future freshness tests.

**How to apply:** Whenever writing test fixtures that touch clubs, players, or Stadium levels, use the pattern in `FreshnessDecayIntegrationTests._make_club / _make_player`.
