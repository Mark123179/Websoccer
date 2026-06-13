---
name: T009 Dismissals V1
description: Platzverweis-Logik (Rot + Gelb-Rot) reduziert Teamstärke; Verletzungs-Aufstellungssperre in ensure_default_tactic.
---

# T009 Dismissals V1

## Regel
Rote Karte und Gelb-Rot führen ab dem **Folgesegment** zur reduzierten Teamstärke. Der verwiesene Spieler wird aus `_calculate_lineup_strength` ausgeschlossen.

**Why:** Vorher lief die Simulation immer mit 11-Mann-Stärke, auch nach Platzverweis.

## How to apply
- `dismissed_pids: set` und `gk_strength_override: Optional[float]` als neue Parameter in `_calculate_lineup_strength()`.
- `_dismissal_this_segment()` ersetzt `_red_card_this_segment()` — gibt `(count, card_type)` zurück; Gelb-Rot nur wenn Team ≥ 2 Gelbe hat.
- `_resolve_dismissal()` wählt den Spieler; TW-Sonderlogik: Bench-TW → dessen Stärke für GK-Linie; kein Bench-TW → schwächster Outfielder × 0.6 als Not-TW.
- `h_dismissed_pids`, `h_gk_str_override` als Loop-Variablen vor dem 5-Minuten-Loop initialisieren.
- `dismissal_events` im Result-Dict von `_simulate_match_minutes` und `simulate_match`.
- In `simulate_match`: dismissed Spieler vormarkieren (`red_cards=1`), dann `_assign_cards_to_players` mit reduziertem red_remaining aufrufen.

## Verletzungs-Aufstellungssperre
`ensure_default_tactic()` filtert `is_ws_injured=True` Spieler aus der Lineup- und Bank-Auswahl. Fallback: wenn < 11 gesunde Spieler vorhanden, wird die Taktik unverändert gelassen.
