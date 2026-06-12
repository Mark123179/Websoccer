---
name: Match-day potential draw
description: Design intent for how player potential affects per-match strength in simulate_match().
---

# Match-day potential draw

**Rule:** Before every match, each player's effective match strength is drawn randomly between their base and potential ceiling, then the form modifier is added.

```
match_strength = random.uniform(base_strength, calculated_potential_strength) + form_modifier
clamped to [0, 200]
```

**Implementation:** `_draw_match_strength(player)` in `match_engine.py`. Called once per player in `simulate_match()` as a pre-compute step → stored in `match_strengths: dict[player_id → float]` → passed to both `_build_team_dict()` (simulation) and `_player_row()` (display). This ensures simulation and Spielbericht show the same value.

**Why:** User-confirmed design intent. A player with high potential can reach their ceiling — but not every match. This creates natural variance per game without permanently changing base_strength.

**How to apply:**
- Never call `_draw_match_strength()` separately for display vs simulation — always pre-compute once and pass the same dict to both.
- `_player_row(match_strength=...)` uses the pre-computed value; falls back to `base_strength` if None.
- `_build_team_dict(match_strengths=...)` uses the dict; falls back to `sp.final_strength` if player not in dict.
- Spielbericht column renamed from "Endst." to "Matchst." to avoid confusion with permanent development strength.
