---
name: Template-JSON XSS trap
description: Inline `{{ x|safe }}` JSON in <script> is a stored-XSS vector once user text lands in it
---

**Rule:** Never embed JSON into a `<script>` block with `|safe` if any field can ever contain user-submitted text. A payload containing `</script>` breaks out of the script block at parse time — client-side `esc()` on render does NOT protect against this.

**Why:** The Managerprofil timeline bootstrapped `MP_TL_EVENTS`/`MP_TL_CLUBS` via `|safe`; once "Eintrag einreichen" let managers persist title/body, that became stored XSS (found by review 2026-07-14).

**How to apply:** Use `{{ obj|json_script:"my-id" }}` in the template + `JSON.parse(document.getElementById('my-id').textContent)` in JS. In the view, pass a plain Python object; if it contains dates/Decimals, round-trip via `json.loads(json.dumps(obj, default=str))`. Regression test pattern: submit `</script><script>alert(1)</script>` and assert it never appears raw in page source (see game/tests/test_timeline_entry.py).
