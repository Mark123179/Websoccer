---
name: Momentum-Kurve Torseiten-Konsistenz
description: Regel für die Spielbericht-Momentum-Kurve — jedes Tor muss auf der Kurvenseite des Schützen liegen; Glättung darf das nicht aushebeln.
---

# Momentum-Kurve: Tor muss auf Schützenseite liegen

**Regel:** In der Spielbericht-Momentum-Kurve muss die Kurve an jeder Torminute auf der Seite des Torschützen liegen (Heim = positiv, Auswärts = negativ, Mindestabstand ~0.15). Reines Glätten von Event-Impulsen reicht nicht — dicht aufeinanderfolgende Tore beider Teams heben sich sonst gegenseitig auf und Marker landen auf der "falschen" Seite.

**Why:** Nutzerfeedback (Task-661-Kontext, Juli 2026): ein Auswärtstor bei Heim-Momentum wirkt wie ein Datenfehler, selbst wenn die Glättung mathematisch korrekt ist. Optik schlägt hier Signalverarbeitung.

**How to apply:**
- Drangphasen-Impulse VOR dem Tor (m-3..m-1, ansteigend) statt nur Impuls an der Torminute — erzeugt visuell plausiblen Anstieg.
- Nach Normalisierung ein Konsistenz-Durchlauf: lokale Korrektur mit kleinem Dreieckskern (±2min, 2 Iterationen) + finaler direkter Clamp der Torminute.
- Sonderfall: Tore BEIDER Teams in derselben Minute → keine Seite erzwingen (mathematisch unlösbar), Minute überspringen.
- Verifikation immer über viele Matches scripten (Kurve + Marker paarweise prüfen), nicht nur ein Beispiel-Match ansehen.
