# Vereins-/Spielerimport (Creator-Mode)

Technische Projektdokumentation des gesamten Vereins-/Spielerimports — von der
Auftragserstellung über den lokalen Importer bis zum verbindlichen
Datenbankimport. Sie beschreibt Architektur, Datenfluss, die geschützte
Token-API sowie die Kernregeln zu Saison, Positionen, Überschreiben und
Sicherheit.

> **Leitprinzip:** Der Server berechnet, normalisiert und schreibt; der lokale
> Importer liest nur Rohdaten und überträgt sie. Auf dem Server findet **kein**
> Scraping statt, der Importer berechnet **keine** finalen Attribute und
> importiert **keine** Bilder.

---

## 1. Überblick & Architektur

Der Import besteht aus vier Bausteinen, die über eine token-geschützte
JSON-API zusammenspielen:

```
┌──────────────────────┐     HTTPS + Bearer-Token      ┌───────────────────────┐
│  Lokaler Importer     │  ───────────────────────────▶ │  Token-API (Server)    │
│  (Windows, MS Edge)   │   next / claim / heartbeat     │  game/views_importer_  │
│  tools/cfm_importer/  │   progress / candidates        │  api.py                │
│                       │   complete / fail              │                        │
│  liest TM/FMInside/   │ ◀─────────────────────────── │  speichert Rohdaten als │
│  SoFIFA → Rohdaten     │     Lease-Token, Status        │  PlayerImportCandidate │
└──────────────────────┘                                └───────────┬───────────┘
                                                                     │
                          ┌──────────────────────────────────────────┘
                          ▼
            ┌──────────────────────────┐        ┌──────────────────────────┐
            │  Engine (game/club_import)│        │  Creator-Oberfläche       │
            │  parsing / positions /    │ ◀────▶ │  game/views_creator.py    │
            │  matching / normalization │        │  Kontrollansicht & Diffs  │
            │  review / import_service  │        │  Auswahl / Überschreiben  │
            └────────────┬─────────────┘        └────────────┬─────────────┘
                         │ verbindlicher DB-Import (Bestätigung)
                         ▼
                ┌──────────────────┐
                │  Spiel-Datenbank  │  Player, Club, PlayerSourceRating,
                │  (PostgreSQL)     │  PlayerExternalId, PlayerStrengthProfile
                └──────────────────┘
```

**Rollen:**

| Baustein | Verantwortung | Ort |
|----------|---------------|-----|
| Lokaler Importer | Sichtbarer Edge, scrapt Rohdaten, überträgt Kandidaten | `tools/cfm_importer/` (eigene `README.md`) |
| Token-API | Authentifizierung, Lease/Heartbeat, Sanitizing, Persistenz der Rohdaten | `game/views_importer_api.py` |
| Engine | Parsing, Positions-/Namenslogik, Matching, Normalisierung, DB-Import | `game/club_import/` |
| Creator-Oberfläche | Auftrag anlegen, Kontrolle, Auswahl/Überschreiben, Bestätigung | `game/views_creator.py`, `game/templates/creator/` |

---

## 2. Datenfluss (Ende zu Ende)

1. **Auftrag anlegen** — Im Creator-Mode legt der Administrator einen Auftrag in
   einem von zwei Modi an (`creator_import_create` → `ClubPlayerImportJob`,
   Status `pending`); die **Saison-ID** wird automatisch bestimmt und
   eingefroren:
   * **Bestehenden Verein befüllen:** ein vorhandener WS-Verein wird als Ziel
     gewählt und die **Transfermarkt-Vereins-ID** angegeben.
   * **Neuen Verein anlegen:** für einen im WS noch nicht existierenden Verein
     gibt der Administrator **Vereinsname + Ziel-Liga + Transfermarkt-Vereins-ID**
     an. Der WS-Verein wird sofort als **echter** Verein
     (`is_import_placeholder=False`) in der gewählten, real existierenden Liga
     angelegt; der Auftrag zeigt direkt darauf. Existiert bereits ein
     Platzhalterverein mit gleicher TM-ID (z. B. früher als Leihgeber erzeugt),
     wird dieser **hochgestuft** statt dupliziert; ein bereits vorhandener
     **echter** Verein wird abgelehnt (siehe Abschnitt 5.7).
