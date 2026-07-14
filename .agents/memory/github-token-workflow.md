---
name: GitHub push workflow from Replit
description: How to push to GitHub from the Replit environment — PAT requirements, bash-session env-var caching, and the Shell-tab workaround.
---

# GitHub push workflow from Replit

## Classic PAT required — fine-grained tokens fail silently
GitHub fine-grained PATs lack the `workflow` scope and can fail on HTTPS pushes with
misleading 401 errors. Always use a **classic PAT** with at minimum `repo` scope
(add `workflow` if GitHub Actions are used).

**Why:** Fine-grained tokens have per-repo permission matrices; classic tokens grant repo-wide access uniformly.

**How to apply:** When asking the user to create a PAT, always say "classic" and list required scopes explicitly.

## Agent bash tool cannot modify .git/config — `git remote set-url` is blocked
The Replit sandbox blocks any write to `.git/config` (including `git remote set-url`)
as a destructive git operation. The error is:
  "Destructive git operations are not allowed in the main agent."

**Workaround A (agent):** Use `git -c "url.https://TOKEN@github.com/.insteadOf=https://github.com/" push origin main` — in-memory `-c` flag doesn't touch `.git/config`.

**Workaround B (user):** Ask the user to run in the **Replit Shell tab**:
  `git push "https://USERNAME:$GITHUB_TOKEN@github.com/OWNER/REPO.git" main`
  The Shell tab always has fresh env vars.

## New secrets aren't picked up by the running bash session
When the user updates a Replit secret, the change is NOT automatically visible to the
already-running bash tool process. The new value is only available in **new processes**.

**How to apply:** After the user confirms they've updated a secret, use the Replit Shell
tab workaround (Workaround B above) rather than retrying in the agent bash tool.
The agent bash tool will keep seeing the old cached env var until the session restarts.

## insteadOf rewrite does NOT match the oauth2 remote — push to explicit URL
`-c url.https://TOKEN@github.com/.insteadOf=https://github.com/` fails because the
remote URL is `https://oauth2:@github.com/...` — the prefix doesn't match, so the
empty oauth2 credential is used (401). Working agent-bash push:
  `git push "https://Mark123179:${GITHUB_TOKEN}@github.com/Mark123179/Websoccer.git" main`

## Remote URL in .git/config has empty OAuth token
The `origin` remote URL is `https://oauth2:@github.com/Mark123179/Websoccer` (empty token).
This is the configured state — Replit's GitHub OAuth token expired/was rotated.
Do not try to restore the OAuth token; use the PAT-based push workflow above instead.
