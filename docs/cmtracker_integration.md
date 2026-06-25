# cmtracker-Integration — CMTracker-Ratings importieren

Technische Dokumentation der cmtracker-Anbindung: vom API-Abruf über das
Abflachen der JSON-Antwort bis zur Übergabe an den bestehenden CMTracker-Importer.
Beschreibt Architektur, Feldmapping, das geprüfte Dry-Run-Ergebnis, die
Sandbox-Einschränkung, die Matching-/ID-Strategie sowie den Plan für den
Live-Modus.

> **Leitprinzip:** cmtracker liefert nur Rohwerte. Der bestehende Importer
> (`game/sofifa_import_service.py`) bleibt die **einzige** Schreibstelle —
> inklusive Matching, Logging und Stärkeberechnung. Die cmtracker-Schicht
> übersetzt ausschließlich JSON → CSV. Es findet **kein** Scraping statt und
> der API-Key wird **nie** ausgegeben.

---

## 1. Architektur & Datenfluss

```
┌─────────────────────────┐   X-API-Key (HTTPS)   ┌────────────────────────┐
│  cmtracker API           │ ◀──────────────────── │  game/cmtracker_api.py  │
│  api.cmtracker.net/v1     │   GET /dbs /players    │  CmtrackerClient        │
│  (FC26-DB-Slug 26062400)  │ ────────────────────▶ │  iter_players()         │
└─────────────────────────┘     JSON (verschacht.)  └───────────┬────────────┘
                                                                  │ _dig / players_to_csv
                                                                  ▼ (dotted CSV-Header)
                                            ┌──────────────────────────────────┐
                                            │  import_sofifa_csv.COLUMN_ALIASES  │
                                            │  normalize_header → Zielspalten    │
                                            └───────────────┬───────────────────┘
                                                            ▼
                                       ┌────────────────────────────────────────┐
                                       │  sofifa_import_service.run_sofifa_import │
                                       │  Matching → Diff → (DB-Schreiben) →      │
                                       │  calculate_player_strengths              │
                                       └────────────────────────────────────────┘
```

- **Client:** `game/cmtracker_api.py` (`CmtrackerClient`, Auth via Header
  `X-API-Key`, Methoden `list_dbs` / `list_players` / `get_player` /
  `iter_players`). `CSV_COLUMNS` definiert die gepunkteten JSON-Pfade,
  `_dig`/`_cell`/`players_to_csv` flachen die Antwort zu CSV ab.
- **CLI:** `python manage.py import_cmtracker` mit
  `--list-dbs`, `--dry-run`, `--sandbox`, `--team/--league/--min-overall`,
  `--limit/--max-pages`, `--skip-recalculate`.
- **Brücke:** Die gepunkteten Header (`info.overallrating` …) werden über
  `COLUMN_ALIASES` aufgelöst, weil `normalize_header` die Punkte entfernt.
- **Konfiguration:** Basis-URL überschreibbar via `CMTRACKER_BASE_URL`.
  Der API-Key liegt ausschließlich im Secret `CMTRACKER_API_KEY`.

---

## 2. Feldmapping (cmtracker-JSON → Websoccer-Zielfeld)

**Identität & Stammdaten**

| cmtracker-Pfad | Zielfeld |
| --- | --- |
| `info.playerid` | `sofifa_id` (externe ID, wird persistiert — siehe §5) |
| `info.name.knownas` | `name` |
| `info.name.firstname` | `first_name_raw` |
| `info.name.lastname` | `last_name_raw` |
| `info.teams.club_team.name` | `club` |
| `info.overallrating` | `rating` |
| `info.potential` | `potential` |
| `info.birthdate` | `dob` |

**Feldspieler-Attribute**

| cmtracker-Pfad | Zielfeld |
| --- | --- |
| `card_attrs.pac` | `tempo` |
| `attributes.stamina` | `ausdauer` |
| `attributes.strength` | `kraft` |
| `attributes.ballcontrol` | `technik` |
| `attributes.dribbling` | `dribbling` |
| `attributes.shortpassing` | `passspiel` |
| `attributes.crossing` | `flanken` |
| `attributes.finishing` | `abschluss` |
| `attributes.headingaccuracy` | `kopfball` |
| `attributes.standingtackle` | `zweikampf` |
| `attributes.marking` | `defensivstellung` |
| `attributes.vision` | `uebersicht` |
| `attributes.penalties` | `elfmeter` |
| `attributes.freekickaccuracy` | `freistoss` |

**Torwart-Attribute**

| cmtracker-Pfad | Zielfeld |
| --- | --- |
| `attributes.gkreflexes` | `tw_reflexe` |
| `attributes.gkhandling` | `tw_fangsicherheit` |
| `attributes.gkpositioning` | `tw_stellungsspiel` |
| `attributes.gkkicking` | `tw_passen` |
| `attributes.gkdiving` | `tw_eins_gegen_eins` |

---

## 3. Dry-Run-Ergebnis (Sandbox, End-to-End-Test)

