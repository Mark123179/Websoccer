---
name: Finanz-Ledger Buchungs-Konvention
description: Wie Budget-Mutationen zu loggen sind (log_club_transaction) und welche Saison-Konvention im ClubFinancialTransaction-Ledger gilt.
---

# Finanz-Ledger — Buchungs-Konvention

**Regel:** Jede Mutation von `Club.budget` MUSS in derselben DB-Transaktion eine
Ledger-Zeile über `game/finance.py::log_club_transaction()` schreiben, auf der
per `select_for_update` gesperrten Club-Zeile.

**Saison-Konvention:** `ClubFinancialTransaction.season` ist IMMER die
numerische Sim-Saison als String (`str(GameSeasonState.current_season)`, z. B.
`"0"`). TM-Labels wie `"2025/26"` sind verboten — die Manager-Finanzansicht
und die Creator-Finanzanalyse filtern exakt auf diesen String. Alt-Zeilen mit
`/` wurden per Datenmigration auf die Sim-Saison gemappt.

**Why:** Scouting buchte anfangs mit TM-Saisonlabels, wodurch die
Manager-Finanzansicht (numerischer Filter) diese Buchungen unsichtbar
verschluckte. Außerdem hatte stadium_expand einen TOCTOU-Bug
(Budget-Check ohne Lock).

**How to apply:** Bei jedem neuen Geldfluss: `with transaction.atomic():`
→ `Club.objects.select_for_update().get(...)` → Budget mutieren →
`log_club_transaction(locked, kategorie, beschreibung, betrag)`.
Kategorien kommen aus `ClubFinancialTransaction.CATEGORY_CHOICES`;
positiv = Einnahme, negativ = Ausgabe. `log_club_transaction` ist die
Austausch-Naht für das spätere FinanceTransaction-Ledger aus der
Finanzsystem-Spec (Phase 1) — Aufrufer nicht direkt auf das Modell koppeln.

Globale Auswertung: Creator-Seite „Finanzanalyse" (`/creator/finanzen/`,
staff-only). Creator-Navigation ist zentral in
`game/templates/creator/_nav_pills.html` (nav_active-Parameter) — neue
Creator-Seiten dort eintragen, nicht Pill-Blöcke duplizieren.
