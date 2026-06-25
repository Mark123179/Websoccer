---
name: Secret rotation & leaked-dump cleanup
description: What the agent can vs. cannot do when secrets leak into committed files / git history
---

# Secret rotation after a leak

Django `SECRET_KEY` is read from the environment with a per-process random
fallback: `os.environ.get('SECRET_KEY') or get_random_secret_key()`. DB config
reads `DATABASE_URL` (sqlite fallback). No secrets are hardcoded in
`core/settings.py`.

**Why:** Debug error-page dumps (`attached_assets/Pasted-*.txt`) were committed
with real secrets (SECRET_KEY/SESSION_SECRET, DATABASE_URL, PGPASSWORD,
REPLIT_DB_URL). `.gitignore` now blocks `attached_assets/Pasted-*.txt|.html`.

**How to apply — agent capability boundaries (non-obvious):**
- Agent CAN: remove hardcoded secrets from code, request a fresh `SECRET_KEY`
  via `requestEnvVar` (user sets it as a Secret; never print the value).
- Agent CANNOT: rotate platform/runtime-managed creds (`DATABASE_URL`,
  `PGPASSWORD`, `REPLIT_DB_URL`) — those need the Replit DB/secrets tooling;
  `setEnvVars` refuses secrets and the env-secrets skill forbids touching
  runtime-managed DATABASE_URL.
- Agent CANNOT: rewrite git history (VCS is platform-managed; destructive
  history rewrite must run as a protected background/platform task, not the
  agent shell). So leaked values stay in history until rotated — rotation, not
  rewrite, is what actually neutralizes the exposure.
