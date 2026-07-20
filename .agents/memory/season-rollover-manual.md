---
name: Season rollover is manual
description: How to close a sim season and why calibration metrics stay "nicht messbar" until rollover
---

# Season rollover is manual (no single command)

Rule: closing a season = play all matchdays (`play_matchday`), then
`finance_season_close --saison N`, then set `GameSeasonState.current_season`
to N+1 (shell — no canonical command exists), then ensure
`finance_season_open` for N+1 (may already be open; it's idempotent).

**Why:** `kalibrierung.py` treats `saison == current_season()` as "laufend" →
Gehaltslasten stays nicht_messbar, and MW-drift needs the (N+1)-season
`SeasonEconomySnapshot` created at season open. Forgetting the counter bump
silently keeps metrics unmeasurable.

**How to apply:** whenever a calibration run or any "after season end" job is
requested, check `GameSeasonState.current_season` and played fixtures first.
Ablöse/MW-Median additionally needs KI_KAEUFER.dry_run=False (real transfers).
