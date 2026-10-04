# Spielvorschau: freigegebene vollständige Übersicht

Der Nutzer hat diesen Aufbau ausdrücklich freigegeben:

- Gelieferte neutrale Kabine als Hintergrund, Referenzbild ausschließlich für die Anordnung.
- Drei dunkle, leicht transparente Kacheln in bestehenden Produktfarben, Breitenverhältnis etwa 1:2:1.
- Stuhl unten links und Tasche unten rechts bleiben unverändert im Originalbild. Die Kacheln werden an ihren Konturen maskiert und liegen dadurch dahinter; keine freigestellten Bildkopien.
- Der Kabinenhintergrund reicht über die gesamte Inhaltsfläche einschließlich
  des Bereichs hinter dem Kalender. Die Kacheln werden innerhalb der vorhandenen Seite größer.
- Links: letzte Gegneraufstellung mit Spielerporträts auf dem Spielfeld,
  Trainerporträt, Form, letztes Ergebnis mit Wappen, Verletzte und Gesperrte.
- Mitte: Wettbewerb, Spieltag, beide Vereinsnamen und Wappen, tatsächlich
  verwendete Heim-/Auswärtstrikots, Ort, Datum, Uhrzeit, Stadionname, Wetter
  und Referee; darunter Umschaltung zwischen Stadionfoto und 3D-Modell.
- Rechts: Top-Torjäger, Notenbester, bester Spieler des letzten Gegnerspiels
  mit Note und wertvollster Spieler, jeweils mit Bild; letzte Vereinsnews.
- Bestehende Navigation, Kalender, globale Artboard-Skalierung und andere Vereinsseiten bleiben unverändert.

## Umsetzung

Bestehende nächste-Spiel- und konkrete-Fixture-Routen nutzen ein eigenes Django-Template und ausschließlich seitenbezogene CSS-Regeln. Wettbewerb stammt aus dem Fixture, ohne Fixture aus der Vereinsliga. Ohne Liga wird nur die neutrale Überschrift „Wettbewerb“ gezeigt.

Hintergrund und SAM-Kartenmaske haben dieselbe Originalgröße und dieselbe
Cover-Ausrichtung auf der gesamten Inhaltsfläche. Es gibt keine Simulation,
historische Backfills oder Datenmutation beim Öffnen.
Isoliertes JS unterstützt das verzögerte Laden der sichtbaren 3D-Ansicht und
ehrliche Bild-Ausfallzustände; Django escaped alle Texte.

Die Aufstellung stammt aus dem letzten kanonischen Gegner-Spielbericht,
nicht aus der aktuellen Taktik. Noten werden auf der deutschen Skala
ausgewertet (1 besser als 6); Saisonstatistiken sind an aktuellen Spielverein
und numerische Spielsaison gebunden. Stadion und Ort gehören immer zum
Heimverein, der Gegner wird relativ zum aufgerufenen Verein bestimmt.
Vereinsnews beziehen sich auf den aufgerufenen Verein.

Auf ausdrücklichen Nutzerwunsch werden fehlende Trainer-, Wetter- und
Schiedsrichterdaten vorübergehend durch gekennzeichnete Testdaten ergänzt.
Diese bleiben reine Anzeigedaten, ohne Speicherung oder Simulationseinfluss.
Vorhandene echte Daten haben Vorrang. Stadionfoto und 3D stehen nebeneinander;
für andere Spielorte ist Dortmunds Modell ausdrücklich als Testmodell
beschriftet, nicht als Modell des tatsächlichen Heimstadions.
Vorhandenes Tageswetter wird gelesen, nicht beim Seitenaufruf gewürfelt.
Das Gegner-Spielfeld wird etwas länger und verwendet das Spielfeldbild
der bestehenden Taktikansicht anstelle synthetischer CSS-Markierungen.

## Prüfung

## Aktualisierte Referenzrichtung

Die jüngste freigegebene Vorlage verlangt kompaktere Teilbereiche und eine
stärkere Wappen-/Trikot-/Porträt-Hierarchie. Die Kabine samt SAM-Projektion
bleibt unverändert. Das 3D-Stadion steht neben „Form & Stats“; dort werden
beide Vereine mit ihrer Form und echten Werten des jeweils letzten
Spielberichts gezeigt (keine erfundenen Saisonmittelwerte). An der Position
des Trainerzitats steht das Schiedsrichterprofil mit passendem Porträt.
Kein Trainerzitat und kein „Spiel starten“-Button.

## Persönlicher Layoutmodus

Direkt in der Spielvorschau können Gruppen und einzelne Gestaltungselemente
ausgewählt, gezogen und über acht Griffe oder Zahlenfelder skaliert werden.
Die Position wird unabhängig von der Game-Stage-Skalierung berechnet.
Textgröße, Sichtbarkeit und Ebenenreihenfolge sind ebenfalls bearbeitbar.
Hierarchische Gruppen bleiben zusammen; Daten und Links werden nicht geklont.

Speichern übernimmt die Darstellung browserlokal, getrennt nach Nutzer.
Abbrechen stellt den zuletzt gespeicherten Zustand wieder her.
Standardlayout ist zunächst ein Entwurf und wird erst durch Speichern
übernommen. Im Editiermodus wird die Objektmaske vorübergehend deaktiviert,
damit verdeckte Elemente erreichbar bleiben; in der normalen Ansicht bleibt
die freigegebene Maskierung erhalten. Keine Schreibzugriffe auf Spieldaten.

Gezielte Tests für Wettbewerb und Fixture-Route, Rollenwechsel,
Snapshot-Aufstellung, Notensortierung, Saisonbindung, Ausfälle, leere
und teilweise befüllte Zustände. Originalfoto und SAM-Maske unverändert
vergleichen; Seite und Assets im laufenden Workflow prüfen.