---
name: Spielvorschau visual contract
description: User-approved scope and reference-image boundaries for the empty match preview.
---

Die Spielvorschau übernimmt aus dem Referenz-Screenshot ausschließlich den Aufbau: drei Kacheln, die mittlere breiter; Stuhl links unten und Tasche rechts unten liegen vor den Kacheln. Der separat gelieferte neutrale Kabinenhintergrund bleibt die tatsächliche Bildquelle. Bestehende Produktfarben bleiben erhalten, Kacheln leicht transparent.

**Why:** Der Nutzer hat ausdrücklich nur die Art und Weise der Referenz bestellt, nicht deren Mannschaften, Texte, Farben oder Inhalte.

**How to apply:** Wettbewerb oben im Header, sonst Kacheln leer lassen. Inhalte werden später separat definiert; keine Aufstellungen, Hinweise oder Beispielwerte vorwegnehmen.

Stuhl und Tasche im Originalbild unangetastet lassen; nur die darüberliegenden Kacheln an den Objektkonturen maskieren.

**Why:** Der Nutzer beanstandete die sichtbaren Freistellungskanten ausdrücklich: „Die Kacheln sollten einfach nur dahinter“.

**How to apply:** Keine ausgeschnittenen RGB-Kopien der Bildobjekte darüberlegen. Die Kartenmaske und das Originalfoto müssen dieselbe Bildprojektion verwenden, einschließlich Cover-Skalierung und Zentrierung.

Generativ erzeugte Schwarz-Weiß-Bilder nicht als pixelgenaue Objektsegmentierung behandeln.

**Why:** Die KI-Bildbearbeitung lieferte trotz ausdrücklicher Vorgabe ein quadratisches Bild mit veränderten Objektkonturen. Zurückskalieren auf die Originalgröße ließ störende Bodenflächen um die Objekte frei.

**How to apply:** Jede externe Maske gegen die Originalkonturen in vergrößerten Ausschnitten prüfen. Identische Bildabmessungen allein beweisen keine geometrische Übereinstimmung; für exakte Konturen ein Segmentierungsverfahren bevorzugen.

Segmentierung ist ein einmaliger Asset-Aufbereitungsschritt, keine neue App-Laufzeitfunktion.

**Why:** MobileSAM ließ sich mit dem bereits verfügbaren ONNX Runtime lokal auf der CPU betreiben, ohne PyTorch, neue Verbindung oder Änderungen an den App-Abhängigkeiten. Der Nutzer hat die SAM-Konturen nach der Detailvorschau ausdrücklich zum Einbau freigegeben. Eine fertige statische Maske genügt für die Darstellung.

**How to apply:** Modellgewichte und Experimente außerhalb der App halten. Nur die geprüfte Bildmaske integrieren; das Spiel soll keine Modelle laden oder Konturen bei Seitenaufrufen berechnen.