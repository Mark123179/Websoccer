---
name: FMI position scraper
description: How to scrape fminside.net for FM player positions and convert to WS codes
---

## URL Schema
Two forms exist in the codebase:
- `populate_positions_fmi` command: `https://fminside.net/players/7-fm-26/{fm_inside_id}-{name-slug}` (`7-fm-26` = FM26 category; fallback fm-26 → fm-25 → fm-27 → fm-28)
- cfm_importer adapter (`_lookup_by_id`): `https://fminside.net/players/{fm_inside_id}-{name-slug}` (per user; slug cosmetic, ID maßgeblich)

- slug = firstname+lastname, lowercased, unicode-normalized to ASCII, spaces→hyphens
- Only players with `fm_inside_id` set in DB can be scraped by the command (76 total: Bayern 24, BVB 24, Gladbach 27, Frankfurt 1)

## HTML Structure
```html
<span class="mobile_position">
  <span position="st" title="Natural" class="position natural">ST</span>
</span>
<span class="desktop_positions">
  <span position="amc" title="Accomplished" class="position decent">AMC</span>,
  <span position="st" title="Natural" class="position natural">ST</span>
</span>
```
- `mobile_position` = primary (most natural) position
- `desktop_positions` = all positions including primary
- `title` attribute = proficiency: Natural (0) > Accomplished (1) > Competent (2) > Unconvincing (3) > Ineffective (4)

## FM → WS Code Mapping
```
gk→TW  dc→IV  dl→LV  dr→RV  wbl→LV  wbr→RV
dm→DM  mc→ZM  ml→LM  mr→RM
amc→OM  aml→LF  amr→RF  st→ST
```

## Command
`game/management/commands/populate_positions_fmi.py`

**Why:** FMI has richer role data than TM.de (secondary positions more accurate).
**How to apply:** Run with `--overwrite` after TM.de pass; FMI takes priority for the 76 players with fm_inside_id. Use `--club` flag to limit scope.
