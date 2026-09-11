---
name: Turnier-Zustandsautomat testen
description: Welche Randpfade bei mehrstufigen Community-Turnieren zwingend separat geprüft werden müssen.
---

Mehrstufige Turniere erst abnehmen, wenn Tests nicht nur einzelne Runden, sondern den vollständigen Zustandsautomaten bis zum Abschluss durchlaufen. Zwingende Randpfade sind Hin-/Rückspiel-Finals, aggregierte Gleichstände, ausfallbedingte Einzel-Freilose, Einzel- und Doppel-Nichtantritt, Gruppen-H2H über alle direkten Duelle sowie formatabhängige Endplatzierungen und Prämien.

**Why:** Lokale Grünpfadtests ließen mehrfach Fehler bestehen, bei denen Turniere nach einem Hinspiel vorzeitig endeten, in einem Freilos-Zustand stecken blieben oder Top-3-Prämien nach Tabellenpunkten statt Ausscheidungsrunde vergaben.

**How to apply:** Bei Änderungen an Turnierfortschritt, Tabellen oder Prämien mindestens ein komplettes Liga-, Pokal- und Gruppen-K.-o.-Turnier mit den genannten Randpfaden bis zum persistierten Endstand testen.