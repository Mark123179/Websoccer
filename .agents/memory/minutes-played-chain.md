---
name: Minutes Played + Ratings chain
description: _build_minutes_played_map() Implementierung + Notenmodifikator für kurze Einsatzzeiten + bench rows in simulate_match()
---

## Regel
`_build_minutes_played_map(sub_events)` trackt `on_min` und `off_min` getrennt.
- Starter raus bei M → `minutes = M - 0 = M`
- Eingewechselter rein bei M → `minutes = 90 - M`
- Wechselkette (rein M1, raus M2) → `minutes = M2 - M1`

**Wichtig**: Nicht `min(90-M_in, M_out)` — das ergibt für Ketten falsche Werte (frühere Implementierung hatte diesen Bug).

## Notenmodifikator G (compute_player_ratings._rate())
```python
mp = p.get('minutes_played', 90)
if mp < 15:   rating = 3.5 + (rating - 3.5) * 0.20
elif mp < 30: rating = 3.5 + (rating - 3.5) * 0.50
elif mp < 45: rating = 3.5 + (rating - 3.5) * 0.75
```

## Bench-Rows in simulate_match()
Nach Aufbau von h_players/a_players werden Eingewechselte (is_sub=True) als extra Rows hinzugefügt.
Slot-Gruppe via `_slot_to_group(slot_code)`.

## Regression-Check: "Events nach Auswechslung"
Prüfung muss `goal_minute > sub_off_minute` vergleichen — nicht nur `scorer_id in out_pids`.
Ohne Minutenvergleich gibt es False Positives (Spieler trifft VOR seiner Auswechslung).

**Why:** _build_minutes_played_map wurde zunächst mit `min(90-on, off)` implementiert, was bei Ketten
off-on Minuten falsch berechnet. Separates Tracking löst das sauber.
