---
name: Transfer v2 Ereignis-Schicht (Gerüchte/Push/Ticker)
description: Architekturregeln der gemeinsamen Event-Schicht des Transfersystems v2 — Isolation, Richtungs-Konvention, Vollständigkeit, Aufsichts-Routing, Gerüchte-Würfel.
---

# Transfer v2 Ereignis-Schicht

**Regel 1 — Isolation:** Gerüchte-, Push- und Ticker-Nebenwirkungen laufen ausnahmslos über einen zentralen Nach-Commit-Dispatch (`transaction.on_commit`) — NICHT bloß „nach dem lokalen atomic-Block“, denn Services können in einer umgebenden Transaktion aufgerufen werden; nur on_commit garantiert Ausführung nach dem dauerhaften äußersten Commit und nie bei Rollback. Der GESAMTE Auslöser inkl. Empfänger-Lookups muss fehler-isoliert sein (loggen, nie propagieren).
**Why:** Ein Geldvorgang darf nie an der Ausspielung scheitern; Hooks vor dem echten Commit können bei Rollback bereits ausgespielt worden sein; eine fehlgeschlagene Empfänger-Query darf nach erfolgreichem Commit nicht mehr hochschlagen.

**Regel 2 — Richtungs-Konvention:** Events beschreiben den Wechsel aus **Spieler-Sicht** (abgebender Verein → aufnehmender Verein), NIE aus Initiator-Sicht des Deals. Bei Deals die Richtung aus den Record-Spielerseiten ableiten (Side A wechselt A→B, Side B wechselt B→A) — ein Kaufangebot des Initiators für einen fremden Spieler hat die umgekehrte Richtung. Der reaktionsberechtigte Verein ist der abgebende.
**Why:** Die Richtungs-Ableitung muss auf ALLEN Anzeigeflächen (Gerüchte, Vereinsnews, Historie, Ticker) gleich sein, nicht nur bei der Gerücht-Erzeugung.

**Regel 3 — Vollständigkeit:** JEDER vollzogene Vorgang ist ein Event — auch gezogene Kaufoptionen und Leih-Rückkehr (eigener Textpool, gleicher Event-Typ wie Leihstart). Neue Abschlusspfade brauchen einen Hook.

**Regel 4 — Aufsicht ist echter Workflow:** Eine „Meldung an die Aufsicht“ ist erst fertig, wenn die Aufsicht sie sehen UND bearbeiten kann: Routing an Staff-Manager mit Bearbeitungs-Link, Admin-Registrierung mit Statuswechsel, Ergebnis-Push an den Melder bei Entscheidung. Eine reine Eingangsbestätigung an den Melder genügt nicht.

**Gerüchte-Würfel:** Wahrscheinlichkeiten als EconomyParameter (je Event-Typ + Exakt/Spanne); max. 1 Gerücht pro (Spieler, Event-Typ, Tag) — DB-erzwungen: UniqueConstraint auf persistiertem Dedup-Tag PLUS CheckConstraint „Spieler ⇒ Tag gesetzt“ + Autofill in save(), sonst ist die Dedup per ORM/bulk_create umgehbar; exists()-Vorprüfung allein ist race-anfällig; IntegrityError im eigenen Savepoint sauber schlucken. Spannen ±20 % auf glatte Mio. Kein Typ-Enum auf Notification — Push-Katalog unterscheidet per Titel/Text.
