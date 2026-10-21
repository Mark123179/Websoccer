---
name: Sitzquellen und Fangruppen
description: Unterschiedliche Gruppenaufteilung in Sitz-JSON und Unity-Modell darf nicht als amtliche Blocktopologie gelten.
---

Sitz-JSON und Unity-Crowd können trotz passendem Stadion und passender räumlicher
Drehung unterschiedliche Fangruppennamen und Abschnittsgrenzen enthalten.
Bei solchen Abweichungen ist die Originalmodell-Geometrie maßgeblich für
abgeleitete Editor-Hüllen; die JSON-Gruppen nicht als offizielle Blöcke ausgeben.

**Why:** Beim HSV passten mehrere gleichnamige Gruppen nur teilweise zusammen,
während einzelne Gästegruppen nur in einer der beiden Quellen existierten.
Eine strikte Namensgleichheit hätte entweder die Quelle fälschlich abgelehnt
oder zu unbelegten Blockzuordnungen geführt.

**How to apply:** Drehung und Geometriebezug getrennt von der semantischen
Gruppenzuordnung prüfen. Nicht zuordenbare Gruppen offen dokumentieren,
Kamerapositionen zusätzlich räumlich absichern und wirtschaftliche Kapazität
weiterhin ausschließlich aus dem bestehenden Stadion übernehmen.

Originale Sitztexturen sind nicht automatisch eine korrekte Vereinsdarstellung.
Bei erkennbar handgezeichneten oder verzerrten Wappen und Schriftzügen die
Darstellung gegen ein reales Tribünenfoto und das vorhandene Vereinswappen
prüfen, statt den Fehler allein mit Quelltreue zu rechtfertigen.

**Why:** Der Nutzer beanstandete ausdrücklich das kindlich gezeichnete
HSV-Muster der Unity-Quelle und gab dessen Korrektur anhand seines realen
Tribünenfotos samt direktem Einbau frei.

**How to apply:** Die Freigabe betrifft das HSV-Sitzmuster, nicht die
Stadiongeometrie oder Kapazitäten. Bei vergleichbaren Korrekturen Muster
über die tatsächlichen UV-Flächen abgleichen und im Stadion ansehen;
ein sauberes Wappenbild allein beweist keine unverzerrte Projektion.

Bei Sitzschriftzügen nicht voraussetzen, dass jeder UV-Punkt genau einer
Welthöhe entspricht. Crowd-Atlanten können dieselbe Bildstelle für Tritt-
und Setzflächen wiederverwenden; die Schrift muss trotzdem eine Zeile bleiben.

**Why:** Bei der Veltins-Quelle führte eine höhenabhängige Neuzeichnung zu
widersprüchlichen Schriftzeilen auf gemeinsam genutzten Atlasflächen.

**How to apply:** Vor einer weltkoordinatenbasierten Sitzbemalung die
UV-Wiederverwendung prüfen. Bei geteilter Registrierung den belegten
Schriftbereich des Atlasses erhalten und die fertigen Buchstaben am
Quellmodell prüfen, nicht nur als flaches Texturbild.
