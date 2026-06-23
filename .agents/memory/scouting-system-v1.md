---
name: Scouting-System V1 design decisions
description: Durable money-safety, settlement, and authz decisions for the Scouting subsystem (game/scouting/).
---

# Scouting-System V1 design decisions

## Per-club Club row lock IS the serialization point (do not add bid-row locks to place_bid)
`place_bid` does `Club.objects.select_for_update()` at the top and holds it for the whole txn. Because
every budget/slot/commitment/coin-affecting op for a club must take that same Club row, concurrent bids
for one club are fully serialized — no overspend even though `reserved_budget()` / `reserved_slots()` /
`commitment_used()` are plain aggregates (not select_for_update).

**Why:** `resolve_due_windows` locks **bids → then Club** (in `_settle_win`). If you ADD bid-row
select_for_update to `place_bid`, its order becomes **Club → bids**, creating a classic lock-ordering
deadlock cycle with resolution. Don't. The Club lock already gives the guarantee.

**How to apply:** Keep the Club lock as the single per-club gate. Concurrent `withdraw_bid` only makes
`place_bid` more conservative (never an overspend), so it needs no extra coordination.

## Coin-earmarked bids must consume a coin at settlement or LOSE
`coin_earmarked` is set at bid time when commitment > base slots and a coin was available, but the coin
is **not** consumed until the window resolves. Coins can be spent elsewhere in between. So `_settle_win`
re-checks the (locked) HoenessCoin: no consumable coin → `_settle_loss` (player NOT transferred), never
a free transfer at the limit.

**Why:** locked decision "bids beyond 2 require earmarked coin capacity; coin consumed on win." Awarding
a WON bid with `coin_used=False` would hand out a transfer the manager can't pay for in coins.

## Creator-area authz convention = @login_required only
The entire `/creator/` namespace (club/player/manager/coin editors) is gated by `@login_required` ONLY —
no staff/role check anywhere. This is a single-player local game where the logged-in user is the admin.

**How to apply:** New creator views (incl. scouting creator/overview/moderation) must match this — do NOT
add a divergent role gate to just one corner. A role-based creator gate would be a separate cross-cutting
task for the whole namespace.

## Never expose base_strength / potential
Coverage map contract to the frontend = iso2/name/continent/region/status/coverage_percent/coverage_label/
hint ONLY (never pool_count). Find/bid/result rendering must never leak `base_strength` or `potential`.
