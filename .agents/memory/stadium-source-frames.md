---
name: Stadion-Quellrahmen und Herkunft
description: Themenindex zu Sitzrahmen, Dächern, geografischem Umfeld, ausfahrbaren Feldern und Rekonstruktionen.
---

- [Dortmund Unity seat/mesh frame](dortmund-unity-frame.md) — Sitz-JSON ist ungedreht, Mesh-Export hat 90° Parent-Rotation gebacken; Standzuordnung immer gegen Crowd-Bounds prüfen.
- [Borussia-Park Sitzrahmen](gladbach-source-frame.md) — Sitz-JSON erst um +90° an World-Meshes anbinden; bei neuen Bundles Bereichs-Bounds erneut vergleichen.
- [Dortmund roof layers](dortmund-roof-layers.md) — Dachhaut, Decke und Träger überlagern sich in mehreren Unity-Meshes; einzelne Dachmeshes ausblenden reicht für Innenansichten nicht.
- [Dortmund OSM context](dortmund-osm-context.md) — Umgebung aus realen OSM-Lagen und grobem DEM, nicht aus erfundenen Bergen; Modell-Nord und Kartennord müssen getrennt kalibriert werden.
- [Dortmund single-side expansion edges](dortmund-single-side-expansion-edges.md) — Endkappen allein schließen Einzel-Ausbau nicht: Rangbreite am freien Ende auf Bestandskante begrenzen; Rundum darf verbreitern.
- [Dortmund Bestand source attribution](dortmund-bestand-facade-attribution.md) — Gegenseite darf als beschriftete Rekonstruktion geschlossen sein; niemals als Unity-Quelle ausgeben.
- [Überlappende Dach- und Ranghöhen](stadium-roof-height-overlap.md) — Höhenbasierte Dachschalter können Oberrang-Stufen ausblenden; Schema- und Hashprüfung reichen nicht.
- [Amtliche Dachdeckung](official-roof-coverage.md) — Echte Quelllücken nicht als Rundung verstecken; unvollständige Dächer behalten ihre ausdrücklich schematische Hülle.
- [Ausfahrbare Spielfelder](stadium-rollout-pitch-frame.md) — Veltins-OSM-Feld liegt außerhalb; Umfeld an der Arena statt am geparkten Rasen ausrichten.
