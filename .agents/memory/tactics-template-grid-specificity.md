---
name: Tactics template-grid specificity trap
description: Height changes to tactics panels must target .tactics-template-grid rules, not the generic panel rules — specificity mismatch causes silent overrides.
---

The actual height-controlling rule for the tactics page panels and side-stack is:

```css
.tactics-template-grid .tactics-preview-panel,
.tactics-template-grid .tactics-pitch-panel,
.tactics-template-grid .tactics-side-stack {
    height: 700px;  /* current value */
}
```

This sits in tactics.css around line 1815 and has specificity **0,2,0**.

The generic rules (`.tactics-preview-panel, .tactics-pitch-panel { height: ... }`) have specificity **0,1,0** and are silently overridden by the above. All height edits must target the `.tactics-template-grid` block.

**Why:** The template wraps everything in `<main class="tactics-template-grid">`, so all children carry the higher-specificity context. Editing only the lower-specificity rules has zero visible effect on the tactics page.

**How to apply:** Before changing any tactics panel height, grep for `.tactics-template-grid .tactics-*panel\|.tactics-template-grid .tactics-side-stack` and update that rule. The 586px default was too short for the Standards panel to show all 4 rows; 700px gives Standards ~194px which fits comfortably.
