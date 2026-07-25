---
name: Asset URL single source of truth
description: How ASSETS_BASE_URL must be wired — runtime read only, never frozen as a module constant.
---

# Asset URL single source of truth

## The rule
`game/asset_urls.py::_base()` reads `settings.ASSETS_BASE_URL` at call time.
No module-level constant (the old `ASSETS_BASE = _resolve_assets_base()` was the bug).

**Why:** Django settings are loaded after module imports in some startup paths.
A module-level constant that calls `settings.*` before the app is fully ready
can freeze to the wrong value (e.g. the dev fallback `/static/assets/` even when
`ASSETS_BASE_URL=/assets/` is in the .env). The old code also ignored
`settings.ASSETS_BASE_URL` entirely and had its own detection logic with a
hardcoded `https://playwebsoccer.de/assets/` string.

## How to apply
- All URL builders must call `_base()` (not `ASSETS_BASE`) — `_base()` re-reads settings each call.
- Do NOT import `ASSETS_BASE` from `asset_urls` anywhere. Use `_base()` or `settings.ASSETS_BASE_URL` directly.
- Context processor `current_manager` injects `assets_base_url` into every template.
- `base.html` sets `window.wsAssetsBase` and `window.wsDefaultPlayerUrl` for all JS.

## Production-critical .env entries
```
ASSETS_BASE_URL=/assets/
ASSETS_ROOT=/app/assets
```
Missing `ASSETS_BASE_URL` → server generates `/static/assets/` URLs → 404 for all images.
`ASSETS_ROOT=/app/assets` is a bind-mount of host `/var/www/assets`.
nginx serves `/var/www/assets` at location `/assets/`.

## JSON/report_data rule
Never use stored image URLs from `report_data` JSON as `src` directly.
Always call `player_face_url(fm_inside_id)` etc. at render time — old reports
may contain frozen `/static/assets/` paths from before the fix.
