---
name: SoFIFA-CSV-Importer — Live-Pfad vs. toter Zwilling
description: Welcher der zwei SoFIFA-Import-Module produktiv ist, plus die DOB-Matching-Entscheidung.
---

# Welcher Importer ist live?

Es gibt ZWEI fast identische Importer-Module. Nur eines ist verdrahtet:

- **LIVE:** `game/sofifa_import_service.py` (`run_sofifa_import`, `_parse_row`,
  `_match_player`). Wird genutzt vom CLI-Command `import_sofifa_csv` UND vom
  Creator-Mode-Upload (`views_creator.creator_sofifa_import`). Die
  Spalten-Aliase, `normalize_*` und `parse_dob` liegen im Command-Modul
  `game/management/commands/import_sofifa_csv.py` und werden von dort importiert.
- **TOT:** `game/sofifa_import.py` (`run_import`, `match_player`) — wird
  produktiv von NICHTS importiert (nur ggf. eigene Tests).

**Why:** Eine Änderung am Matching wurde zuerst im toten Modul gemacht; der
Dry-Run blieb unverändert, weil der Command den Service-Pfad nutzt. Kostet sonst
einen kompletten Debug-Zyklus.

**How to apply:** Jede Änderung an Matching/Parsing/Aliasen IMMER im
Service-Pfad (`sofifa_import_service.py` + `commands/import_sofifa_csv.py`)
machen. Verifizieren mit `python manage.py import_sofifa_csv <csv> --dry-run`
(zeigt Match-Modus `[id]`/`[dob]`/`[name]` und Bilanz).

# DOB-Matching-Regel

Matching-Reihenfolge in `_match_player`: (1) vorhandene sofifa_id (PlayerExternalId)
→ (2) Geburtsdatum, vereinsübergreifend (KEIN Club-Filter) → (3) Name+Verein.

- Genau ein Spieler mit dem DOB → Treffer (Modus `dob`), Name egal.
- Mehrere mit gleichem DOB → Tie-Break über Namensähnlichkeit, nur bei
  eindeutig höchstem Score; sonst Durchfall zum Namens-Fallback.

**Why (Nutzer-Direktive):** Namensungleichheit ist egal (Transfermarkt-Namen
weichen von CMTracker ab, Zweitnamen). Leihspieler stehen in der CSV unter
ihrem Stammverein → Club-Filter im Namens-Fallback schließt sie sonst aus
(Otele-Fall). DOB ist der robuste Schlüssel; CSV-Header `info.birthdate`.

**Risiko:** Einzelner globaler DOB-Treffer wird akzeptiert, auch wenn der Name
abweicht → seltene Fehlzuordnung bei DOB-Kollision möglich. Bewusst akzeptiert
(Nutzer-Vorgabe); Import ist über Dry-Run/Creator-Diff reviewbar.
