---
name: News archive pagination rationale
description: Why archive loading uses separate streams and stable cursors rather than offset pages.
---

Beim News-Nachladen Vereins- und Social-Beiträge getrennt begrenzen und stabile Cursor statt Offset-Seiten verwenden.

**Why:** Ein stark gefüllter Social-Bestand darf die neuesten Vereinsartikel nicht aus der ersten Ansicht verdrängen. Veröffentlichungen und Admin-Löschungen zwischen zwei Abrufen dürfen keine Artikel überspringen oder doppelt liefern.

**How to apply:** Bei künftigen Archivänderungen beide Beitragsarten unabhängig prüfen und Pagination auch mit gleichem Veröffentlichungsdatum, einer neuen Meldung und einer gelöschten Seitengrenze testen.