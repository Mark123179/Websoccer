---
name: KI-Käufer Stufe 2 (Finanz-Phase 6)
description: Designentscheidungen und Fallen des KI-Käufers (AITransferOffer/AIBuyerRun, game/economy/ai_buyer/)
---

# KI-Käufer Stufe 2 — Entscheidungen & Fallen

## KI-zu-KI-Clearing dealt gegen die RESERVE, nie gegen die Forderung
Die erwartete Forderung (Bewertung × 1,1–1,3) ist NUR Ranking-Heuristik fürs
Nutzen-Sortieren gegenüber Manager-Vereinen. Beim KI-zu-KI-Clearing sind beide
Bewertungen systemseitig bekannt: Deal, wenn Käufer-Max ≥ Schmerzgrenze des
Verkäufers (Reserve), Preis = Mittelwert. Effekt: nur Bedarfskäufe
(Max = 1,0×) clearen KI-zu-KI — exakt zur Schmerzgrenze; Qualität (0,85×) und
Talent (0,9× Zukunftswert) nie.
**Why:** Beide Seiten nutzen dieselbe Schmerzgrenzen-Bewertung
(Bewertungssymmetrie) ⇒ gegen die 1,1–1,3×-Forderung wäre max_gebot < Forderung
IMMER und Clearing strukturell tot (Trockenlauf: 26 Läufe, 0 Deals); Spec 9.3
verlangt aber den Ito-Referenzfall „KI-zu-KI sofort".
**How to apply:** Auch Bezahlbarkeits-Gates (Prüflauf) am Käufer-Maximum
messen, nicht an der Forderung — sonst werden Manager-Angebote unterdrückt,
die die Gebotstreppe nie über Max führt.

## Trockenlauf-Altbestand beim Scharfschalten stornieren
`berechnet`-Angebote (dry_run) haben kein gueltig_bis und laufen nie ab; sie
zählen in Kadenz-Limits (`_manager_kadenz_ok`, `_fenster_angebote`) und
sperren Kandidaten (`_gesperrte_spieler_ids`). Der dry_run-Toggle in der
KI-Transferzentrale storniert sie deshalb beim Umschalten auf scharf.
**How to apply:** Jeder neue Pfad, der dry_run→scharf umschaltet (z. B. per
Command), muss denselben Storno machen, sonst ist die Angebotsaktivität im
ersten scharfen Fenster massiv unterdrückt.

## Kadenz-Limits (eingefroren)
Manager-Postfach: max 2 offene / 4 je Fenster. KI-Seite: max 1 offen / 3 je
Fenster. Im Trockenlauf zählt Status `berechnet` als offen (bewusst, damit die
Simulation realistisch bleibt).

## Leak-Schutz
`bewertung`/`max_gebot`/`noise_seed` verlassen NIE den Server Richtung
Manager (nur Creator-Admin sieht sie, staff-gated). Serializer-Leak-Tests in
test_finance_phase6.py decken payload/rows/reject-Response ab.
