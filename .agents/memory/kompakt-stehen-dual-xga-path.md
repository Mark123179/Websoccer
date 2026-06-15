---
name: kompakt_stehen dual xGA path
description: kompakt_stehen has two separate xGA-reduction mechanisms; the defense_delta path is invisible to the compiler, creating a balance gap with offensive line options.
---

## Rule
Never assume the compiler's `xg_against` value fully predicts simulation xGA when `kompakt_stehen` is the defense option.

## Two Paths for xGA Reduction

| Path | Mechanism | Compiler-visible? | Size |
|---|---|---|---|
| A — `xg_against_delta` | Direct xGA multiplier (from line options like nachruecken, strafraum_besetzen) | ✅ Yes | varies |
| B — `defense_delta → line_multipliers["defense"] = 1.03` | Boosts defensive player strength 3% → engine reduces xGA via strength exponent 1.25 | ❌ No | ~−0.028 fixed |

## Measured DIFF (Compiler xGA − Simulation xGA)
- Any STD defense combo: DIFF ≈ +0.001 (zero)
- Any kompakt_stehen combo: DIFF ≈ −0.028 (constant, combo-independent)

Confirmed at n=20,000 mirrored matches:
- kompakt+nach+strafraum: DIFF=−0.0278
- kompakt+offensiv+abwehrkette: DIFF=−0.0278
- kompakt+absichern+strafraum: DIFF=−0.0275

## Balance Gap
Offensive line options (nachruecken, strafraum_besetzen, abwehrkette_binden) are designed with xGA costs (+0.012..+0.025 each via `line_xg_ag`). With kompakt_stehen, Path B negates ~75% of those costs, creating unintended net benefit combos.

## Confirmed Alarms (Freeze: no changes without ≥50-season evidence + explicit user approval)
- kompakt+offensiv_besetzen+abwehrkette_binden: PPG-Δ=+0.065, xGD-Δ=+0.063 [ALARM at n=12k]
- kompakt+nach+strafraum: PPG-Δ=+0.044, xGD-Δ=+0.069 [VERDACHT at n=20k]
- kompakt+absichern+strafraum: PPG-Δ=+0.043, xGD-Δ=+0.067, xGA-Δ=−0.034, c_risk=+0.01 [VERDACHT — cheapest cost]

## Why
kompakt_stehen's `defense_delta=+0.03` was added pre-dating the new per-half midfield/attack line options. The line options were balanced assuming defense path B is absent. When combined, the strengths stack invisibly.

## How to Apply
- When evaluating any kompakt_stehen combination via compiler alone: add −0.028 to the predicted xGA to get the actual simulation xGA.
- If addressing the balance gap: preferred fix is a coherence penalty on kompakt_stehen + offensive line options (analogous to tief_stehen+offensiv_besetzen+strafraum_besetzen → coherence −0.04), NOT changing defense_delta (which would break existing pre-Freeze balancing).
- Match Engine V2 Freeze (since 2026-06-12) applies: any fix requires explicit user approval.
