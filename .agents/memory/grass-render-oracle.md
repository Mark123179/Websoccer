---
name: Gerenderter Rasen-Farborakel
description: Unabhängige Referenzen und neutrale Lambert-Beleuchtung für UV-/Farbraumdiagnosen.
---

Eine gerenderte UV-Prüfung muss Sollpunkte unabhängig von der getesteten
UV-Funktion definieren und mittlere statt ausschließlich voll gesättigter
Farben verwenden.

**Why:** Sonst kann ein gemeinsamer Orientierungsfehler im Soll-/Ist-Pfad
unentdeckt bleiben; reine RGB-Extrema unterscheiden sRGB und lineare
Dekodierung nicht.

**How to apply:** Weltkoordinaten und Bildorientierung explizit festhalten;
Spiegelungs-, flipY- und Farbraumkontrollen müssen bei korrektem Ausgangslauf
jeweils fehlschlagen. Beim echten Three.js-Lambert-Material erzeugt weißes
Ambientlicht mit Intensität π bei deaktiviertem Tonemapping die für einen
direkten sRGB-Bytevergleich nötige Einheitsreflexion (BRDF enthält 1/π).
Diese neutrale Diagnose nicht auf produktive Lichtprofile übertragen.
