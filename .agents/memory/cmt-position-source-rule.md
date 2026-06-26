---
name: CMT position source rule
description: TM.de is sole source for WS player position fields; CMT positions are diagnostic-only.
---

## Rule

`Player.position`, `main_position_1`, and `secondary_position_*` must **never** be set from CMT data.
CMT position data (`info.positions`, `roles[*].pos`, `info.preferredposition`) is stored only as `cmt_pos_raw` for diagnostics.

## Enforcement

`create_player_from_cmt_raw(raw, db_slug, ws_club=None, dry_run=False, tm_position=None)`:

- If `tm_position is None` → returns `{'status': 'blocked', 'reason': 'TM-Position fehlt …'}` immediately.  
  No `Player.objects.create()` is called. Dry-run also returns `blocked` (no ST preview).
- If `tm_position` is provided → `Player.position = tm_position`, `main_position_1 = tm_position`.
- `_cmt_position_to_ws(raw)` is still called but its WS code is discarded; only `cmt_pos_raw` (the raw label) is kept.

`import_cmtracker.py` `_auto_create_players` always passes `tm_position=None` (no TM data in CLI path).
Blocked players are displayed as `⊘ BLOCKIERT: TM-Position fehlt → kein aktiver Auto-Create`.

## Why

Correct player positions require squad membership context that only TM.de provides.
CMT has no reliable squad-role information — its position fields map to EA FC roles,
which silently fell back to ST for CDM/RB players (Palhinha, Boey, Zaragoza, Ibrahimović case).

## How to apply

- Any future code path that calls `create_player_from_cmt_raw` for real player creation **must** pass `tm_position` from a TM CSV or TM import row.
- Test helpers that test player-creation behavior must pass `tm_position='ZM'` (or appropriate) explicitly.
- Tests that test the blocked path call `_auto_create(self.raw)` without `tm_position`.
- The `NoTmPositionBlockTest` class (8 tests) is the canonical coverage for this rule.
