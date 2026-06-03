---
name: Squad/club mutation auth + CSRF wiring
description: How to secure AJAX POST endpoints (shirt number, move-to-youth, etc.) given session-based CSRF and the manager→club ownership model.
---

# Securing club-scoped AJAX mutations

**CSRF is session-based** (`CSRF_USE_SESSIONS = True` in core/settings.py).
**Why:** there is NO `csrftoken` cookie, so JS that reads `getCookie('csrftoken')`
sends an empty header and every POST 403s in a real browser (the Django test
client hides this because it disables CSRF by default).
**How to apply:** render the token in the template (`{{ csrf_token }}` into a
`data-csrf` attribute or `{% csrf_token %}` hidden input) and read it in JS for
the `X-CSRFToken` header. Do not rely on the cookie.

**Authorization model for "my club" mutations:**
- Add `@login_required` (matches existing mutation endpoints like
  update_manager_profile / set_trainer_type).
- Ownership check: `current_manager_club(user=request.user)` returns the Club the
  authed user manages (or None). Compare it to the URL's club and return 403 if
  they differ — `Player(id=..., club=club)` scoping alone does NOT stop IDOR
  across clubs.
**Why:** club squad VIEW pages are public, but mutating another club's players
must be blocked. Bayern (club_id=2) is managed by user `admin`.
