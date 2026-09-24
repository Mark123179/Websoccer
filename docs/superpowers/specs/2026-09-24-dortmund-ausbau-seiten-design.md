# Dortmunder Ausbau: Seiten und Anschlüsse

## Ziel und Grenze

Die beanstandete Dortmunder Ausbauansicht soll räumlich nachvollziehbar werden:
Nord/Süd/Ost/West in Auswahl und 3D bezeichnen dieselben Stadionseiten, und neue
Ränge, Wände, Ecken und Dachübergänge schließen plausibel an den sichtbaren Bestand
an. Die Aufnahme `attached_assets/image_1790265460242.png` ist die Perspektivvorlage.
Unity-Export und Originalmeshes bleiben unverändert. Die rekonstruierte
Bestandsfassade bleibt als Rekonstruktion erkennbar; der Rundum-Entwurf wird nicht
in eine neue Bestandsbehauptung umgedeutet. Wirtschaftliche Kapazität und
Ausbauaufträge werden nicht geändert.

## Entwurfsentscheidung

Die Lösung kalibriert zuerst das Modellkoordinatensystem anhand des vorhandenen
georeferenzierten OSM-Stadionumrisses und überprüfbarer Ortsmerkmale. Insbesondere
werden die längere Modellachse, erkennbare Tribünen und die Lage der umliegenden
Straßen gegenüber der Karten-Nordrichtung geprüft. Die bisherige Gleichsetzung
`+X = Süd` gilt bis dahin nicht als Beleg. Die so belegte Zuordnung wird zentral
festgehalten und von 2D-Auswahl, Beschriftung und produktiver 3D-Szene genutzt;
die Vergleichsszene zeigt dieselbe Orientierung. Wenn die Quellen nur die
Modellseite, aber nicht die absolute geographische Richtung tragen, benennt die
Oberfläche diese Unsicherheit ausdrücklich statt eine Himmelsrichtung zu erfinden.
Kameradrehung darf die Seitenzuordnung nicht ändern.

Nur neu gezeichnete bzw. zur Laufzeit abgeleitete Ausbauflächen werden verändert.
Die Ausbaugeometrie erhält an ihren Anfangs- und Endpunkten geschlossene
Übergänge zu den vorhandenen Rängen und Dachkanten; gemeinsame Eckpunkte werden
für angrenzende neue Flächen wiederverwendet. Die bisherige flächige Verschiebung
von Dachteilen wird gegen die tatsächlich sichtbaren Anschlusskanten abgeglichen.
Editor und Vergleichsvorschau verwenden dieselben Maße/Seitendefinitionen oder
werden durch Geometrie-Vertragstests auf Gleichheit geprüft. Die Süd- und
Rundum-Vergleichsvarianten bleiben eigenständige Konzepte.

## Gespeicherte Daten

Der Nutzer hat das Verwerfen bestehender Entwürfe bestätigt. Es wird **nur**
der gespeicherte `StadiumDesign`-Datensatz des Dortmunder Stadions
(Verein-ID 3) zurückgesetzt bzw. entfernt. Damit gehen auch dort gespeicherte
Sitzfarben, Palette und Blickrichtung verloren; keine Migration alter
Seitenbezeichnungen findet statt. Stadion-Designs anderer Vereine,
`StadiumGeometry`, `StadiumExpansion`, Kapazität und Finanzdaten bleiben
unverändert. Ohne vorhandenen Dortmunder Datensatz ist der Reset ein No-op.

## Abnahme

- Die Ansicht aus der Anlage wird mit gleichem Blickwinkel vorher/nachher
  verglichen; weitere Aufnahmen zeigen Außenansicht, Draufsicht, Dach an/aus
  und beide Eckanschlüsse. Unbelegte Stellen werden nicht als nahtlos bezeichnet.
- Tests prüfen die Achsen-/Seitenzuordnung samt 2D- und 3D-Verwendung,
  Eckpunkt- und Dachanschlüsse, unveränderte Originalgeometrie und die
  Begrenzung des Resets auf Dortmund.
- Im Browser werden Auswahl, Vorschau, Speichern und Wiederladen,
  Kamerawechsel sowie der getrennte Rundum-Entwurf geprüft. Ein Reset darf
  keine Ausbauaufträge und keine Kapazität ändern.