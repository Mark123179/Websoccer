---
name: Match-report reference CSS extraction + pitch formation parsing
description: How to extract exact 1:1 CSS from the reference spielbericht HTML, and a formation-string parsing trap in the Aufstellungen pitch feature.
---

# Match-report reference CSS extraction

For a strict 1:1 rebuild of `game/templates/game/match_report.html` against
`attached_assets/spielbericht_1783681002812.html`, do not hand-guess property
values (border-radius, sizes, gradients) from a screenshot — grep the raw
reference HTML's `<style>` block directly (`content.find('.classname{')`) and
copy the exact declaration. Guessed values (e.g. `border-radius:50%` instead
of the reference's `13px`, or putting `clip-path` on the wrong element) look
plausible but are wrong and must be corrected against the source of truth.

# Grid-row image-slot alignment trap

When a row uses CSS Grid with a fixed-width first column for a player photo,
and the photo is conditionally rendered (`{% if p.portrait_url %}<img>{% endif %}`)
directly as a grid child, an empty case removes the grid item entirely and
shifts every subsequent cell one column left. Fix: always render a wrapper
element (e.g. `<span class="ph-slot">...conditional img...</span>`) as the
permanent grid child so the column is always reserved, even when there's no
portrait.

**Why:** silent grid misalignment only shows up for specific players (no
portrait), so it's easy to miss in a quick screenshot check with fully-populated data.

**How to apply:** any templated grid/flex row where an image or icon is
conditionally rendered as a direct grid/flex item.

# Formation-code string vs dict mismatch

`game/tactics.py`'s `formation_slots(formation)` / `normalize_formation()`
expect a **dict** (`{'defense': '4n', 'midfield': '4', ...}`), but
`SimulatedMatch.report_data['home_formation']` stores the **display string**
produced by `formation_code()` (hyphen-joined values in `FORMATION_ORDER`
order, e.g. `'4n-0-4-0-2'`). Passing the raw string into `formation_slots()`
fails silently inside a broad `try/except Exception` and the pitch feature
degrades to "no lineup data" for every single match — easy to miss since the
degraded state renders as a plausible empty-state UI, not an error.

**Why:** two different representations of "the same" formation exist in the
codebase (structured dict for `Tactic.formation`, flat string for display in
`report_data`) and there was no round-trip parser between them.

**How to apply:** before calling `formation_slots()`/`normalize_formation()`
on a formation value read from `report_data`, split it on `-`, zip against
`tactics.FORMATION_ORDER`, and validate each part against
`tactics.FORMATION_PARTS[part]` before use — never pass the raw string through.
