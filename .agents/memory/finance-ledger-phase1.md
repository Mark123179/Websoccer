---
name: Finanz-Ledger Phase 1
description: FinanceTransaction-Ledger, book()-Deckungsregel, Betriebskosten-Fenster, Idempotenz des Spieltagslaufs — Kernregeln für alle künftigen Finanz-Phasen.
---

# Finanz-Ledger Phase 1 — Kernregeln

## Buchungsregel (game/economy/booking.py)
- JEDE Kontobewegung läuft über `book()`/`book_many()` — nie `Club.budget` direkt mutieren.
- **Warum:** Ledger (FinanceTransaction) ist die Wahrheit, `Club.budget` nur Cache; direkte Mutationen erzeugen Drift, die der tägliche Integritätscheck als Alarm meldet.
- Deckungsregel: aktive Ausgaben (`pflicht=False`) werfen `InsufficientFunds`; Pflichtbuchungen (Gehalt/Betrieb/Unterhalt) dürfen ins Minus.
- `book_many` sperrt Club-Zeilen mit `select_for_update().order_by('pk')` — das `order_by` ist PFLICHT, sonst ist die Lock-Reihenfolge planabhängig (Deadlock-Risiko). Ein sortiertes Python-Set reicht NICHT.
- `log_club_transaction` (game/finance.py) ist nur noch Legacy-Wrapper und mutiert seit Phase 1 das Budget MIT — Aufrufer dürfen nicht zusätzlich selbst buchen (Doppel-Buchung).

## Betriebskosten-Fenster (matchday_run)
- Fenster = halboffen `(prev.run_at, run.run_at]`. Einnahmen des laufenden Laufs (created_at > run.run_at) fallen erst in den FOLGELAUF.
- **Warum:** Ohne Obergrenze wurde jede TV-/Ticket-Einnahme in zwei aufeinanderfolgenden Läufen mit der 34%-Quote belastet (effektiv 68 %). Architect-Fund; Regressionstest `test_betriebskosten_taxes_income_exactly_once` deckt zwei Läufe ab.
- **How to apply:** Neue operative Einnahmetypen in `OPERATIVE_EINNAHME_TYPEN` aufnehmen; Fensterlogik nie auf "created_at > window_start" allein reduzieren.

## Idempotenz & Hooks
- `FinanceMatchdayRun` (unique je Verein+Saison+Spieltag) macht den Lauf idempotent; Marker rollt bei Buchungsfehler mit zurück (eine Transaktion pro Verein).
- Hooks laufen NACH dem atomic-Block der Sim (season_service/play_matchday); Finanzfehler sind Warnungen, stoppen die Simulation nie.
- TV Phase 1 = Interim: `TV_INTERIM_RANG_JE_LAND` (Land→Rang), alle Ligen als "liga1"; echte Landeskoeffizienten kommen in Phase 2.

## Offene Risiken (Phase 2 beachten)
- Doppel-Ticket-Pfad: Signal `auto_record_matchday_revenue` (post_save MatchResult) UND `_book_tickets` im Finanzlauf buchen beide TICKET; derzeit kollisionsfrei (MatchResult nur manuell), vor Phase 2 dedupen/abschalten.
- `check_ledger_integrity(fix=True)` schreibt Budget ohne Lock — nur für manuelle Reparatur gedacht.
- Jedes `Club.save()` ohne `update_fields` kann den Budget-Cache mit stalem In-Memory-Wert überschreiben; täglicher Celery-Integritätscheck fängt das auf.
