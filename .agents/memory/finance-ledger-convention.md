---
name: Finanz-Ledger Buchungs-Konvention
description: Wie Budget-Mutationen zu buchen sind (seit Phase 1 via game.economy.booking.book) und welche Saison-Konvention im Ledger gilt.
---

# Finanz-Ledger — Buchungs-Konvention

**Regel (seit Finanzsystem Phase 1):** Jede Mutation von `Club.budget` läuft
über `game/economy/booking.py::book()` bzw. `book_many()` — die Funktion
sperrt selbst (`select_for_update`), schreibt die `FinanceTransaction`-Zeile
und aktualisiert den Budget-Cache atomar. NIE Budget von Hand mutieren und
daneben loggen. `game/finance.py::log_club_transaction()` ist nur noch ein
Legacy-Wrapper um `book()` (mappt Alt-Kategorien auf Typen) und bucht das
Budget MIT — Aufrufer dürfen nicht zusätzlich selbst mutieren.
Details: siehe [finance-ledger-phase1.md](finance-ledger-phase1.md).

**Saison-Konvention:** `FinanceTransaction.saison` ist IMMER die numerische
Sim-Saison als String (`str(GameSeasonState.current_season)`, z. B. `"0"`).
TM-Labels wie `"2025/26"` sind verboten — Manager-Kontoauszug und
Creator-Finanzanalyse filtern exakt auf diesen String. Alt-Zeilen mit `/`
wurden per Datenmigration gemappt.

**Why:** Scouting buchte anfangs mit TM-Saisonlabels, wodurch die
Manager-Finanzansicht (numerischer Filter) diese Buchungen unsichtbar
verschluckte. Außerdem hatte stadium_expand einen TOCTOU-Bug
(Budget-Check ohne Lock) — `book()` erzwingt jetzt beides zentral.

**How to apply:** Neuer Geldfluss = ein `book(club, TYP, betrag, …)`-Aufruf
(positiv = Einnahme, negativ = Ausgabe; `pflicht=True` nur für Gehälter/
Betrieb/Unterhalt). Typen aus `FinanceTransaction.TYP_CHOICES`.

Globale Auswertung: Creator-Seite „Finanzanalyse" (`/creator/finanzen/`,
staff-only). Creator-Navigation ist zentral in
`game/templates/creator/_nav_pills.html` (nav_active-Parameter) — neue
Creator-Seiten dort eintragen, nicht Pill-Blöcke duplizieren.
