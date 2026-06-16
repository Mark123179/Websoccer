---
name: CFM-Importer FMInside lookup
description: How the local cfm_importer reaches FMInside player pages, why it 404'd, and the unresolved FM-ID wiring gap.
---

# FMInside lookup in the local cfm_importer

Live-verified facts about fminside.net (June 2026) that drive the importer's
FMInside adapter (`tools/cfm_importer/cfm_importer/adapters/fminside.py`):

- **One-segment URL auto-redirects to the NEWEST DB version.** `GET
  /players/{id}-{anyslug}` → 200, redirects to the canonical
  `/players/7-fm262/{id}-{slug}` (newest). So **never hardcode a version path**
  (`7-fm-26` etc.) — the one-segment URL always lands on the latest. Verify the
  match by checking the id in the **final** (redirected) URL.
- **Slug is cosmetic but must be non-empty.** `/players/{id}-x` works;
  `/players/{id}` (no slug) redirects to the players LIST, not the player.
- **Two URL id-schemas coexist:** new `/players/{ver}/{id}-{slug}` and old
  `/players/{id}-{slug}`. Parse id with two-segment regex FIRST, else the
  one-segment pattern wrongly grabs the DB-version number (`7`).
- **`/search?q=` is DEAD (404).** The old name-search endpoint no longer exists.
  The real player filter is a stateful 2-step AJAX: POST
  `/resources/inc/ajax/update_filter.php` (serialized `form.filter`, incl.
  `uid`/`name`/`database_version`) then GET
  `/beheer/modules/players/.../generate-player-table.php?ajax_request=1` →
  `#player_table` HTML. Search form fields: `uid` (Unique ID), `name`,
  `database_version` (value `7` = FM26.2, the default/newest option).

## The real 404 cause + open gap

The importer **never receives an FM-ID**: `runner._build_candidate` sets
`fmi_id=tm_data.get('fmi_id') or entry.get('fmi_id')`, both sourced from
Transfermarkt, which has no FMInside IDs. So `_lookup_by_id` never runs and every
player falls to the (now-dead) name path → the user's observed FMI 404.

**Unresolved design decision (ask the user):** how should the importer obtain
each player's FM-ID so the Unique-ID lookup actually triggers?
- Option A: server includes the club roster (incl. `fm_inside_id` from the CSV
  import) in the claim/next response; importer matches its TM squad by
  name+DOB to get the FM-ID. (consistent with server-owns-data architecture)
- Option B: importer reads the Moneyball CSV locally and maps FM-IDs.

FM-ID cleaning (BOM, trailing `.0`, whitespace) lives in BOTH
`game/club_import/fmid_csv_service.py:clean_fm_id` (CSV import → DB) and the
importer adapter's `_clean_fm_id`.
