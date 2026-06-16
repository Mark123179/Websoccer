---
name: Club/Player Import Engine (Creator-Mode)
description: Design constraints for the local-Windows club/player importer engine + data models (game/club_import/).
---

# Club/Player Import Engine

Lokaler Creator-Mode-Importer: Transfermarkt-Kader → WS-Spieler/-Vereine.
Reine Logik in `game/club_import/` (season, positions, normalization, parsing,
matching) + `import_service.py` (verbindlicher DB-Import). API/UI/lokaler
Importer bauen darauf auf.

## NULL-never-0 (harte Regel)
Fehlende Marktwerte/Höhe/Quell-Attribute/Quell-IDs bleiben **NULL/leer, nie 0**.
**Why:** 0 ist ein echter Wert und verfälscht den Stärke-Rechner; deshalb wurde
`Player.market_value` von `default=0` auf `null=True` umgestellt. Alle ~10
Lesestellen sind None-safe (`or 0`/`or ''`, Templatetag → "—").
**How to apply:** Parser geben bei leer/unparsbar `None`/`''` zurück — niemals 0.

## Stärke-Persistenz-Falle
`strength_service.compute_strength_for_player(player)` **berechnet nur** (gibt
dict zurück), persistiert NICHT. Persistenz: `PlayerStrengthProfile.base_strength`
schreiben (so wie `calculate_player_strengths` command). Import macht das pro
Spieler **innerhalb** der `transaction.atomic()`-Klammer (all-or-nothing).

## Platzhalter-Vereine
Reale Stamm-/Leihvereine werden als `Club(is_import_placeholder=True)` angelegt.
League ist Pflicht-FK → eine geteilte `League(name='Platzhalter (Import)')` wird
per get_or_create verwendet. Dedup-Priorität: `Club.transfermarkt_id`, dann
normalisierter Name.

## Matching-Priorität
TM-id → fm_inside_id → SoFIFA (PlayerExternalId, source__code=CODE_SOFIFA) →
Name+Geburtsdatum (nur Dublettenwarnung, `is_strong=False`, kein Auto-Überschreiben).

## HP/NP-Algorithmus (compute_positions)
HP≥25 (max 2), NP≥10 (max 2), immer ≥1 HP (sonst meistgespielte), Jugend-Fallback
auf Profilposition (sonst Fehler). Abgeleitete Zusatz-HP (LV+LM→LOV, RV+RM→ROV,
LM+LF→LOM, RM+RF→ROM) **nur wenn beide Ausgangspositionen HP sind**. Unbekannte
TM-Positionen werden gewarnt, nicht geraten. Mapping zentral in `TM_POSITION_MAP`.