2. **Übernahme** — Der lokale Importer holt den nächsten offenen Auftrag
   (`next`), übernimmt ihn exklusiv (`claim`, erhält ein **Lease-Token**) und
   öffnet die Kaderseite über **Vereins-ID + Saison-ID**.
3. **Übertragung** — Pro Spieler werden Stammdaten, Positionsdaten,
   Leihsituation sowie FMInside-/SoFIFA-Rohwerte erfasst und als
   `PlayerImportCandidate` übertragen (`candidates`, Upsert je
   `job + tm_player_id`). Fortschritt/Heartbeats laufen währenddessen
   (`progress` / `heartbeat`). Abschluss per `complete` → Status `review`.
4. **Kontrolle** — Beim Öffnen der Detailansicht baut
   `review.refresh_job_candidates` aus den getrennten Rohdaten das
   `normalized_data`-Schema, ermittelt einen evtl. vorhandenen Spieler und
   berechnet die Alt→Neu-Diffs. Jeder Kandidat erhält einen Status
   (neu / vorhanden-geändert / vorhanden-unverändert / ungültig …).
5. **Auswahl** — Der Administrator wählt Kandidaten aus und markiert vorhandene
   Spieler ggf. zum Überschreiben (`creator_import_bulk` /
   `creator_import_candidate_update`).
6. **Verbindlicher Import** — `creator_import_confirm` ruft
   `import_service.import_selected_candidates`. Jeder Kandidat wird in einer
   eigenen Transaktion geschrieben (Spieler, Platzhaltervereine, Quell-Ratings,
   externe IDs, Stärkeprofil). Abschluss mit Status `completed` und einer
   Ergebniszusammenfassung (erstellt / aktualisiert / übersprungen /
   fehlgeschlagen).

---

## 3. Datenmodelle

`game/models.py`:

- **`ClubPlayerImportJob`** — Lebenszyklus eines Auftrags. Felder u. a.
  `ws_club`, `tm_club_id`, `tm_season_id`, `season_label`, `status`,
  `progress_*`, `current_step` sowie die Lease-Felder `lease_token`,
  `claimed_at`, `lease_expires_at`, `heartbeat_at`. Status-Kette:
  `pending → claimed → running → review → importing → completed`
  (zusätzlich `failed` / `cancelled`). `new_lease_token()` erzeugt das
  Per-Claim-Geheimnis (`secrets.token_hex`).
- **`PlayerImportCandidate`** — Ein Spieler eines Auftrags. Hält die
  **getrennten Rohdaten** je Quelle (`tm_raw`, `position_raw`, `fmi_raw`,
  `sofifa_raw`) sowie das abgeleitete `normalized_data`, `detected_changes`,
  `validation_errors`, `source_warnings`. Steuerflags `selected_for_import` und
  `overwrite_existing`. Eindeutigkeit per `UniqueConstraint(job, tm_player_id)`
  (Basis für Upsert/Wiederaufnahme).

---

## 4. Token-API

`game/views_importer_api.py` — reine Django-`JsonResponse`-Views (kein DRF).
Alle Endpunkte unter `creator-api/import-jobs/` (siehe `game/urls.py`).

| Methode & Pfad | View | Zweck |
|----------------|------|-------|
| `GET  …/next/` | `importer_next_job` | Nächster übernehmbarer Auftrag (oder `204`). |
| `POST …/<id>/claim/` | `importer_claim_job` | Übernahme; liefert `lease_token` + `lease_expires_at`. |
| `POST …/<id>/heartbeat/` | `importer_heartbeat` | Lease verlängern. |
| `POST …/<id>/progress/` | `importer_progress` | `progress_current/total`, `current_step`. |
| `POST …/<id>/candidates/` | `importer_candidates` | Kandidaten (Upsert je TM-ID). |
| `POST …/<id>/complete/` | `importer_complete` | Auftrag auf `review` setzen; optional `tm_club_name` (bestätigt Neuverein-Namen). |
| `POST …/<id>/fail/` | `importer_fail` | Auftrag als `failed` markieren. |

**Authentifizierung & Lease:**

- `Authorization: Bearer <CFM_IMPORTER_TOKEN>` auf **jedem** Aufruf
  (konstant-zeit-Vergleich; Token nur aus Umgebungsvariable).
