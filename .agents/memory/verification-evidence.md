---
name: Verification evidence boundaries
description: User-required controls for parity, regression, baseline tests and diagnostic counts.
---

Verifikationsbehauptungen müssen die tatsächlich identischen Startbedingungen nennen: Seed-Satz, Saisonanzahl, sämtliche verwendeten Zufallszustände und bei Tests den Zustand der Testdatenbank.

**Why:** Der Nutzer korrigierte eine Abnahme, die unterschiedliche Saisonumfänge als Vorher/Nachher-Beleg verwendete, lokale Seeds mit vollständig kontrolliertem Zufall gleichsetzte und Testfehler ohne Baseline-Lauf als vorbestehend bezeichnete.

**How to apply:** Verteilungsvergleiche nicht als Parität verkaufen. Vorbestehende Testfehler nur nach einem tatsächlichen Baseline-Lauf unter passenden Bedingungen behaupten; frische und wiederverwendete Testdatenbanken getrennt ausweisen. Fachliche Gleichheit von Laufzeitabweichungen trennen.

Diagnosen nach betroffenen Spielen und Zahlentypen aufschlüsseln; mehrere Prüfer können denselben Fehler mehrfach melden. Dateninkonsistenz und Erzählerfehler nur über eine unabhängige Quellenprüfung unterscheiden.

**Why:** Der Nutzer wies darauf hin, dass Meldungszahlen kein Maß für betroffene Spiele sind und eine pauschale Einordnung als harmlose Altdaten ohne Gegenprüfung nicht belegt ist.

**How to apply:** Erwartet/erzählt mit konkreten Fällen zeigen, fehlende Felder von vorhandenen Nullwerten unterscheiden und konsistente Eingaben direkt gegen die unveränderte Erzähler-Baseline prüfen. Eine Ausnahme für inkonsistente Eingaben entschuldigt keine Fehler bei konsistenten Eingaben.