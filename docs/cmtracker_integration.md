# cmtracker-Integration — CMTracker-Ratings importieren

Technische Dokumentation der cmtracker-Anbindung: vom API-Abruf über das
Abflachen der JSON-Antwort bis zur Übergabe an den bestehenden CMTracker-Importer.
Beschreibt Architektur, Feldmapping, das geprüfte Dry-Run-Ergebnis, die
Sandbox-Einschränkung, die Matching-/ID-Strategie sowie den Live-Ablauf auf dem
Produktionsserver (feste IP).

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
- **CSV-Header (cmtracker_* bevorzugt):** Beide CSV-Importpfade akzeptieren die
  kanonischen `cmtracker_*`-Spaltennamen; die alten `sofifa_*`-Header bleiben
  rückwärtskompatibler Alias. Der eigenständige Importer kennt `cmtracker_id`/
  `cmtracker_url`; die Club-Import-„ready"-CSV bevorzugt `cmtracker_id`/
  `cmtracker_url`/`cmtracker_<attr>` und fällt sonst auf `sofifa_*` zurück.
  Interne Schlüssel/Feldnamen (`sofifa_id`, `sofifa_ratings`) bleiben unverändert.
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

## 6. Live-Modus auf dem Produktionsserver (feste IP)

Seit der HTTPS-Produktivstellung läuft Websoccer auf dem Hetzner-Server
(`/opt/websoccer`) mit der **festen IP `49.13.5.151`**. Damit entfällt der
ursprünglich geplante Proxy: Die feste Server-IP ist selbst die IP, die bei
CMTracker für den Live-Key freigeschaltet wird. Der Live-Import läuft deshalb
**direkt auf dem Server** (im `web`-Container), **nicht** aus der Replit-Dev-
Umgebung.

**Voraussetzungen**

- Produktions-Stack läuft (Docker Compose) und ist über HTTPS erreichbar.
- Der **Live**-`CMTRACKER_API_KEY` liegt ausschließlich in der server-lokalen
  `/opt/websoccer/.env` (gitignored). Nie committen, nie loggen.

**Schritt 1 — IP-Freischaltung (manuell beim CMTracker-Anbieter)**

Die feste Hetzner-IP `49.13.5.151` im CMTracker-Konto für den Live-Key
registrieren/freischalten. Verifizieren mit einem einfachen Abruf **vom Server**:

```bash
docker compose run --rm web python manage.py import_cmtracker --list-dbs
```

Läuft das ohne `401/403` durch, ist die IP freigeschaltet.

> **Erwartetes Verhalten:** Von **nicht** registrierten IP-Adressen (z. B. der
> Replit-Dev-Umgebung) antwortet die API bewusst mit **HTTP 401** — das ist
> kein Bug, sondern der IP-Schutz des Live-Keys. Ein Live-Test ist daher nur
> auf dem Server möglich.

**Schritt 2 — Kontrollierter Probelauf (Dry-Run auf dem Server)**

Klein und gefiltert starten, damit nichts geschrieben wird und der Umfang
überschaubar bleibt (valide Liga-/Team-IDs liefert `--list-dbs`):

```bash
docker compose run --rm web python manage.py import_cmtracker \
    --dry-run --league <cmtracker-liga-id> --max-pages 1
```

Erwartung: Bilanz mit gematchten Spielern, `0 Fehler`, **keine** DB-Schreibaktion.

**Schritt 3 — Echter Live-Import (schreibt in die DB)**

`--sandbox` und `--dry-run` weglassen. Für den ersten echten Lauf weiterhin
gezielt filtern (`--league`/`--team`) bzw. `--min-overall`/`--max-pages` setzen,
statt ungefiltert die komplette FC-DB zu ziehen (Sicherheits-Cap: 500 Seiten):

```bash
docker compose run --rm web python manage.py import_cmtracker \
    --league <cmtracker-liga-id>
```

- **Quelle:** Ratings werden unter `CMTRACKER` geschrieben (§5).
- **IDs:** Beim ersten echten Import persistiert `_apply_row` die externe ID;
  Folgeimporte matchen dann per ID (DOB/Name nur noch Fallback).

**Schritt 4 — Verifikation**

- Bilanz prüfen (`neu / aktualisiert / unverändert / nicht gematcht / Fehler`).
- Stichprobe: Ein bekannter Bundesliga-Spieler (z. B. Harry Kane) trägt
  aktualisierte CMTracker-Ratings.

**Secret-Handling (bestätigt)**

- Der Key wird **ausschließlich** aus `os.environ['CMTRACKER_API_KEY']` gelesen
  (`CmtrackerClient.__init__`).
- Er erscheint **nie** in Logs: Fehlermeldungen nennen nur den Variablennamen,
  der Wert geht ausschließlich in den `X-API-Key`-Header.
- Im Repo steht nur der leere Platzhalter in `.env.example`; `.env`/`.env.*`
  sind gitignored.

**Optional (separate Folgeaufgabe):** wiederkehrende, automatisierte Ausführung
über Celery.