- Schreibende Auftragsoperationen erfordern zusätzlich das Lease-Token —
  bevorzugt im Header `X-Lease-Token`, alternativ als Feld `lease_token` im
  JSON-Body. Lease-Dauer **3 min**, empfohlener Heartbeat **~25 s**.
- Die Auftragszeile wird je Schreibvorgang per `select_for_update` gesperrt, damit
  Token-/Lease-Prüfung und Schreibvorgang atomar sind.

**Statuscodes:** `200` Erfolg · `204` kein Auftrag · `400` ungültige Eingabe ·
`401` Token falsch/fehlt · `403` Lease falsch/fehlt · `409` Lease abgelaufen /
Auftrag bereits vergeben · `413` Payload zu groß · `429` Rate-Limit ·
`503` API serverseitig nicht konfiguriert.

**Kandidaten-Payload** (Auszug; der Server verwirft unbekannte Schlüssel über
fest verdrahtete Whitelists `_ALLOWED_*`):

```json
{
  "candidate": {
    "tm_player_id": 892160,
    "tm": {
      "display_name": "Luka Vušković", "first_name": "Luka", "last_name": "Vušković",
      "date_of_birth": "07.02.2007", "height_cm": "1,97 m",
      "preferred_foot": "rechts", "nationalities": ["Kroatien"],
      "market_value_eur": "20,00 Mio. €", "profile_position": "Innenverteidiger"
    },
    "club_assignment": { "loaned_from": { "tm_club_id": 148, "name": "Tottenham Hotspur" } },
    "positions": { "main_positions": ["IV"], "secondary_positions": [], "appearances": [] },
    "fmi": { "id": 7654321, "rating": 78, "potential": 90, "attrs": { "zweikampf": 16 } },
    "warnings": ["SoFIFA: kein eindeutiger Treffer (optional)."],
    "errors": []
  }
}
```

Der Server speichert die Rohstrings unverändert; das Parsen der deutschen
Formate (`"1,97 m"`, `"20,00 Mio. €"`, `"rechts"`, `DD.MM.YYYY`) erfolgt erst in
der Engine.

---

## 5. Kernregeln

### 5.1 Saison (`game/club_import/season.py`)
Stichtag **1. Juli** (Europe/Berlin): 01.01.–30.06. → `Jahr − 1`,
ab 01.07. → `Jahr`. Beispiel: 16.06.2026 → `2025` → „2025/26". Die Saison-ID
wird bei Auftragserstellung **einmalig** bestimmt und danach im Auftrag
eingefroren.

### 5.2 Positionen (`game/club_import/positions.py`)
`TM_POSITION_MAP` bildet Transfermarkt-Bezeichnungen auf interne Kennungen ab;
**unbekannte Bezeichnungen werden nicht geraten**, sondern als Warnung gemeldet.
`compute_positions` (reine Funktion) bestimmt Haupt-/Nebenpositionen
(HP ≥ 25 Einsätze, max. 2; NP ≥ 10, max. 2; mindestens eine HP; abgeleitete
Zusatz-HP). In `review.build_normalized_data` haben **explizite** Haupt-/
Nebenpositionen Vorrang vor abgeleiteten Leistungsdaten.

### 5.3 Matching & Überschreiben (`game/club_import/matching.py`)
Erkennung in Prioritätsreihenfolge: Transfermarkt-ID → FMInside-ID → SoFIFA-ID →
normalisierter Name + Geburtsdatum. ID-Treffer sind **stark** (`is_strong`,
automatisch überschreibbar). Ein reiner Name+Geburtsdatum-Treffer ist **schwach**
und wird nur als Dublettenwarnung behandelt — ohne ausdrückliches
`overwrite_existing` wird **nicht** geschrieben. Beim Überschreiben werden alte
Quellwerte vollständig ersetzt bzw. gelöscht (keine Altwerte verbleiben).

### 5.4 Platzhaltervereine (`import_service.get_or_create_club`)
Existiert der reale Verein oder Leihgeber eines Spielers nicht, wird ein
**Minimal-Platzhalter** (`is_import_placeholder=True`) in der Liga
„Platzhalter (Import)" angelegt. Dedup über `transfermarkt_id`, danach über den
normalisierten Namen.

