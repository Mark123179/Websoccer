---
name: Merge marker detection
description: Decorative equals separators can block merge completion despite clean conflict resolution.
---

The merge-completion checker can flag a file containing seven consecutive equals signs anywhere, including a decorative comment, as still conflicted.

**Why:** A resolved JavaScript file passed syntax checking but merge completion refused it until its decorative equals-sign header was replaced with dashes.

**How to apply:** If all actual conflict markers are gone but completion still reports that file, search for marker substrings rather than only line-start markers. Replace purely decorative equals separators with dashes; do not remove real code or bypass conflict resolution.