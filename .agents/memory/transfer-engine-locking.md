---
name: Transfer-Engine Lock-Ordnung + Doppelkauf-Schutz
description: Verbindliche Lock-Reihenfolge und Re-Validierungspflicht für alle geldbewegenden Transferpfade (Phase 4+).
---

# Transfer-Engine: Lock-Ordnung + Doppelkauf-Schutz

**Regel:** Jeder Pfad, der einen Spieler gegen Geld bewegt, muss innerhalb
der Transaktion (1) Club-Zeilen in sortierter ID-Reihenfolge sperren
(book_many-Konvention) und (2) DANACH die Spielerzeile per
`select_for_update` neu laden und `club_id == verkaeufer.pk` re-validieren.

**Why:** Architect-Review Phase 4 fand ein Doppelkauf-Race: Zwei Manager
bieten parallel auf denselben KI-Spieler; T2 wartete nur auf den
Verkäufer-Lock und arbeitete danach mit dem veralteten In-Memory-`player.club`
weiter → Verkäufer doppelt bezahlt, Spieler beim zweiten Käufer. Der Guard in
`accept_counter` allein reicht nicht, weil ein fremder Bieter dessen
Verhandlungszeile nie berührt.

**How to apply:** Globale, zyklenfreie Lock-Ordnung ist überall:
Verhandlungszeile → Club-Zeilen (sortiert) → Spielerzeile. Kein neuer Pfad
darf andersherum sperren. Bei parallelen Erst-Geboten fängt der partielle
Unique-Index auf offene Verhandlungen die Kollision — IntegrityError als
fachlichen deutschen Fehler zurückgeben, nie als 500 durchreichen.
Phase 6 (KI-Käufer) nutzt dieselbe Abwicklung und erbt diese Pflichten.
