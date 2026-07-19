---
name: PlayerClubHistory (Phase 0 Finanzsystem)
description: Vereinsstationen-Tracking für die Ausbildungsabgabe — Erfassungsregeln, Suppress-Flag, Karrierende-Ausschluss, deferred-load-Falle
---

# Vereinsstationen-Tracking (Phase 0 Finanzsystem)

`PlayerClubHistory(player, club, season)` — eine Zeile pro angefangener Saison
pro Verein, Unique-Constraint. Grundlage der späteren Ausbildungsabgabe.

## Erfassungsregeln (User-Entscheidungen, verbindlich)
- **Creator-Mode- und Django-Admin-Edits erzeugen KEINE Zeile** — sie gelten als
  Datenkorrekturen. Mechanik: `player._suppress_club_history = True` vor `save()`.
  **Why:** User-Entscheidung (2026-07-19); manuelle Zuweisungen korrigieren meist
  Fehlzuordnungen und sind keine echten Ausbildungsstationen.
  **How to apply:** Jeder NEUE manuelle Edit-Pfad (Views, Admin-Actions) muss das
  Flag setzen; jeder echte Transfer-Pfad (Scouting, Importer, künftiges
  Transfersystem) darf es NICHT setzen — Erfassung läuft automatisch über
  `Player.save()`.
- Vereinslos (club=None) und Pseudo-Verein „Karrierende" erzeugen keine Zeile.
- Saison 0 = Sim-Start (Genesis-Seed gelaufen, 500 Zeilen).

## Karrierende-Erkennung per NAME, nicht pk
Prod hat Karrierende als pk=1, aber in Test-DBs bekommt der erste angelegte
Verein pk=1 → Ausschluss NUR über Namen (`karrierende`/`karriereende`,
case-insensitive) in `game/club_history.py`. Verein nie umbenennen.

## Deferred-Load-Falle (N+1)
`Player.from_db` stasht `_loaded_club_id` — dabei NUR `__dict__.get('club_id')`
lesen: Attributzugriff auf deferred Felder (`.only()`-Loads ohne club, z. B.
match_readiness) löst sonst eine Nachlade-Query PRO Instanz aus.
Wenn old-Wert unbekannt (Sentinel) und club gesetzt wurde: alten Stand vor
`super().save()` per `values_list` holen, sonst gehen echte Wechsel verloren.

## Saisonwechsel & Reparatur
- `GameSeasonState.save()` macht bei erhöhter `current_season` einen Snapshot
  (bulk_create ignore_conflicts); Fehler werden geloggt, blockieren aber nicht.
- Idempotenter Reparatur-/Genesis-Pfad: `python manage.py
  seed_player_club_history [--season N]` bzw. `snapshot_season(N)`.
