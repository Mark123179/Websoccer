---
name: Zweite Bundesliga beim weiteren Vereinsimport
description: Freigegebene Ligazuordnung und anfänglicher Spielbarkeitsstatus der weiteren Vereinspakete.
---

Die zusätzliche 2. Bundesliga zunächst als nicht spielbare Liga anlegen;
die bestehende 1. Bundesliga mit ihren 18 Vereinen nicht erweitern.

**Why:** Der Nutzer hat diese Zuordnung für die weiteren Vereinspakete
ausdrücklich gewählt. Die zusätzlichen Pakete ergeben noch keine vollständige
zweite Liga.

**How to apply:** Weitere Imports nicht mit einer Freigabe des Ligaspielbetriebs
gleichsetzen. Die Freigabe dieser Importe gilt für den Workspace, nicht für
einen Produktionsimport.

Ein Spieler darf in zwei Vereinspaketen derselben Lieferung vorkommen,
wenn eines die Verleiher- und das andere die Entleiherperspektive derselben
Leihe beschreibt. Das rechtfertigt weder eine zweite Spieleridentität noch
das Entfernen einer Quellzeile.

**Why:** Die Kieler und Osnabrücker Pakete enthielten dieselbe, widerspruchsfreie
Leihe in beiden Perspektiven; die pauschale Dublettenprüfung des Sammelhelfers
behandelte die gültige Lieferung dennoch als Konflikt.

**How to apply:** Kanonische Spieler-IDs, Eigentümer, Leihverein und Leihende
über beide Pakete vergleichen. Am Ende muss genau ein Spieler mit korrektem
Stamm- und Einsatzverein bestehen; Paketquellen und Rückennummer des
aufnehmenden Vereins erhalten.
