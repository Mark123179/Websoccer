---
name: Spielvorschau visual contract
description: Required match-preview content, full-page locker-room background and approved object masking.
---

Die Spielvorschau übernimmt aus dem Referenz-Screenshot ausschließlich den Aufbau: drei Kacheln, die mittlere breiter; Stuhl links unten und Tasche rechts unten liegen vor den Kacheln. Der separat gelieferte neutrale Kabinenhintergrund bleibt die tatsächliche Bildquelle. Bestehende Produktfarben bleiben erhalten, Kacheln leicht transparent.

**Why:** Der Nutzer hat ausdrücklich nur die Art und Weise der Referenz bestellt, nicht deren Mannschaften, Texte, Farben oder Inhalte.

**How to apply:** Der Nutzer hat die Inhalte inzwischen vorgegeben und lässt die Gestaltung frei. Die frühere Beschränkung auf leere Kacheln gilt nicht mehr.

Die Spielvorschau soll folgende Inhalte zeigen:

- Wettbewerb, Spieltag, Verein X gegen Verein Y, Ort, Datum, Uhrzeit, Stadionname, Wetter und Schiedsrichter.
- Letzte Aufstellung des Gegners auf einem Spielfeld mit Spielerbildern, Trainer mit Profilbild, letztes Gegnerergebnis samt Wappen, Form sowie verletzte und gesperrte Gegner inklusive Namen.
- Letzte Vereinsnews; Top-Torjäger, Notenbester, bester Spieler des letzten Spiels mit Note und wertvollster Spieler, jeweils mit Spielerbild.
- Stadionfoto, 3D-Stadionmodell und die beiden Heim-/Auswärtstrikots, die die Teams tatsächlich in dieser Begegnung verwenden.

**Why:** Der Nutzer gibt die Informationsanforderungen vor, lässt die Gestaltung frei und verlangt ausdrücklich die Qualität eines AAA-Managers.

**How to apply:** Alle genannten Inhalte berücksichtigen; fehlende Daten nicht durch erfundene Spieler, Ergebnisse oder Bewertungen ersetzen.

Der Kabinenhintergrund muss über die ganze Seite reichen, auch hinter den Kalender. Anschließend dürfen die drei Kacheln größer werden.

**Why:** Der Nutzer beanstandet den sichtbaren Beginn des Kabinenfotos unter dem Kalender und verlangt diese Anpassung vor der weiteren Gestaltung.

**How to apply:** Hintergrund und Objektmaske bei der Vergrößerung weiterhin identisch projizieren. Die Kalenderfunktion darf durch die Hintergrunddarstellung nicht verändert werden.

Stuhl und Tasche im Originalbild unangetastet lassen; nur die darüberliegenden Kacheln an den Objektkonturen maskieren.

**Why:** Der Nutzer beanstandete die sichtbaren Freistellungskanten ausdrücklich: „Die Kacheln sollten einfach nur dahinter“.

**How to apply:** Keine ausgeschnittenen RGB-Kopien der Bildobjekte darüberlegen. Die Kartenmaske und das Originalfoto müssen dieselbe Bildprojektion verwenden, einschließlich Cover-Skalierung und Zentrierung.

Generativ erzeugte Schwarz-Weiß-Bilder nicht als pixelgenaue Objektsegmentierung behandeln.

**Why:** Die KI-Bildbearbeitung lieferte trotz ausdrücklicher Vorgabe ein quadratisches Bild mit veränderten Objektkonturen. Zurückskalieren auf die Originalgröße ließ störende Bodenflächen um die Objekte frei.

**How to apply:** Jede externe Maske gegen die Originalkonturen in vergrößerten Ausschnitten prüfen. Identische Bildabmessungen allein beweisen keine geometrische Übereinstimmung; für exakte Konturen ein Segmentierungsverfahren bevorzugen.

Segmentierung ist ein einmaliger Asset-Aufbereitungsschritt, keine neue App-Laufzeitfunktion.

**Why:** MobileSAM ließ sich mit dem bereits verfügbaren ONNX Runtime lokal auf der CPU betreiben, ohne PyTorch, neue Verbindung oder Änderungen an den App-Abhängigkeiten. Der Nutzer hat die SAM-Konturen nach der Detailvorschau ausdrücklich zum Einbau freigegeben. Eine fertige statische Maske genügt für die Darstellung.

**How to apply:** Modellgewichte und Experimente außerhalb der App halten. Nur die geprüfte Bildmaske integrieren; das Spiel soll keine Modelle laden oder Konturen bei Seitenaufrufen berechnen.