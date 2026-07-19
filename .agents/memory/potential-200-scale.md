---
name: potential_200 Skalenregel (Ökonomie)
description: Player.potential ist 100er-Rohwert; Ökonomie/Schmerzgrenze rechnet auf der 200er-Stärkeskala
---

# potential_200 — Skalenfalle in der Ökonomie

Regel: `Player.potential` ist ein 100er-Rohwert; `base_strength`/`staerke_median`
leben auf der 200er-Skala (Summe zweier Quellen-Ratings). Jede Ökonomie-Logik,
die Potential mit Stärke oder Stärke-Medianen vergleicht, MUSS
`schmerzgrenze.potential_200()` nutzen (Quellen-Potentiale summiert, ×2 bei nur
einer Quelle, sonst Rohwert ×2). `SeasonEconomySnapshot.potential_median` ist
seit dem Fix ebenfalls 200er-Skala (Spec nennt ~150).

**Why:** Der Zukunftswert-Pfad der Schmerzgrenze v2 war durch den
Skalen-Mismatch praktisch tot (Rohwert 60–90 nie > 200er-Median) — Talente
hatten keinen Verkaufsaufschlag. Der Fix ändert live Schmerzgrenzen: KI-Clubs
lehnen jetzt Gebote auf junge High-Potential-Spieler ab, die sie vorher
angenommen hätten (beabsichtigt).

**How to apply:** Neue Vergleiche Potential↔Stärke immer über potential_200;
Tests, die Zukunftswert prüfen, auf 200er-Semantik rechnen
(Kurve(pot_200) × Realisierung(alter, pot_200−stärke)).
