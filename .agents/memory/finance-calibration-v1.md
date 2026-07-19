---
name: Finanz-Kalibrierung V1 (Phase 7)
description: Regeln für Kalibrierungs-Report, Regler-Edit-UI und Saison-Versionierung der EconomyParameter
---

# Finanz-Kalibrierung V1 — Regeln

- **Nur EconomyParameter justieren, nie Code-Konstanten.** Formeln sind spec-fixiert (Spec Kap. 16/17); keine Selbstjustierung — jede Änderung ist eine bewusste Admin-Entscheidung.
  - **Why:** Task-Vorgabe Phase 7; Selbstjustierung würde Balancing-Freezes unterlaufen.
  - **How to apply:** Kalibrierungs-Änderungen laufen über Creator → Kalibrierung oder Seed-Migrationen; Code-Konstanten (z. B. Match-Engine) bleiben unberührt.
- **Kennzahlen-Status kennt `nicht_messbar` — nie stilles `ok`.** Dünne Datenbasis (fehlender zweiter MW-Snapshot, 0 Transfers, laufende Saison bei Gehältern) muss explizit als nicht messbar ausgewiesen werden.
- **Regler-Edit-UI-Schutzregeln:** (1) keine neuen Keys via UI (nur Seed-Migrationen), (2) Top-Level-JSON-Typ muss dem Altwert entsprechen (bool separat VOR int prüfen — `isinstance(True, int)` ist True), (3) `KI_KAEUFER.dry_run` wird beim Speichern immer aus dem effektiven Altwert (`get_param`) übernommen, damit ein Regler-Edit die KI-Transferzentrale nicht versehentlich scharf schaltet.
- **Saison-Versionierung = Snapshot-Semantik:** Speichern schreibt immer `update_or_create(saison=aktuelle Saison, key)`; ältere Saisons bleiben unangetastet, `get_param` fällt auf die jüngste frühere Saison zurück. Der Typ-Vergleich muss deshalb gegen `get_param` (effektiver Wert) laufen, nicht gegen die letzte Zeile desselben Keys.
- **Auktionsvolumen ist bewusst ohne Parameter-Key** — zweite große Geldsenke als Admin-Empfehlung im Leitfaden, kein EconomyParameter.
