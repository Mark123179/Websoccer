---
name: Live-Ticker timing contract
description: User-approved playback budget and frozen narrator timing boundary.
---

Die Django-Brücke übernimmt `offset_s` und `duration_s` der vom Nutzer gelieferten Erzähler-Baseline unverändert. Die Gesamtdauer ist letzter Offset plus letzte Dauer: 900 Sekunden regulär, zusätzlich 300 bei Verlängerung, zusätzlich 8 je Elfmeterschuss und 14 Sekunden Rahmen bei Elfmeterschießen.

**Why:** Der Nutzer präzisierte die ursprüngliche Ticketformel um den fehlenden Rahmen und verbietet eine nachträgliche Skalierung zum Schutz der Szenenlängen für die spätere 2D-Abnahme.

**How to apply:** Kein Umrechnen in der Brücke; Formel gegen die Gesamtdauer prüfen, nicht gegen jede einzelne Schussdauer. Das gelieferte Paket bytegleich übernehmen; ein ausdrücklich freigegebener Paketwechsel darf die zugehörigen Textreferenzen aktualisieren.

Normale Freundschaftsspiele haben unabhängige Freigaben; Turnierpartien gehören trotz Freundschaftsspiel-Simulationspfad zur Turnierrunde. Ein Rundentermin als Datum ist kein Echtzeit-Anstoß um Mitternacht.

**Why:** Der Nutzer verlangt ausdrücklich unabhängige Wettbewerbe und einen einmalig gespeicherten echten Lauf-/Anstoßzeitpunkt statt eines künstlichen Kalender-Anstoßes.

**How to apply:** Wettbewerbsidentität statt Datum oder technischen Matchtyp für die Sperre verwenden; unvollständige Runden nicht anhand der bereits vorhandenen Storys freigeben.