---
name: Stadionökonomie Phase 3
description: Nachfrageformel, Ausbau-Bauzeit, 0-€-Buchungsregel und Layout/Ambiente-Split des Stadionumfelds
---

# Stadionökonomie Phase 3 — Kernentscheidungen

- **Kein gepflegter Fanbasis-Wert.** Zuschauer-Nachfrage wird pro Heimspiel live berechnet: Basis aus Kader-Marktwert (NACHFRAGE_KOEFF × MW_Mio^EXP) × Beliebtheit × Gegnerfaktor × Preisfaktor, kategorieweise (Steh/Sitz/VIP) gekappt. Verein ohne Kader-MW ⇒ Nachfrage 0.
  **Why:** Spec Kap. 5.1 verbietet einen zweiten zu balancierenden Zustandswert; MW ist bereits die kanonische Stärkegröße.
  **How to apply:** Nie ein `fanbase`-Feld einführen; neue Attraktivitäts-Einflüsse als Faktor in `compute_demand` (game/economy/stadium.py), Parameter nur über EconomyParameter-Seeds.

- **0-€-Spieltage erzeugen KEINE Ledger-Zeile.** `record_matchday_revenue` legt den MatchdayRevenue-Eintrag immer an, ruft `book()` aber nur bei Einnahmen > 0.
  **Why:** Architect-Review: 0,00-€-TICKET-Zeilen sind Ledger-Rauschen; Tests, die auf die Buchung prüfen, brauchen einen Kader mit Marktwert.

- **Ausbau wirkt erst nach Bauzeit.** `stadium_expand` erhöht Kapazität nicht mehr sofort: StadiumExpansion mit `completes_at`/`applied=False`; `resolve_due_expansions()` claimt per bedingtem UPDATE (applied=False→True) + F()-Ausdruck — idempotent, rennsicher. MAX-Check und Kostenband werden INNERHALB der Club-Sperre (select_for_update) berechnet, inkl. pending seats.
  **Why:** Sofort-Kapazität machte Bauzeit bedeutungslos; Check außerhalb der Sperre ließ parallele Aufträge das STADION_MAX gemeinsam überschreiten.
  **How to apply:** Jeder neue Aufrufort, der Kapazität liest, sollte vorher `resolve_due_expansions()` hooken (aktuell: stadium_detail, management_stadionumfeld, run_club_finance vor transaction.atomic).

- **Stadionumfeld: Layout global, Ambiente per Verein.** STADIONUMFELD_LAYOUT_KEYS (positions/badgePos/selected) → Singleton StadionumfeldConfig; AMBIENTE_KEYS (heimspiel/tod/wetter/day) → ClubStadionumfeldState.for_club. `stadionumfeld_save` MERGT je Ziel (kein Vollersatz), sonst wischt ein partieller POST das Layout weg. Superuser-Gate bleibt bewusst bestehen — Manager können Ambiente (noch) nicht selbst ändern.

- **Ausbau-Kosten nach ZIEL-Band gesplittet.** get_expansion_cost läuft Band für Band über die Zielkapazität (Referenz: 10k→25k SITZ = 27,5 Mio €); Kategorie-Faktoren STEH 0,6 / VIP 4,0; Maximum via max_kapazitaet() aus STADION_MAX — keine MAX_KAPAZITAET-Konstante mehr.
