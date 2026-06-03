---
name: current_manager_club Bayern fallback trap
description: The function used to fall through to the Bayern fallback for authenticated users with no club, silently breaking every user_has_no_club guard in templates.
---

# current_manager_club — authenticated-user branch must return None explicitly

## The rule
When `user` is an authenticated Django user, the function must `return None` inside the `except` block — not `pass` (which falls through to the Bayern fallback).

**Correct shape (game/views.py):**
```python
if user is not None and getattr(user, 'is_authenticated', False):
    try:
        profile = user.manager_profile
        club = Club.objects.select_related('league').get(managed_by=profile)
        return club
    except (Club.DoesNotExist, AttributeError):
        return None   # ← must be explicit return, NOT pass
# Bayern fallback only reached for anonymous / no-user callers
return Club.objects.filter(fm_inside_id=915).first() or ...
```

**Why:** `pass` silently falls through to the Bayern fallback, so `user_has_no_club = (current_manager_club(user=request.user) is None)` is always `False` for logged-in users — every `{% if user_has_no_club %}` guard in home.html becomes dead code.

**How to apply:** Any time you add logic that depends on `user_has_no_club`, verify in a shell that `current_manager_club(user=<no-club-user>)` returns `None`, not a Club instance.
