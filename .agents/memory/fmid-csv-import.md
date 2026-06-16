---
name: FM-ID-/Identitäts-CSV-Import (Creator)
description: Per-Verein Moneyball-CSV-Upload, der nur Identität + fm_inside_id setzt — Design & Fallen.
---

# FM-ID-/Identitäts-CSV-Import (Creator-Mode)

Browser-Upload (eine Moneyball-CSV pro Verein), der **nur Identität + FM-ID**
setzt — niemals Stärke/Attribute. Service: `game/club_import/fmid_csv_service.py`,
View `creator_fmid_csv_import`, Template `creator/fmid_csv_import.html`, URL
`creator/import/fmids/`. Upload→Dry-Run-Vorschau→Confirm→Cancel (csv_text +
club_id in der Session zwischengespeichert).

## Spalten-Mapping (immer identisch, `;`-getrennt)
`Verein;Ansässig in;Liga;Unique ID;Aufgestellt;Spieler;2. Nation;Nation;Geb.`
- **Verein** → aktueller Verein. `!= Zielverein` ⇒ verliehen → Vereinslos.
- **Unique ID** → `fm_inside_id` (Pflicht; Header-Match Kleinbuchstabe `unique id`).
- **Spieler** → Name (Token[0]=Vorname, Rest=Nachname; ein Token → nur Nachname).
- **Nation** → Haupt-Nat, **2. Nation** → zweite (zusammen `', '`-getrennt).
- **Geb.** → `T.M.JJJJ` (auch einstellig).
- Ansässig in / Liga / Aufgestellt → ignoriert.

## Matching & Schreibregeln
- `find_existing_player(fm_inside_id, name, date_of_birth)`: FM-ID-Treffer
  (`fmi`, stark) hat Vorrang → sonst Name+Geburtsdatum (`name_dob`, schwach).
- **Backfill-Kollision unmöglich:** ein FM-ID-Treffer käme vor dem name_dob-Pfad;
  im name_dob-Fall hat also garantiert kein Spieler diese FM-ID → stempeln safe.
- Bestehende Spieler: **nur leere Felder** ergänzen (dob/nationalities/club/
  real_life_club), kuratierte Daten/Positionen/Stärke NIE überschreiben.
- Verein==Ziel → `club=Ziel`, `loan_status='none'`. Verliehen → `club=None`
  (Vereinslos), `real_life_club=Ziel`, `loan_status='loaned_out'`; Leih-Ziel nur
  protokolliert, **kein** Platzhalterverein angelegt (würde nie promoted werden).

**Why:** Identität first, Werte später per lokalem FM-ID-Importer; NULL bleibt
NULL (0 wäre echter Wert). Per-Zeile `transaction.atomic`, nicht
all-or-nothing — eine kaputte Zeile darf den Stapel nicht abbrechen.

## Fallen
- `Player.age` ist Pflicht (kein Default) → bei neuer Hülle aus DOB rechnen, sonst 0.
- Settings-Modul heißt **`core.settings`** (nicht `websoccer`); Smoke-Tests via
  `python manage.py shell < script.py` laufen lassen (PYTHONPATH stimmt dann).
- Club-Dropdown filtert `is_import_placeholder=False`.
