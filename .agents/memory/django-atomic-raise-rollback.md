---
name: Django atomic-Raise-Rollback-Falle
description: Terminal-Status vor einem Fehler-Raise speichern rollt zurück, wenn der Raise noch innerhalb von transaction.atomic() passiert
---

# Terminal-Status + Raise innerhalb von transaction.atomic()

Muster `o.status = ABGELAUFEN; o.save(); raise DomainError(...)` INNERHALB
eines `with transaction.atomic():`-Blocks persistiert NICHTS — der Raise
verlässt den atomic-Block mit Exception und rollt den Status-Save mit zurück.
Das Objekt bleibt still im alten Status (z. B. 'versendet'), der Fehlerpfad
sieht in Tests korrekt aus, solange niemand den persistierten Status prüft.

**Why:** Genau so blieb im KI-Käufer ein abgelaufenes Angebot nach später
Manager-Reaktion auf 'versendet' und war weiter eskalierbar; die Guards waren
vorhanden, aber ihre Status-Saves wurden zurückgerollt.

**How to apply:** Fehlermeldung im atomic-Block nur sammeln (`fehler = '…'`),
Status speichern, atomic normal verlassen (Commit) und ERST DANACH raisen.
Tests für solche Fehlerpfade müssen nach dem erwarteten Raise den
persistierten Status per `refresh_from_db()` asserten — sonst ist die Falle
unsichtbar (Django-TestCase macht atomic zu Savepoints, Verhalten identisch).
