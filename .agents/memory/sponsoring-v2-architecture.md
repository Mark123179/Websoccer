---
name: Sponsoring-Modul V2 Architektur
description: V2-Slot-System (5 Slots), Verhandlungsmechanik, Ledger-Buchungen — Designentscheidungen und Fallstricke
---

# Sponsoring V2 — Architektur & Entscheidungen

## Slot-System
5 Slots: `haupt | trikot | ausruester | stadion | tv` (Konstante `SLOTS` in sponsors.py).
Jeder Slot hat genau einen aktiven `SponsorContract` pro (club, saison).

## Buchungs-Hierarchie
- **V2-First**: `_book_sponsor_income` prüft `get_active_contracts(club, saison)` zuerst
- **V1-Fallback**: Nur wenn keine Contracts vorhanden → `get_active_offer(gewaehlt=True)`
- **KEIN Auto-Finalize im Matchday-Run**: `finalize_contracts_for_club` darf NICHT automatisch
  innerhalb von `_book_sponsor_income` aufgerufen werden — bricht Idempotenz-Tests
  (erzeugt Extra-Buchungen beim Repair-Lauf)

## Verhandlung (Push)
- Deterministisch via SHA-256(`f"push:{offer.pk}:{runde}"`)
- 50% Gewinn / 50% Malus (`RISK_MODE='malus'`: fix_aktuell -= fix_start * RISKS[runde])
- `RISK_MODE='verlust'`: status='abgesagt' (konfigurierbar)
- Max-Runden aus `EconomyParameter('SPONSOR_PUSH_MAX_ROUNDS')`

## Phasensperre
`accept_offer_v2(offer, auto=False)` prüft `LeagueSeasonState.current_matchday > 1`
→ wirft `SponsorAcceptError` wenn Fenster geschlossen

## Auto-Pick (finalize_contracts_for_club)
Muss explizit aufgerufen werden (Management-Command oder `finance_season_open`).
Wählt günstigstes `sicherheit`-Angebot wenn kein anderes Angebot accepted.

**Why:** Auto-Pick im Matchday-Run würde idempotente Repair-Läufe brechen,
da neue Contracts neue Buchungen erzeugen die der Marker-Check nicht antizipiert.

## Felder fix_start / fix_aktuell
- `fix_start`: Ursprüngliches Angebot in € (BigIntegerField)
- `fix_aktuell`: Aktuell ausgehandelter Wert nach Push-Runden
- `fix_betrag`: Legacy-Feld (DecimalField) für V1-Kompatibilität
- View benutzt `o.fix_aktuell if o.fix_aktuell is not None else int(o.fix_betrag)`

## URL-Struktur
- GET  `/management/finanzen/sponsoring/?slot=haupt` → management_sponsoring
- POST `/management/finanzen/sponsoring/annehmen/`  → management_sponsoring_accept
- POST `/management/finanzen/sponsoring/verhandeln/` → management_sponsoring_push

## Admin-View Fix (admin.py)
`finance_completeness_view` setzt jetzt nach Re-Run eine Django-Message (SUCCESS/WARNING)
zusätzlich zur Session-Speicherung — war vorher fehlend (Tests erwarteten Message).
