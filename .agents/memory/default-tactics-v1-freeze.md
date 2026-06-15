---
name: Default-Taktik V1 Freeze-Stand
description: Alle V1-Design-Entscheidungen nach Review eingefroren; 13 Pflicht-Tests grün.
---

## Frozen (Stand 2026-06-15)

### Kategorisierung

```
clear_underdog : relative_diff ≤ −7.0 %
underdog       : −7.0 % < diff ≤ −3.5 %
balanced       : −3.5 % < diff < +3.5 %
favorite       : +3.5 % ≤ diff < +7.0 %
clear_favorite : diff ≥ +7.0 %
```

`relative_diff = (own − opp) / avg(own, opp)` — Rohwert, keine Rundung.

Grenzfall 69 vs 74 = −6.993 % → **underdog** (nicht clear_underdog).

### Links/Rechts-Spiegel

`analyze_side_matchups()` vergleicht gespiegelt:
- eigener **linker** Angriff → gegnerische **RECHTE** Abwehr
- eigener **rechter** Angriff → gegnerische **LINKE** Abwehr

### Conditions-Matrix (Rückstand/Führung nach Kategorie)

| Kategorie      | Rückstand ab | Schlussangriff ab | Führung sichern ab |
|----------------|-------------|-------------------|--------------------|
| clear_underdog | 65'         | 80' (rueckstand_2)| 70'                |
| underdog       | 60'         | —                 | 75'                |
| balanced       | 60'         | —                 | 75'                |
| favorite       | 55'         | —                 | 75'                |
| clear_favorite | 50'         | 75' (rueckstand_2)| 70'                |

Für clear_underdog und clear_favorite: spezifischste Bedingung (rueckstand_2)
steht in der conditions-Liste ZUERST (select_active_condition_plan gibt ersten Match zurück).

### Reihenfolgeunabhängigkeit (Snapshot-Ansatz)

`_make_default_tactic_snapshot(tactic_setup)` → `(str_dict, zone_dict)` liest
nur `lineup`, `formation`, `base_strength` — KEINE Taktik-Einstellungen.
In `match_engine.py` werden Snapshots VOR jeder Modifikation für beide Clubs berechnet.
Beide Snapshots werden als Parameter übergeben.

### Debug-Felder im Return-Dict

`generate_default_tactic()` liefert:
- `own_overall`, `opp_overall`: float
- `relative_diff`: Rohwert (nicht gerundet)

### Tests

13 Pflicht-Tests in `game/tests/test_default_tactic_v1.py`.
T04 via `unittest.mock.patch('game.match_engine.apply_default_tactic_settings')` —
managed clubs setzen first_half durch andere Pfade (patch_managed_lineup),
daher Mock statt assertIsNone.