Kommando: `python manage.py import_cmtracker --sandbox --dry-run`
(keine DB-Schreibaktion).

- **Abruf:** 25 Spieler aus der Sandbox-Stichprobe.
- **Bilanz:** `0 neu · 2 aktualisierbar · 0 unverändert · 23 nicht gematcht · 0 Fehler`.
- **Gematcht (jeweils per DOB):** Harry Kane und Michael Olise
  (beide FC Bayern München) — existieren in der Websoccer-DB.
- **23 nicht gematcht:** ausschließlich Nicht-Bundesliga- bzw.
  Frauenfußball-Spieler:innen, die es in Websoccer nicht gibt → erwartetes,
  korrektes Verhalten.

Fazit: Die komplette Kette **API → Flatten → CSV → Importer → DOB-Matching**
greift nachweislich. Der Dry-Run gilt als erfolgreicher End-to-End-Test; ein
echter Import wurde bewusst **nicht** ausgeführt (siehe §4).

---

## 4. Sandbox-Einschränkung (kein vollständiger Ligaabgleich)

Der Sandbox-Key liefert nur eine **feste Stichprobe von 25 Spielern**. Filter
und Pagination sind serverseitig **deaktiviert** (`iter_players(sandbox=True)`
sendet genau ein parameterloses `GET /players`; ein `db`-Slug wird, falls
gesetzt, weiterhin mitgeschickt).

Konsequenz: Ein echter Sandbox-Import würde nur die zufällig in der Stichprobe
enthaltenen, in der DB vorhandenen Spieler (hier Kane/Olise) überschreiben und
damit **Mischdaten** erzeugen. Ein vollständiger Bundesliga-Abgleich ist nur im
**Live-Modus** möglich (siehe §6). Deshalb wird in der Sandbox **kein** echter
Import durchgeführt.

---

## 5. Matching-Strategie & dauerhafte ID-Speicherung

`_match_player` matcht in fester Priorität:

1. **ID** — `PlayerExternalId(source=CMTRACKER, external_id=info.playerid)` → `match_mode='id'`
2. **DOB** — über `date_of_birth`, bei Mehrdeutigkeit Namensähnlichkeit als Tiebreak → `match_mode='dob'`
3. **Name** — vereins-gescoptes Fuzzy-Matching → `match_mode='name'`

**Befund zu Punkt „ID dauerhaft speichern, DOB nur Fallback":** Bereits erfüllt.
Beim **echten** Import schreibt `_apply_row` die externe ID via
`PlayerExternalId.update_or_create(source=CMTRACKER, external_id=info.playerid)`.
Ab dem ersten echten Import greift damit automatisch das **ID-Matching**; DOB
und Name sind nur noch Fallback. Im **Dry-Run** wird die ID bewusst **nicht**
geschrieben — deshalb liefen Kane/Olise dort über DOB.

**Quellen-Konsolidierung (erledigt):** Die DataSource heißt jetzt `CMTRACKER`
(Label „CMTracker"); die Rating-Quelle (`PlayerSourceRating.source`) und die
Import-Läufe (`SourceImportRun.source`) wurden per Datenmigration von
`EA`/`SOFIFA`/`sofifa` auf `CMTRACKER`/`cmtracker` überführt — eine reine
Identitäts-Umbenennung, die Spielstärken bleiben unverändert. Die externe ID
wird aus Rückwärtskompatibilität weiterhin unter dem CSV-/Feldschlüssel
`sofifa_id` geführt, liegt aber unter der DataSource `CMTRACKER`. Sollte
cmtracker künftig eine **eigene**, von der EA-ID abweichende ID führen, bleibt
der Schlüsselname ein reines Implementierungsdetail.

---

## 6. Nächste Aufgabe — Live-Modus-Vorbereitung (Proxy / feste IP)

**Problem:** Live-Keys funktionieren nur von **registrierten IP-Adressen**. Die
Replit-Ausgangs-IP ist nicht stabil → ein vorgelagerter Proxy/Gateway mit
**fester IP** ist nötig.

Geplante Schritte:

1. **Feste IP bereitstellen:** Proxy/Gateway mit statischer Ausgangs-IP
   einrichten und diese IP bei cmtracker für den Live-Key registrieren.
2. **Proxy-Support im Client:** in `CmtrackerClient` HTTP(S)-Proxy-Nutzung
   ergänzen (`requests` `proxies=`), Proxy-URL als Secret hinterlegen.
3. **Live-Key als separates Secret** führen (getrennt vom Sandbox-Key).
4. **Live-Abruf testen** (`--sandbox` weglassen): FC26-DB-Slug `26062400`,
   Filter `--team/--league/--min-overall`, Pagination `--max-pages` prüfen.
5. **Erst-Import (voller Ligaabgleich):** danach greift automatisch das
   ID-Matching (§5); Folgeimporte sind robust gegen Namens-/Vereinswechsel.
6. **Optional:** Auslöse-Button im Creator-Mode (bisher bewusst nur CLI).