### 5.5 NULL-statt-0
Fehlende Werte bleiben `None` / `''` — **niemals `0`**. Eine `0` wäre ein echter
Wert und würde die Stärke-Kalibrierung verfälschen. Diese Regel gilt durchgängig
in `parsing.py`, `review.py` und `import_service.py`.

### 5.6 Fehlende/uneindeutige Quellen
Fehlendes **SoFIFA** blockiert den Import nicht (es wird einfach kein externer
SoFIFA-Eintrag geschrieben); analog wird ohne **FMInside**-Daten kein
FMInside-Rating gesetzt. `source_warnings` eines Kandidaten speist sich aktuell
aus der Positionsberechnung (`build_normalized_data`) — es gibt **keine**
automatische „FMInside/SoFIFA fehlt"-Warnung auf Serverseite; entsprechende
Hinweise liefert der lokale Importer im `warnings`-Feld der Rohdaten. Einzelne
Parser-/Seitenfehler überspringen nur den betroffenen Spieler.

### 5.7 Neuen Zielverein anlegen (`import_service.create_or_promote_target_club`)
Beim Modus „Neuen Verein anlegen" (Abschnitt 2) entsteht — anders als bei den
Platzhaltervereinen aus 5.4 — ein **echter** Verein
(`is_import_placeholder=False`) in einer vom Administrator gewählten, real
existierenden WS-Liga. Dedup-Priorität wie bei `get_or_create_club`:
`transfermarkt_id`, danach normalisierter Name. Ergebnis (`created` / `promoted`
/ `exists`):

- **created** — kein Treffer; neuer echter Verein wird angelegt
  (Gründungsjahr/Budget mit neutralen Startwerten, später im Vereins-Admin
  editierbar).
- **promoted** — es existiert bereits ein **Platzhalterverein** mit gleicher
  TM-ID/Name; er wird zum echten Verein hochgestuft (Liga gesetzt,
  Platzhalter-Flag entfernt) — **kein Duplikat**.
