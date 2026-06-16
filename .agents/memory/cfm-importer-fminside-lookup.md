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

## The real 404 cause (root) + the chosen fix

The 404 root cause was that the importer **never received an FM-ID**: candidate
building sourced `fmi_id` only from Transfermarkt data, which has no FMInside IDs,
so the ID-first lookup never ran and every player fell to the dead name path.

**Resolved via Option A (server-owns-data):** at job *claim*, the Django app
returns the target club's roster (only players that already carry an
`fm_inside_id`, set by the CSV import) in the response. The local importer builds
a name+DOB index from that roster and resolves each Transfermarkt player to an
`fm_inside_id`, which then drives the unique-ID FMInside lookup.

**Matching safety rule (do not regress):** the roster matcher prefers exact
name+DOB, falls back to a unique-name match only when DOBs don't contradict, and
returns *no match* for any ambiguity — duplicate names without DOB, conflicting
DOBs, OR the same name+DOB mapping to different IDs. Never last-write-wins; a
wrong `fm_inside_id` would make the ID-first lookup scrape the wrong player
without a DOB recheck.

FM-ID cleaning (BOM, trailing `.0`, whitespace) is duplicated by design on both
sides of the wire (CSV-import path and the importer adapter).
