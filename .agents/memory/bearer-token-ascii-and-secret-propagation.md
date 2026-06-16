---
name: Bearer-Token ASCII + Secret-Propagation
description: Why importer/API bearer tokens must be ASCII, and why a workflow restart after a secret change can still see the old value.
---

# Bearer tokens must be ASCII (hex), never Umlaute/Emoji

**Rule:** Any secret used as an HTTP `Authorization: Bearer <token>` value MUST be a
pure ASCII string (e.g. `secrets.token_hex(32)` → 64 hex chars). Do not accept
Umlauts/emoji.

**Why:**
- WSGI decodes incoming HTTP header values as **latin-1**, but `os.environ`
  decodes the secret as **UTF-8**. The *same* non-ASCII token therefore arrives as
  a *different* Python string on each side (e.g. `ä` → mojibake `Ã¤`), so the
  comparison can never match — every request 401s even though the token "looks
  right".
- `hmac.compare_digest(a, b)` with two `str` raises `TypeError` if either contains
  non-ASCII → 500, not 401. Always `.encode('utf-8')` both sides before comparing.

**How to apply:** Keep `_tokens_equal()` comparing UTF-8 bytes (no-crash → graceful
401). When requesting the secret, explicitly tell the user to use ASCII/hex only.
Trying to "recover" non-ASCII via latin-1 re-encoding is client-dependent and
fragile (Python `requests` sends header str as latin-1, curl sends UTF-8 bytes) —
do not go down that road; require ASCII.

**Debug-leak trap:** Do NOT `print(repr(provided_token))` to diagnose — that writes
the secret in plaintext into the workflow logs. If it happens, the secret is
compromised and must be rotated.

# Secret change requires a restart AFTER propagation

**Rule:** `os.environ.get()` is read at process start. After adding/rotating a
secret, the **dev server must be restarted**, AND the restart must happen *after*
the new value has actually propagated to the environment.

**Why:** A `restart_workflow` issued in the same turn as the secret request can race
ahead of propagation — the server then boots with the OLD value while a fresh
`bash` shell already has the NEW value, producing a confusing 401 on a token that
is correct in the shell. The fix was a second restart once the secret was
confirmed present.

**How to apply:** After the "secrets have been added" confirmation, verify the
value in `bash` (`os.environ`), then restart `Start application`, then smoke-test.
