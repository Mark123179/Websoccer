---
name: Design system tokens & rules
description: Canonical CSS custom properties and visual rules for the Websoccer dark dashboard.
---

## CSS tokens (defined in global CSS, use everywhere)

```css
--app-bg:       #03070c
--stadium-bg:   #07111a
--panel:        rgba(9, 23, 34, 0.82)
--panel-strong: rgba(12, 31, 45, 0.94)
--panel-soft:   rgba(17, 43, 58, 0.72)
--line:         rgba(44, 231, 255, 0.18)
--line-strong:  rgba(44, 231, 255, 0.38)
--cyan:         #22e6ff
--green:        #30f29c
--yellow:       #ffd166
--red:          #ff5570
--text:         #f4fbff
--muted:        rgba(244, 251, 255, 0.64)
--faint:        rgba(244, 251, 255, 0.38)
--radius:       8px
```

## Colour semantics

- **Cyan** = interactive / functional light (buttons, active states, links) — not decoration
- **Green** = fitness, pitch, form, positive sport values
- **Yellow** = warnings, coins, economic values (Hoeneß-Coin etc.)
- **Red** = errors, negative sport values, injuries

## Hard rules

- No bright / white backgrounds on the main screen — always dark stadium feel
- No marketing hero sections — first screen must be immediately usable data
- No nested cards (card inside card)
- Tables stay compact: modern rows, image columns, position badges
- All football assets (crests, player images) stay local, linked via `fm_inside_id`
- Base artboard: 1440 × 900 px; wide-shell CSS scope governs horizontal layout

**Why:** These are the founding design decisions; deviating creates visual inconsistency across the ~20 page templates already built.
