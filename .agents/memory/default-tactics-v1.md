---
name: Default-Taktik V1
description: Automatische Taktikwahl für trainerlose Vereine — Architektur, Schwellen, Integrationsschicht
---

## Übersicht
`game/default_tactics.py` (kein Django) + Integration in `match_readiness.py` + Hook in `match_engine.py`.

## Kalibrierte Schwellen
```python
DEFAULT_TACTIC_MATCHUP_THRESHOLDS = {
    "clear_underdog":  -0.070,
    "underdog":        -0.035,
    "balanced_upper":  +0.035,
    "favorite_upper":  +0.070,
}
# rel_diff = (own - opp) / ((own + opp) / 2)
```

## 5 Grundprofile (orientation / defense / midfield / attack / effort)
| Kategorie | orient | defense | midfield | attack | effort |
|---|---|---|---|---|---|
| clear_underdog | 30 | kompakt_stehen | absichern | unterstuetzen | normal |
| underdog | 38 | kompakt_stehen | absichern | unterstuetzen | normal |
| balanced | 50 | standard | standard | standard | normal |
| favorite | 62 | hoeher_stehen | nachruecken | abwehrkette_binden | normal |
| clear_favorite | 72/65 | hoeher_stehen | offensiv_besetzen/nachruecken | strafraum_besetzen/abwehrkette_binden | hoch/normal |

## Linien-Anpassungen (auf Basis-Profil)
- `attack_vs_defense ≥ +5%`: Angriffsoption upgraden (unterstuetzen→standard→abwehrkette_binden)
- `attack_vs_defense ≤ −7%`: Angriffsoption downgraden
- `defense_vs_attack ≤ −7%`: Defensivoption verstärken (hoeher_stehen→standard→kompakt_stehen)

## Seiten-Priorierung (attack_focus)
Reihenfolge: ueber_links → ueber_rechts → durch_mitte → fluegelspiel
- Eindeutige Seite: ≥ 5% Vorteil UND > 2% Abstand zur zweitbesten
- Flügelspiel: beide Flanken ≥ 5%, Abstand zueinander < 10%, Zentrum schwächer

## Integration
- `apply_default_tactic_settings(own_setup, opp_setup)` in `match_readiness.py`
  - Nutzt `calculate_lineup_strength()` für Linienstärken (base_strength, kein Tagesform-Roll)
  - Nutzt `_compute_zone_strengths_for_setup()` für Zonenstärken
  - Speichert first_half/second_half/instructions/conditions auf dem TacticSetup
- Hook in `simulate_match()` Schritt 1b, nur für `managed_by_id is None`

**Why:** Trainerlose Vereine sollen nicht mit Static-Standard-Taktik spielen, sondern adaptiv reagieren. Trainer-Vorgaben bleiben unberührt.
