---
name: Freundschaftsspiel-Sandkasten
description: Nicht offensichtliche Integritätsregeln für Freundschaftsspiele, ihre Simulation und Saisonbereinigung.
---

Freundschaftsspiele sind ein isolierter Simulationspfad: Sie verwenden den getrennten Taktikkontext `freundschaft`, dürfen keine Frische-, Verletzungs-, Karten-, Form-, Saisonstatistik- oder Finanzpersistenz auslösen und erscheinen nicht im globalen Kalender. Bei neutralem Spielort müssen sämtliche Heimboni auch in der Verlängerung deaktiviert sein.

**Why:** Die normale Match-Engine enthält mehrere voneinander unabhängige Heimmodifikatoren. Ein neutraler Berichtsschlüssel allein macht die Simulation nicht neutral. Außerdem können parallele Annahmen und abgestürzte Tick-Worker sonst Doppelbelegungen oder dauerhaft laufende Partien erzeugen.

**How to apply:** Zusagen reservieren beide Clubzeilen in stabiler Reihenfolge und prüfen ein dreistündiges Spielzeitfenster; Pflichtspiele ohne Uhrzeit und Pokalrunden reservieren den ganzen Tag. Tick-Claims brauchen Zeitstempel plus Token, damit veraltete Worker nicht finalisieren. Tick-Fehler werden pro Partie isoliert; drei Versuche laufen mit Backoff, danach endet die Partie kontrolliert als nicht gespielt. Ein Saisonwechsel muss alte Vorgänge und Berichte atomar und fail-closed löschen.