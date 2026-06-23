---
name: Clubless watchlist access
description: Which scouting features stay club-gated vs. are manager-bound and usable without a club, and how to resolve the manager.
---

# Clubless manager access to scouting

The Beobachtungsliste (watchlist) and community submissions are **manager-bound**:
they must stay fully usable (view + edit) for managers who have **no club**. The
rest of the scouting screen (assignments, finds, bids/auctions) stays
**club-gated**.

**Rule:** for manager-bound scouting features resolve the manager from
`request.user.manager_profile` (helper `_manager_of_user`), and let `club` be
`None` without redirecting. Use `current_manager_club()` only for the club-gated
parts.

**Why:** `current_manager_club()` is club-scoped and has the Bayern-fallback trap
(see current-manager-club-fallback.md); using it for the watchlist would either
crash clubless managers or silently bind them to the wrong club. The watchlist is
a personal manager artifact (`WatchlistEntry.manager`), independent of any club.

**How to apply:** when adding a scouting feature, first decide club-gated vs
manager-bound. Manager-bound add/remove endpoints take an arbitrary `player_id`
(any player may be watched) — parse it defensively (int + `.filter().first()`,
never let a bad id 500) and never emit `base_strength`/`potential` in search or
list payloads (public fields only: name/age/flag/position/market_value).
