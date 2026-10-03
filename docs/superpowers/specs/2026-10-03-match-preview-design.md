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
Isoliertes JS unterstützt Foto/3D-Umschaltung, verzögertes Laden und
ehrliche Bild-Ausfallzustände; Django escaped alle Texte.

Die Aufstellung stammt aus dem letzten kanonischen Gegner-Spielbericht,
nicht aus der aktuellen Taktik. Noten werden auf der deutschen Skala
ausgewertet (1 besser als 6); Saisonstatistiken sind an aktuellen Spielverein
und numerische Spielsaison gebunden. Stadion und Ort gehören immer zum
Heimverein, der Gegner wird relativ zum aufgerufenen Verein bestimmt.
Vereinsnews beziehen sich auf den aufgerufenen Verein.

Fehlende Daten werden nicht erfunden: ein zukünftiger Referee ist im
vorhandenen Modell noch nicht angesetzt, sondern erst am simulierten Spiel
gespeichert. Das vorhandene Live-3D-Modell ist Dortmund-spezifisch und darf
nicht für andere Stadien ausgegeben werden. Vorhandenes Tageswetter wird
gelesen, nicht beim Seitenaufruf gewürfelt.

## Prüfung

Gezielte Tests für Wettbewerb und Fixture-Route, Rollenwechsel,
Snapshot-Aufstellung, Notensortierung, Saisonbindung, Ausfälle, leere
und teilweise befüllte Zustände. Originalfoto und SAM-Maske unverändert
vergleichen; Seite und Assets im laufenden Workflow prüfen.