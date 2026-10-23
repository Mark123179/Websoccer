---
name: Englische Vereinspakete und aktive Leihspieler
description: Freigegebene Premier-League-Zuordnung im Workspace und Schutz laufender deutscher Spielstände.
---

Englische Vereinspakete gehören in eine eigene Premier League in England,
zunächst nicht spielbar. Die bestehenden beiden deutschen Ligen bleiben
unverändert. Die Freigabe gilt für den Workspace, nicht für Produktion.

**Why:** Der Nutzer bestätigte ausdrücklich „Ja, Premier League anlegen und
vier Vereine importieren“. Eine weitere Liga ist keine Freigabe für ihren
Spielbetrieb oder für Änderungen an der Bundesliga.

**How to apply:** Weitere angeforderte englische Pakete derselben Liga
zuordnen, statt sie über die deutsche Standardzuordnung einzuspielen.
Weder Saison noch Spielplan initialisieren oder die Liga automatisch aktivieren.

Ein ausländisches Stammvereinspaket darf einen bereits in einer spielbaren
Liga eingesetzten Leihspieler nicht erneut initialisieren.

**Why:** Der Stammverein liefert einen statischen Quellenstand, während der
entleihende Verein bereits einen laufenden Simulationszustand besitzt. Ein
erneuter Import darf Fortschritt, Stärke, Historie oder Rückennummer nicht
auf den Quellenstand zurücksetzen.

**How to apply:** Nur eine eindeutig übereinstimmende Leihe mit identischen
Spieler-IDs, Geburtsdatum, Eigentümer, Einsatzverein und Leihende übernehmen.
Bestehende Daten und Belege erhalten; lediglich bereits belegte, zuvor
unaufgelöste Vereinsverweise ergänzen. Widersprüche stoppen den Import.
Eine Auslassung im Stammvereinspaket darf den aktiven Spieler nicht aus
dem Kader entfernen.

Historische Nachlieferungen sind keine Freigabe, einen ansonsten identischen
Kader erneut zu initialisieren.

**Why:** Eine erneut gelieferte englische Vereinsdatei korrigierte nur einen
historischen Trainerrekord. Die Spieler-, Vereins- und Stadionquellen waren
identisch und mussten für diese Berichtigung nicht erneut angewendet werden.

**How to apply:** Bei solchen Nachlieferungen nur die geänderten historischen
Fakten samt Quellenarchiv übernehmen. Bestehende Spielerzustände, Stärken
und Bezüge erhalten; frühere historische Personen nicht global löschen.
