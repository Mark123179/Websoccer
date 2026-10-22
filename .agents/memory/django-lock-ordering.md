---
name: PostgreSQL-Sperren und implizite Sortier-Joins
description: Nullable Relations können über Meta.ordering auch ohne select_related eine Zeilensperre verhindern.
---

Bei gezielten Zeilensperren auch die implizite Modell-Sortierung prüfen.
Ein `Meta.ordering` über eine nullable Relation kann einen äußeren Join
erzeugen, selbst wenn die Abfrage kein `select_related` enthält oder
anschließend `values()` verwendet.

**Why:** Das Entfernen eines expliziten nullable Joins beseitigte einen
PostgreSQL-Fehler bei einer Identitätssperre zunächst nicht: Die Standardsortierung
über den optionalen aktiven Spieler führte denselben Join wieder ein.

**How to apply:** Für solche Sperr-/Snapshot-Abfragen eine lokale,
deterministische Sortierung verwenden und den Sperrumfang bei Bedarf explizit
auf die Ausgangstabelle begrenzen. Verbundene nullable Entitäten separat
sperren, statt die Modell-Sortierung global zu ändern.
