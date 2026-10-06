---
name: Authenticated preview screenshots
description: How to capture an authenticated app_preview screenshot when the screenshot browser is logged out.
---

# Authenticated preview screenshots

The `screenshot` (app_preview) tool uses a fresh, **unauthenticated** browser context — it
lands on `/auth/login/` for any `@login_required` page, so it cannot see manager screens by default.

**Safe verification:** use the testing browser with an authenticated session.
Never remove `@login_required` to take a screenshot. For a strict no-game-writes
pilot, prepare a short-lived Django session for an existing authorized account
without calling login/force_login, since those can update last_login or signals.
Keep cookie material in an owner-only temporary file, never echo it, and remove
both the session and file after the browser pass.

**Why:** The pilot's display review must preserve all game data, while login
signals can mutate account activity. Authentication must stay enforced throughout
verification, not merely be restored before delivery.

**How to apply:** Use the pilot's own session engine/signing settings and an
existing staff account; don't change passwords, roles, manager assignments, or
game rows. Test-client force_login is appropriate in an isolated test database,
not a real pilot with a strict fingerprint contract.
