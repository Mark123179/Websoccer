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

Die weitere Dortmund-Bildreferenz konkretisiert den Bildausschnitt: Stadion nahezu über die gesamte Breite, Spielfeld dicht am unteren Bildrand ohne große leere Vordergrundfläche, sichtbare Innenränge und Umgebung als Hintergrund. Eine etwas tiefere Kamera ist ein gewünschter Versuch, keine bereits festgelegte Kamerahöhe.

**Why:** Der Nutzer: „So wäre zumindest die Proportion, unterer Rand usw. vllt. die Kamera noch tiefer“.

**How to apply:** Den Ausschnitt an dieser Referenz ausrichten, statt das vollständige Stadion samt großem Vorplatz ins Bild einzupassen. Die Kameraabsenkung gegen die Sichtbarkeit des Spielfelds abwägen; diesen Framing-Schritt nicht mit einer bereits erreichten Materialqualität gleichsetzen.

Die Kamerahöhe soll vom Nutzer einstellbar bleiben; der hintere Spielfeldbereich braucht mehr sichtbare Fläche.

**Why:** Der Nutzer: „hinten brauchen wir mehr Feld, gibt mir eine Option die Kamera einzustellen von der Höhe her.“

**How to apply:** Eine Höhenvorgabe nicht als endgültig freigegeben behandeln. Bei weiteren Darstellungsänderungen die direkte Kameraeinstellung erhalten und die Sicht auf das hintere Spielfeld mitprüfen.

Die Kamera der Test-Spielansicht soll perspektivisch sein, nicht orthografisch. Der Monitorfoto-Blick ist eine visuelle Referenz, keine Quelle für einen exakt bekannten Kamerawinkel.

**Why:** Nach dem Vergleich der Neigungen gefiel dem Nutzer weiterhin die ursprüngliche Spielansicht; auf die Frage nach der Umstellung antwortete er „Ja, perspektivische Kamera verwenden“. Nach der Umstellung bestätigte er „besser“.

**How to apply:** Bei weiteren Kameraanpassungen die perspektivische Tiefenwirkung erhalten. Einen aus dem schräg fotografierten Monitor geschätzten Winkel nicht als gemessenen oder final freigegebenen Wert behandeln.

Die perspektivische Ansicht mit optionalem Dach ist positiv bestätigt. Für das Live-Ticker-Umfeld möchte der Nutzer oben mehr sichtbare Umgebung und eine natürliche Darstellungsqualität wie in der Spielansichts-Referenz, auf OSM-Grundlage.

**Why:** Nach der Dachoption sagte der Nutzer „sehr stark“ und fragte nach mehr Umgebung oben sowie „gemessen an OSM aber in der qualität wie im Screenshot“.

**How to apply:** Perspektive und Dachwahl bei der Umfelddarstellung erhalten. Die natürliche Referenz gilt für den Live-Ticker-Test; sie hebt die getrennte Neon-Vorgabe des produktiven Stadioneditors nicht auf. Kartendaten von grafisch angenäherten Formen und Materialien unterscheiden.

Die Umfelddarstellung muss auf andere Stadien übertragbar sein und deren jeweils reale Umgebung berücksichtigen. Ein einmaliger Vorbereitungsschritt je Stadion ist akzeptabel.

**Why:** Der Nutzer: „Das muss immer multiplizierbar sein, jedes Stadion hat ja in RL eine andere Umgebung. Zur Not eine Variante, die wir für jedes Stadion einmal machen müssen.“

**How to apply:** Dortmund nicht als einmalige fest verdrahtete Kulisse bauen. Gemeinsame Darstellung und wiederverwendbare Assets von den geografischen Daten und der Modell-Kalibrierung pro Stadion trennen; individuelle Nachpflege ermöglichen.