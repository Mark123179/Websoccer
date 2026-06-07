---
name: Economy / Balancing design principles
description: Core rules for Websoccer's financial simulation — what makes it fun vs. broken.
---

## Core principle

Every significant sporting decision must have a financial consequence. The economy exists to create meaningful trade-offs, not just to track numbers.

## Balance checklist (apply when adding any money-touching feature)

1. Does this feature create new money in the system? → needs a counter-cost
2. Does it benefit only rich clubs? → add a scaling mechanism for small clubs
3. Can the player exploit it infinitely? → add a cap or cooldown
4. Does it drive long-term wage/market-value inflation? → add depreciation logic
5. Is the best option always obvious? → if yes, the feature is a non-decision; redesign

## Salary > transfer fee (long-term rule)

Wages must matter more than one-time transfer fees over a full season. Star players should be expensive to keep, not just expensive to buy. This prevents "buy one superstar and coast" strategies.

## Market value formula inputs

Age + Strength + Potential + Position scarcity + Contract length remaining. Very young high-potential players = valuable but risky. Old strong players = short-term boost, high wage, low resale.

## Hard no-gos

- No unlimited income source without risk or counter-cost
- No transfer without follow-up costs (salary, agent fee, etc.)
- No mechanic where the richest strategy always wins
- No endless linear budget growth without a sporting trigger

**Why:** These principles were written before any economy was implemented. They guide feature design so balancing problems are caught early rather than retrofitted.

**How to apply:** Before implementing any feature involving money, transfers, salaries, sponsors, stadium, youth, or prize money — run through the checklist above.
