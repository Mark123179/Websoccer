---
name: News cleanup safety
description: Why destructive news cleanup requires paused writers and protects both migration snapshots.
---

News-image deletion requires quiescent news writers, including migrations and
restores; an operator confirmation is not an automatically enforced maintenance
mode. Never describe a reference recheck or a seven-day grace period as sufficient
protection against concurrent reuse of an old image URL.

**Why:** File storage and article persistence cannot share a transaction. A pending
publication can reuse an old URL after a cleanup reference scan. This deliberate
operational prerequisite avoids changing publication/profile upload behavior.

**How to apply:** Keep cleanup opt-in and document the pause/drain requirement.
If online cleanup is requested later, coordinate all writers with a real lock and
validate reused image references inside that coordination, rather than removing
the operator prerequisite alone.

Migration snapshots must protect both their original and migrated image
references even after an article is restored or deleted.

**Why:** The requested restoration guarantee is stronger than retaining only
images currently referenced by an article.

**How to apply:** Treat unreadable backups as a reason to stop, not as unused
data. In Replit, consider local historical storage as well as the bucket because
media delivery reads both.

Cleanup reference discovery must follow all historical rendering sources, not
just the current upload payload.

**Why:** Legacy/default cards can render a thumbnail field even when their upload
JSON and main image field are empty. An upload-only inventory would classify a
live article image as orphaned.

**How to apply:** When rendering gains a new persisted image source, extend the
cleanup protection inventory and add a reference-only regression case.