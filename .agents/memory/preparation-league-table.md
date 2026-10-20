---
name: Ligatabelle vor Saisonstart
description: Vereinsimport berechtigt nicht zur Initialisierung oder zum Start einer Saison.
---

Die Anzeige importierter Ligavereine in der Vorbereitung soll keinen
Saisonstart, Spielplan oder persistierte Tabellenzeilen auslösen.

**Why:** Nach dem Vereinsneuimport waren alle 18 Vereine vorhanden, während
die noch nicht initialisierte Tabelle leer blieb. Die reine Anzeige muss
funktionieren, ohne den Saisonbetrieb vorwegzunehmen.

**How to apply:** Vor dem ersten Saisonstart eine rein lesende Nulltabelle
aus der aktuellen Ligazugehörigkeit anzeigen. Echte Tabellenwerte haben
Vorrang; fehlende Daten nach Saisonstart nicht als Nulltabelle verschleiern.
