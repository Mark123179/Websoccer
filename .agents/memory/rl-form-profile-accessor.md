---
name: PlayerRLFormProfile reverse accessor
description: The OneToOne reverse accessor from Player is `player.ln`, not the model name — naming footgun.
---

# PlayerRLFormProfile reverse accessor is `player.ln`

The `PlayerRLFormProfile.player` OneToOneField uses `related_name='ln'`, so the
reverse accessor from a `Player` instance is **`player.ln`** (used in
`views_creator.py`, `strength_service.py`, `auto_match_api_football.py` via
`ln__api_football_player_id`). The forward model field for the form value is
`rl_form_score`. So field name (`rl_form_score`) and reverse accessor (`ln`)
look unrelated.

**Why:** Cost real time during the 424-player reseed — guessing `player.rl_form_profile`
would raise AttributeError. To create a neutral profile you can sidestep the
naming entirely: `PlayerRLFormProfile.objects.create(player=player)` — all
defaults are already neutral (rl_form_score=0, rl_form_fit=1.00,
status=not_mapped).

**How to apply:** When reading/filtering the RL-form relation from Player, use
`player.ln` / `ln__...`. When only the model defaults are needed (neutral form,
no API mapping), create via the model manager and ignore the accessor.
