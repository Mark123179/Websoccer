---
name: Simulation-Diagnose Status-Klassifikation (Creator Mode)
description: Wann ein Diagnose-Feature/eine Ticker-Familie n/v (na) statt warn bekommt, und warum die Abdeckungsquote unmessbare Familien ausschließt.
---

# Simulation-Diagnose: na (n/v) vs. warn

Der Creator-Mode-Report (`game/simulation_diagnostics/`) bewertet Features und
Ticker-Event-Familien gegen eine Stichprobe von `report_data`-Dicts. Drei Status:
`ok` (aufgetreten), `warn` (messbar, aber in der Stichprobe nicht aufgetreten),
`na`/n/v (gar nicht aus `report_data` messbar). Früher wurde alles nicht
Aufgetretene pauschal `warn` → irreführend, weil es Code-Lücke suggerierte, wo gar
keine Messbarkeit existiert.

## Regel
- **warn** nur, wenn die Sache *messbar* ist (würde als Ereignis in `report_data`
  landen), aber in der Stichprobe ausblieb. Das ist ein echtes Signal.
- **na/n/v**, wenn die Sache prinzipiell nicht aus `report_data` ablesbar ist —
  entweder weil sie intern wirkt oder die Familie in Liga-Sims nie persistiert wird.

## Konkrete n/v-Fälle (durch Domänenwissen, nicht aus Code ableitbar)
- **Frische/Ermüdung** ist `internal`: `home/away_fatigue_cost` IST in `report_data`
  (Default **1.0** = Taktik-Multiplikator). Abweichung von 1.0 → `ok`, sonst `na`
  (kein eigenes Ereignis, wirkt nur intern). Feature-Dict trägt `internal: True` +
  `na_evidence`; `build_features` erzeugt dann `na` statt `warn` bei `match_count==0`.
- **Ticker-Familien** in `EVENT_FAMILY_UNMEASURABLE` (constants.py):
  - `save` → mappt nur auf `fk_saved`; normale Paraden stecken im Schuss-/Chancen-
    Tickertext, sind also keine eigene Ereignisart.
  - `kickoff`/`fulltime` → mappen nur auf `extra_time_*`/`penalty_shootout_*`, also
    K.-o./Pokal-only; in `ws_liga`-Ligasimulationen nie vorhanden.

## Abdeckungsquote (build_ticker_coverage)
- Nenner = **nur messbare Familien** (`measurable = supported - UNMEASURABLE`).
  Sonst drücken K.-o.-only-Familien die Quote künstlich.
- `supported_count = len(measurable)`, zusätzlich `unmeasurable_count` ausweisen.
- `never_triggered` enthält **nur** messbare-aber-nicht-aufgetretene Familien;
  n/v-Familien sind kein Fehlschlag und dürfen dort nie auftauchen.

## Positionsmatrix ist NICHT betroffen
`ws_liga`-`PlayerFormSnapshot`-Zeilen (season_service `_update_player_season_stats`)
enthalten Bank/Einwechsler (`is_sub`/`started`), lesen `minutes_played` pro Spieler
und Tore/Assists/Position aus den korrekten Feldern. Die Positionsdaten sind also
vollständig — kein analoges n/v-Problem; nicht spekulativ umbauen.
