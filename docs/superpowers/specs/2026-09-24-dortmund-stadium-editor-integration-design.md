# Dortmunder Stadioneditor: produktive Integration

## Ziel und Geltungsbereich

Der freigegebene Rundum-Prototyp wird für Borussia Dortmund in den bestehenden Django-Stadioneditor integriert. Nur Dortmund wechselt zunächst zur neuen Oberfläche. Die Stadien, Geometrien, Designs, Ausbauaufträge und Finanzhistorie der anderen Vereine bleiben erhalten; auch Dortmunder Bestandsdaten werden nicht gelöscht.

## UI und Architektur

Die bestehende authentifizierte Editorroute bleibt der Einstieg. Für Dortmund nutzt sie eine neue, responsive Oberfläche im visuellen Stil des Rundum-Prototyps; für andere Vereine bleibt die bisherige Oberfläche. Der 2D-Grundriss verwendet die vom Server gelieferten tatsächlichen Stadionblöcke, keine schematischen Rechtecke als speicherbare Geometrie. Auswahl, Gestaltung, Farb-/Bild-/Textwerkzeuge, Rückgängig/Wiederholen und Speichern behalten ihre bestehende Bedeutung und ihre vorhandenen Datenformate.

Die bestehende änderungstreue 3D-Ansicht ist die verbindliche Prüfung für Änderungen am Entwurf, auch bevor er gespeichert wird. Sie bietet Drehen/Neigen, Dach ein/aus und Innen-/Sitzansicht. Das detaillierte Dortmunder Originalmodell wird als getrennte, klar bezeichnete Konzeptansicht gezeigt, solange es Entwurfsänderungen nicht selbst visualisiert; es darf nicht als aktualisierte Vorschau ausgegeben werden. Schlägt WebGL fehl, muss eine verständliche Meldung oder ein statisches Ersatzbild erscheinen.

## Vorschau, Speicherung und echter Ausbau

Nur Staff/Admin sieht und betätigt die Simulationssteuerung für eine ausgewählte Tribüne. Sie bietet Schritte von 1.000, 5.000, 10.000 und 20.000 Plätzen und verwendet die bestehende clientseitige Vorschauberechnung mit deren Sicherheitsgrenze. Sie erzeugt ausschließlich simulierte Entwurfsblöcke; weder Geld noch echte Kapazität oder Ausbauaufträge werden dabei verändert. Der Save-Button verwendet weiterhin den authentifizierten, CSRF-geschützten Design-Speicherendpunkt und zeigt Erfolg oder Fehler explizit an. Serverseitige Geometrieprüfung und Sanitizing bleiben verbindlich.

Der tatsächliche Ausbau wird ausschließlich über die existierende Stadionverwaltung bestellt. Ein eindeutiger Link führt vom Editor dorthin und zurück. Beauftragte, noch nicht abgeschlossene Ausbauten werden als ausstehend, nicht als bestehende Plätze, angezeigt. Nach Fertigstellung übernimmt die vorhandene Ausbau-/Geometrie-Pipeline die neue Kapazität; nach erneutem Laden des Editors ist der abgeschlossene Stand sichtbar. Vorschaublöcke und realer Ausbau werden beschriftet und rechnerisch getrennt.

## Zugriff und Fehlerbehandlung

Manager können nur den Entwurf ihres eigenen Vereins laden und speichern. Nicht-Admins erhalten keine Simulationssteuerung; keine neue Änderungsroute öffnet die Simulation ohne entsprechende Berechtigung. Fehlende Geometrie bleibt ein expliziter Nicht-verfügbar-Zustand. Laden/Speichern zeigt Netzwerk-, Validierungs- und Berechtigungsfehler an, statt lokal einen falschen Erfolg zu melden. Die vorhandenen Produktionsdaten werden weder migriert noch gelöscht.

## Abnahme

Prüfen: Dortmund lädt Bestandsentwurf; 2D-Auswahl und Bearbeitungswerkzeuge funktionieren; Speichern und Neuladen erhalten Änderungen; Vorschau verändert weder `Stadium`-Kapazität noch Budget oder `StadiumExpansion`; Nicht-Admin sieht keine Simulationssteuerung; echte Ausbauaufträge bleiben nur im Stadion-Menü; ausstehende und abgeschlossene Aufträge sind korrekt unterscheidbar; die änderungstreue 3D-Ansicht zeigt Entwurfsänderungen und ihre Kamera-/Dachfunktionen; andere Vereine behalten ihren bisherigen Editor und ihre Daten.