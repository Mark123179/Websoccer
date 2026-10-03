# Spielvorschau: freigegebener visueller Aufbau

Der Nutzer hat diesen Aufbau ausdrücklich freigegeben:

- Gelieferte neutrale Kabine als Hintergrund, Referenzbild ausschließlich für die Anordnung.
- Drei dunkle, leicht transparente Kacheln in bestehenden Produktfarben, Breitenverhältnis etwa 1:2:1.
- Stuhl unten links und Tasche unten rechts bleiben unverändert im Originalbild. Die Kacheln werden an ihren Konturen maskiert und liegen dadurch dahinter; keine freigestellten Bildkopien.
- Wettbewerb als einzige neue sichtbare Information im Kopf der mittleren Kachel.
- Kachelinhalte bleiben leer, bis sie später separat definiert werden.
- Bestehende Navigation, Kalender, globale Artboard-Skalierung und andere Vereinsseiten bleiben unverändert.

## Umsetzung

Bestehende nächste-Spiel- und konkrete-Fixture-Routen nutzen ein eigenes Django-Template und ausschließlich seitenbezogene CSS-Regeln. Wettbewerb stammt aus dem Fixture, ohne Fixture aus der Vereinsliga. Ohne Liga wird nur die neutrale Überschrift „Wettbewerb“ gezeigt.

Hintergrund und Kartenmaske haben dieselbe Originalgröße und dieselbe Cover-Ausrichtung. So bleiben die Kacheln unabhängig von der Szenengröße hinter den Originalobjekten. Es gibt keine neue Simulation, kein JavaScript und keine Datenmutation.

## Prüfung

Gezielte Tests für Wettbewerbsauswahl, konkrete-Fixture-Route und leere Kacheln; Django-Systemcheck und visuelle Prüfung der öffentlichen Spielvorschau.