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
