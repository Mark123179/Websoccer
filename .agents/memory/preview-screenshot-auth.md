---
name: Authenticated preview screenshots
description: How to capture an authenticated app_preview screenshot when the screenshot browser is logged out.
---

# Authenticated preview screenshots

The `screenshot` (app_preview) tool uses a fresh, **unauthenticated** browser context — it
lands on `/auth/login/` for any `@login_required` page, so it cannot see manager screens by default.

**Safe workaround for visual verification:** `current_manager_club(user=...)` returns the Bayern
fallback for an *anonymous* request (only the authenticated-user branch returns None on miss). So you
can temporarily comment out the `@login_required` decorator on the single view you need to screenshot,
restart the workflow, capture, then **restore the decorator immediately** and re-verify auth gating
(anon → 302 to login, auth → 200).

**Why:** This is a 1440×900 locked golden-master app with no dev/auto-login bypass, and you must not
ship one. The temporary-decorator trick leaves zero residue once reverted and never weakens shipped code.

**How to apply:** Only for a screenshot pass. Always grep for the bypass marker and confirm the
decorator is back before committing. Test-client `force_login()` GET (200) is the headless alternative
when a pixel screenshot isn't required.
