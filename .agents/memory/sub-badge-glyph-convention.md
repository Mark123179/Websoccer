---
name: Substitution badge glyph convention (match report)
description: In/out substitution markers on player photos must use distinct glyphs, not just color
---

On the match report page, the round on-photo `.sub-badge` markers now use **shape**, not just color,
to distinguish substitution direction: `.sub-badge.on` (bench player who came on) is a green up-arrow
(↑), `.sub-badge.off` (starter who was subbed out) is a red down-arrow (↓).

**Why:** They previously both rendered the same bidirectional-arrow glyph (⇆), differing only by
badge color — ambiguous at a glance and for anyone who can't rely on color alone. The rest of the
match report already used ↑ (in) / ↓ (out) elsewhere (bench-row minute label, Auswechslungen list),
so aligning the photo badges to that existing convention was the natural fix rather than inventing
a new icon language.

**How to apply:** The generic `.sub-badge.inline` marker used in the Auswechslungen list row (next
to a swap's minute, not on a specific player photo) intentionally keeps the ⇆ glyph — it marks
"a substitution happened here" as an event, not a specific in/out direction, and was already
explicitly approved. Don't change that one for "consistency"; only the on/off directional badges
needed the fix.