- **exists** — es existiert bereits ein **echter** Verein; der Auftrag wird mit
  Hinweis abgelehnt (stattdessen Modus „Bestehenden Verein befüllen" nutzen).

`ClubPlayerImportJob.ws_club` bleibt ein Pflicht-Fremdschlüssel und zeigt auf den
frisch angelegten/hochgestuften Verein. Die gesamte nachgelagerte Pipeline
(Importer, Kontrolle, DB-Import) bleibt unverändert.

#### Vorläufiger Name & TM-Bestätigung

Der beim Anlegen **manuell eingegebene** Vereinsname ist zunächst nur ein
Platzhalter: `created`/`promoted` setzen daher `Club.import_name_provisional =
True`. Sobald der lokale Importer die Kaderseite gelesen hat, überträgt er den
dort angezeigten Vereinsnamen beim `complete`-Aufruf als `tm_club_name`. Der
Server speichert ihn auf `ClubPlayerImportJob.tm_club_name` und — **nur** wenn
`import_name_provisional` gesetzt ist — bestätigt/aktualisiert er damit
`Club.name`/`short_name` und löscht das Flag.

So bleibt ein vom Administrator gewählter **bestehender** Verein (Modus
„befüllen", `import_name_provisional = False`) garantiert unverändert, während ein
neu angelegter Verein automatisch den echten Transfermarkt-Namen erhält. Fehlt
der Name (älterer Importer, Header nicht lesbar), bleibt der manuelle Name samt
Flag erhalten — der Schritt ist vollständig rückwärtskompatibel.

---

## 6. Sicherheit (Härtung)

- **Token** ausschließlich aus `CFM_IMPORTER_TOKEN`, nie im Repo/Log; im
  lokalen Importer wird der Token in jeder Logzeile maskiert.
- **CSRF** ist nur auf den API-Endpunkten deaktiviert; die Creator-Weboberfläche
  bleibt CSRF- und login-geschützt.
- **Whitelist statt Freitext:** Der Importer kann keine beliebigen Modellfelder
  bestimmen — der Server filtert jede Eingabe gegen feste Feldlisten
  (`_ALLOWED_TM`, `_ALLOWED_POSITION_KEYS`, …).
- **Limits:** Payload-Größe (1 MB), Kandidaten pro Batch (50), Rate-Limit
  (240 Requests/60 s pro Client-IP).
- **Lease-Bindung:** Genau ein Importer pro Auftrag; ein veralteter Importer
  kann nach Lease-Wechsel keinen Zustand mehr überschreiben.

---

## 7. End-to-End-Abnahme (Referenzfall)

Als manueller Referenzfall dient der **HSV** (Transfermarkt-Vereins-ID **41**,
Saison-ID **2025**) mit **Luka Vušković** (Transfermarkt-Spieler-ID **892160**).
Diese Werte sind reine Eingabedaten — sie sind **nicht** als Sonderregel im
Produktivcode verdrahtet.

Der Durchlauf ist als automatisierte Abnahme in
`game/tests/test_club_import_e2e.py` hinterlegt und deckt die komplette Kette
über die echten Komponenten ab:

1. **Auftrag anlegen** (HSV, TM-Verein 41, Saison 2025/26).
2. **Token-API:** `next` → `claim` (Lease) → `candidates` (Batch) → `complete`.
3. **Kontrolle:** `refresh_job_candidates` klassifiziert die Kandidaten und
   berechnet Diffs.
4. **Verbindlicher Import:** `import_selected_candidates` schreibt die Auswahl.

Belegte Fälle:

| Fall | Erwartung | Beleg im Test |
|------|-----------|---------------|
| **Neuer Spieler** (Vušković) | wird angelegt (IV, 197 cm, Marktwert 20 Mio., Fuß R) | `test_full_pipeline_hsv_reference_case` |
| **Vorhandener Spieler** | wird gezielt überschrieben (Marktwert/Position geändert), kein Duplikat | dito |
| **Fehlendes SoFIFA** | blockiert nicht; kein SoFIFA-Eintrag, FMInside-Rating vorhanden | dito |
| **Platzhalterverein** (Tottenham als Leihgeber) | wird automatisch als `is_import_placeholder` erzeugt | dito |
| **NULL-Erhalt** | fehlende Werte bleiben `None`/`''` | Engine-Tests + E2E |
| **Importbestätigung** | korrekte Zusammenfassung (created/updated/…); Endstatus „importiert" | dito |
| **Ohne Auswahl** | vorhandener Spieler bleibt unangetastet | `test_unselected_existing_player_is_not_overwritten` |
| **Neuer Verein** | wird als echter Verein in der gewählten Liga angelegt; Platzhalter wird hochgestuft statt dupliziert; echter Bestandsverein wird abgelehnt | `test_club_import_new_club.py` |

**Reproduktion:**

```bash
python manage.py test game.tests.test_club_import_e2e --verbosity=2 --keepdb
```

---

## 8. Tests

| Bereich | Datei |
|---------|-------|
| Engine & Datenmodelle (Saison, Positionen, Parsing, Matching, DB-Import) | `game/tests/test_club_import.py` |
| Token-API (Auth, Lease, Sanitizing, Limits) | `game/tests/test_importer_api.py` |
| Creator-Oberfläche (Kontrollansicht, Auswahl, Bestätigung) | `game/tests/test_club_import_ui.py` |
| End-to-End-Abnahme (HSV/Vušković-Referenzfall) | `game/tests/test_club_import_e2e.py` |
| Neuen Verein anlegen (Helfer + Auftrags-Erstellung) | `game/tests/test_club_import_new_club.py` |

Gesamten Import-Bereich ausführen:

```bash
python manage.py test \
  game.tests.test_club_import \
  game.tests.test_importer_api \
  game.tests.test_club_import_ui \
  game.tests.test_club_import_e2e \
  game.tests.test_club_import_new_club \
  --keepdb
```

---

## 9. Verwandte Dateien

- Token-API: `game/views_importer_api.py`
- Engine: `game/club_import/{season,positions,matching,normalization,parsing,review,import_service}.py`
- Creator-Oberfläche: `game/views_creator.py`, `game/templates/creator/import_index.html`, `import_detail.html`
- Datenmodelle: `game/models.py` (`ClubPlayerImportJob`, `PlayerImportCandidate`)
- Routing: `game/urls.py`
- Lokaler Importer: `tools/cfm_importer/` (Endnutzer-Anleitung in dessen `README.md`)
