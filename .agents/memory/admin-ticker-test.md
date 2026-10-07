---
name: Admin-Ticker-Test
description: Nutzeranforderungen an echte Testsimulationen, Reset, Reload und Originaltempo.
---

Der Live-Ticker-Test ist nur für Admins und läuft im Originaltempo, nicht auf eine Minute reduziert. Reset soll eine neue Simulation derselben beiden Mannschaften erzeugen, nicht dieselbe Geschichte wiedergeben. Reload soll den laufenden Test fortsetzen.

**Why:** Der Nutzer: „will richtigen Test“ und „ich will ja nicht immer das selbe Spiel sehen, sondern die selben beiden Mannschaften, aber immer mit ‚neuer‘ Geschichte und Ausgang.“

**How to apply:** Einen neuen Testlauf mit der echten Engine und neuem Erzählen erzeugen, ohne normale Spiele oder historische Geschichten zu verändern. Nicht auf ein anderes Vereinspaar wechseln oder einen anderen Endstand erzwingen; gleiche Endstände können zufällig erneut auftreten. Navigation und API müssen gleichermaßen Adminzugriff verlangen.

Die gewünschte Stadionansicht kombiniert ein waagerechtes Spielfeld mit Umgebung wie in der gelieferten Spielansicht und drei sichtbare Seiten des Signal-Iduna-Modells. Die kameranahe vierte Seite soll den Blick nicht verdecken.

**Why:** Der Nutzer ordnete Umgebung/Spielfeld seiner zweiten Bildreferenz und die drei Stadionseiten seiner ersten Bildreferenz zu und bat um einen ersten Entwurf im Live-Ticker-Testbereich.

**How to apply:** Kamerastudien zuerst dort zeigen, das vollständige Modell erhalten und eine spätere Übernahme in normale Spiele separat abstimmen. Eine erste statische Ansicht nicht als echte Spieler-/Ballanimation ausgeben.