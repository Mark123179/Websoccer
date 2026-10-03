# Stadionmodell in der Vereinsübersicht

## Freigegebene Darstellung

Die bisherige Partnerverein-Kachel wird durch „3D-Stadion“ ersetzt.
Der Nutzer präzisiert: „dreht sich von alleine, kann man selbst nicht drehen.“
Nur das bestehende Stadionmodell ist sichtbar; keine Umgebung, keine Bäume,
keine Ausbauvorschau und keine Bedienleiste. Größe und Position der Kachel
sowie alle übrigen Karten bleiben unverändert. Der Nutzer hat zusätzlich einen
transparenten Modellhintergrund gewünscht: kein schwarzes Canvas-Rechteck.
Nach Präzisierung bleibt der alte Kachelhintergrund erhalten; das transparente
Modell liegt darüber und wird etwas größer dargestellt.

## Umsetzung

- Den vorhandenen Dortmunder Renderer wiederverwenden: optionale automatische
  Rotation, deaktivierte Maus-/Touchsteuerung, kein Umfeld und passende Kamera
  für die kleine Kachel. Editor-Standardeinstellungen bleiben erhalten.
- Das Modell erst laden, wenn die Kachel sichtbar ist. Animation bei
  ausgeblendeter Kachel oder verborgenem Tab pausieren; Ressourcen beim
  Verlassen freigeben. Reduzierte Bewegung respektieren.
- Nur für Dortmund ist dieses Originalmodell vorhanden. Andere Vereine
  erhalten einen ehrlichen Hinweis statt eines fremden Stadionmodells.
- Lade- und WebGL-Fehler verständlich in der Kachel anzeigen.
- Keine Datenbankänderungen, finanziellen Buchungen oder neuen Abhängigkeiten.

## Prüfung

Template-Prüfungen für Dortmund und einen anderen Verein; JavaScript-Prüfungen
für konfigurierte Rotation, ausgeschaltete Bedienung und Umfeldfreiheit.
Bestehende Renderer-Prüfungen sowie Sichtprüfung der realen Vereinsübersicht.