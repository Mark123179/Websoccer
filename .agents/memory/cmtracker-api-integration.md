---
name: cmtracker API integration
description: How the cmtracker player-ratings API is integrated and the auth/sandbox gotchas that cost real debugging time.
---

# cmtracker API integration

Imports EA/SoFIFA-style player ratings from cmtracker into Websoccer.

## Auth
- Base URL `https://api.cmtracker.net/api/v1`, header `X-API-Key` (secret `CMTRACKER_API_KEY`). Optional base-URL override via `CMTRACKER_BASE_URL`.
- The portal docs (`api-dashboard.cmtracker.net/portal/docs`) are authoritative. There is an OLD/community API at `be.cmtracker.net` using `x-user-email`+`x-user-token` — that is NOT this API; ignore it.

## Bridge design (do not duplicate parsing)
- `game/cmtracker_api.py` is a thin read-only client that FLATTENS cmtracker JSON into the exact CSV column shape the existing live importer already understands, then feeds `game/sofifa_import_service.run_sofifa_import`.
- `CSV_COLUMNS` are dotted JSON paths (e.g. `info.playerid`, `attributes.stamina`). They map through the importer's `COLUMN_ALIASES` because `normalize_header` strips dots (`info.playerid`→`infoplayerid`→`sofifa_id`). Each column maps to exactly one target so nothing overwrites.
- **Why:** reuse the frozen parse / DOB-first match / logging / strength-recalc pipeline instead of re-implementing it.
- CLI trigger: `python manage.py import_cmtracker` (`--list-dbs`, `--dry-run`, `--sandbox`, filters). Creator-Mode UI button was deferred by the user.

## Sandbox vs live (critical)
- A **sandbox** key works from any IP but server-side **filters and pagination are DISABLED**. Use `--sandbox` → one param-free `GET /players` (db selector still allowed; filters/sort/page/limit omitted).
- Sandbox returns a **fixed ~25-player sample** (mixed leagues + women's football), NOT your league. So a real sandbox import only touches whichever of those happen to exist in the DB → creates mixed data. A full Bundesliga sync is only possible in live mode.
- A **live** key only works from **registered IP addresses** → will need a PROXY server to call from Replit. Coordinate IP registration with cmtracker before switching to live.

## Gotchas that wasted time
- `403 {"detail":"Invalid API key"}` with that CUSTOM message means the header WAS parsed and the key VALUE was rejected (credential/activation issue), NOT a code bug. It appears on every endpoint (`/dbs`, `/players`, `/players/{id}`) regardless of params.
- The demo site `demo.cmtracker.net` authenticates via a logged-in WEB SESSION (cookie) and sits behind Cloudflare. Being able to browse the demo does NOT prove the programmatic `X-API-Key` is valid — they are independent auth paths.
- FC26 latest db slug example: `26062400`. Demo player-page URL shape is `/players/{playerid}/{dbslug}` (frontend route, not the API route).

## Validation status (do not re-run the real import without reason)
- A valid key was confirmed; `--sandbox --dry-run` passes end-to-end (25 fetched, 2 DB matches via DOB, 23 expected non-matches). No real import has been run by request — a sandbox-only import is intentionally avoided to prevent mixed data.
- ID persistence is **already** handled by the importer: `_match_player` priority is id → dob → name, and a real import writes `PlayerExternalId(source=SOFIFA, external_id=info.playerid)`. So DOB is only the fallback after the first real import. If cmtracker ever exposes its own id distinct from the EA/SoFIFA id, add a separate `CMTRACKER` DataSource.
- Full technical doc: `docs/cmtracker_integration.md` (mapping, dry-run result, sandbox limit, live-mode plan).
