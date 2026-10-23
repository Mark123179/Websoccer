---
name: Strikt schreibfreie HTTP-Vorschauen
description: Warum ein lesender GET-View allein keine schreibfreie Vorschau garantiert.
---

Eine Vorschau ohne Speichern muss über den vollständigen HTTP-Aufruf
geprüft werden, nicht nur durch direkten Aufruf ihrer View-Funktion.

**Why:** Beim Rasen-Pilot erzeugten globale Aufrufeffekte trotz rein
lesender View zunächst Aktivitätsbelohnungen und anschließend Wetterdaten.
Eine Anmeldung ohne Login-Signale allein verhindert solche Effekte nicht.

**How to apply:** Vorher-/Nachher-Vergleiche der betroffenen Spiel- und
Stadiondaten um einen authentifizierten HTTP-Aufruf legen. Globale
Request-Helfer und Template-Kontext als mögliche Schreiber berücksichtigen.
Nötige Ausnahmen eng auf die isolierte Vorschau begrenzen; weder
Authentifizierung lockern noch die Datenprüfung abschwächen oder das
normale Spielverhalten pauschal ändern.
