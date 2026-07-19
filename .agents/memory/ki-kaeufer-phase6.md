---
name: KI-Käufer Stufe 2 (Finanz-Phase 6)
description: Designentscheidungen und Fallen des KI-Käufers (AITransferOffer/AIBuyerRun, game/economy/ai_buyer/)
---

# KI-Käufer Stufe 2 — Entscheidungen & Fallen

## Bewertungssymmetrie ⇒ KI-zu-KI-Clearing dealt strukturell NIE
Spec 9.3: Verkäufer-Forderung = Bewertung × 1,1–1,3, Käufer-Max = 1,0 × Bewertung
(bei Bedarf; Qualität/Talent noch weniger). Beide Seiten nutzen dieselbe
Schmerzgrenzen-Bewertung ⇒ max_gebot < Forderung IMMER ⇒ `ki_zu_ki_clearing`
kann nie abschließen; Deals entstehen nur bei Manager-Vereinen via Gebotstreppe
(70/90/100 % mit Dringlichkeits-Gates).
**Why:** Trockenlauf auf Live-Daten (26 Läufe) ergab 0 Angebote — empirisch
bestätigt; Architect stufte es als Spec-Widerspruch ein (Spec erwartet im
Ito-Referenzfall „KI-zu-KI sofort").
**How to apply:** NICHT stillschweigend patchen — Balancing-Entscheidung des
Users. Naheliegende Korrektur: Clearing gegen Schmerzgrenze (Reserve) statt
gegen Forderung. Log „kein bezahlbarer Kandidat" ist dabei irreführend (Budget
war nie das Gate).

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
