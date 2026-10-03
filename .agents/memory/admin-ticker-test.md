---
name: Admin-Ticker-Test
description: Nutzeranforderungen an echte Testsimulationen, Reset, Reload und Originaltempo.
---

Der Live-Ticker-Test ist nur für Admins und läuft im Originaltempo, nicht auf eine Minute reduziert. Reset soll eine neue Simulation derselben beiden Mannschaften erzeugen, nicht dieselbe Geschichte wiedergeben. Reload soll den laufenden Test fortsetzen.

**Why:** Der Nutzer: „will richtigen Test“ und „ich will ja nicht immer das selbe Spiel sehen, sondern die selben beiden Mannschaften, aber immer mit ‚neuer‘ Geschichte und Ausgang.“

**How to apply:** Einen neuen Testlauf mit der echten Engine und neuem Erzählen erzeugen, ohne normale Spiele oder historische Geschichten zu verändern. Nicht auf ein anderes Vereinspaar wechseln oder einen anderen Endstand erzwingen; gleiche Endstände können zufällig erneut auftreten. Navigation und API müssen gleichermaßen Adminzugriff verlangen.