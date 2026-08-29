# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Zuerst lesen: `.agents/memory/`

Der wichtigste Kontext dieses Repos steht nicht im Code, sondern in **`.agents/memory/`** — rund 90 Einträge mit den durable Architektur-, Balancing- und Design-Entscheidungen samt der Fallen, die dahinter stecken. `.agents/memory/MEMORY.md` ist der Index mit einer Zusammenfassung pro Eintrag.

**Vor jeder Änderung an Match-Engine, Finanzen, Import-Pipeline, Scouting oder Layout den passenden Memory-Eintrag lesen.** Viele Bugs in diesem Projekt waren Wiederholungen bereits dokumentierter Fallen (Bayern-Fallback, Decimal-Phantomdiffs, CSS-Cache-Bust, `game/tests.py`-Schatten).

Ergänzende Kontextdokumente im Root: `PROJEKTKONTEXT.md` (Überblick), `SPIELSTAERKEMODELL.md` (Stärkeberechnung), `DATEN_UND_ASSETS.md` (Asset-ID-Mapping), `DESIGN.md` (Design-Tokens und -Regeln), `docs/` (Kalibrierung, CMTracker, Deployment).

Projektsprache ist Deutsch: Doku, Code-Kommentare und UI-Texte auf Deutsch. Commit-Messages sind gemischt; inhaltliche Änderungen referenzieren oft `Task #NNN`.

## Befehle

Es gibt **keinen konfigurierten Linter/Formatter** (kein ruff, flake8, black, pre-commit). `python manage.py check` ist der Smoke-Test.

```bash
# Dev-Server (Port 5000, nicht 8000)
python manage.py runserver 0.0.0.0:5000

# Tests — game/tests ist ein Package, game/tests.py wird ignoriert (s. u.)
python manage.py test game.tests --verbosity=0 --keepdb
python manage.py test game.tests.test_cup_service                 # eine Datei
python manage.py test game.tests.test_cup_service.RoundCodesTests   # eine Klasse

# Match-Engine-Regression (Pflicht nach Engine-Änderungen)
bash scripts/run_regression_v3.sh --seasons 20   # ohne Flag: 100 Saisons
python manage.py fast_season --seasons 50        # kanonische Freeze-Validierung

# Datenqualität + Security
python manage.py revalidate_clubs --strict
bash scripts/audit_deps.sh                       # pip-audit, exit 1 bei CVE/veraltet

# Spieltag simulieren
python manage.py play_matchday --league <id> --matchday <n> [--season S] [--force] [--dry-run]

# Celery (Prod: eigene Compose-Services)
celery -A core worker --loglevel=info --concurrency=2
celery -A core beat --loglevel=info
```

Ohne `DATABASE_URL` fällt Django auf lokales SQLite zurück — mit Supabase-Postgres verhält sich das Verhalten teils anders (Decimal, Locking). Env-Keys: `.env.example`.

Deployment läuft über `docker-compose.yml` (web/db/redis/celeryworker/celerybeat/nginx/certbot), Details in `docs/production-deployment.md`. `scripts/post-merge.sh` migriert, sammelt Static und legt einen 10-Saisons-Regressions-Snapshot an.

## Architektur

Zwei Django-Apps: `core/` (Settings, URLs, Celery-App) und `game/` (praktisch die gesamte Spiellogik), dazu `showauction/` als eigenständige Auktions-App.

`game/` ist flach organisiert, aber die Größe täuscht — `views.py`, `models.py` und `views_creator.py` liegen jeweils im Hunderter-KB-Bereich. Die eigentlichen Subsysteme:

**Match-Simulation.** `match_engine.py` (`simulate_match()`, `simulate_ko_match()`) ist der Kern. `tactic_compiler.py` ist bewusst eine *standalone Kopie* ohne ORM-Zugriff; die Brücke ist `_build_team_dict()`. Drumherum: `strength_engine.py`/`strength_service.py` (Spielerstärken), `tactics.py` + `default_tactics.py` (Taktikeingabe), `match_readiness.py` (Aufstellungs-Vorbereitung), `matchday_xi.py` (automatische Elf, mit hartem Backtracking-Limit), `ticker_commentary.py` (deterministischer Live-Ticker via Seed), `weather_service.py`, `referee_service.py`.

**Saisonbetrieb.** `season_service.py` ist die kanonische Schnittstelle (`simulate_matchday()`, `close_matchday()`, `write_simulated_match_stats()`); `LeagueSeasonState` ist die State Machine pro Liga+Saison. Dazu `schedule_generator.py`, `cup_service.py`. **Der Saisonwechsel ist manuell**, nicht automatisch — Reihenfolge in `.agents/memory/season-rollover-manual.md`.

**Wirtschaft.** Das Paket `game/economy/` (Booking, Transfers, Sponsoren, Stadion, Insolvenz, KI-Käufer, Kalibrierung) ist die Wahrheit; `finance.py` ist der Legacy-Wrapper. Alle Geldbewegungen laufen über `economy/booking.py::book()`.

**Datenimport.** Mehrere Pfade, die leicht verwechselt werden: `game/club_import/` ist die Creator-Mode-Engine (CSV/ZIP, Vollanlage vs. Aktualisierung), `sofifa_import_service.py` ist der produktive SoFIFA-Pfad (`sofifa_import.py` ist ein toter Zwilling), `cmtracker_api.py` bridged die CMTracker-API über CSV in denselben Importer, `api_football.py` liefert Formdaten. Live-Scraping ist serverseitig nicht möglich (Cloudflare) — nur der lokale Importer scrapt.

**Assets.** Alle Vereins- und Spielerbilder sind über `fm_inside_id` verschlüsselt, nicht über Django-PKs. `asset_urls.py` liest `ASSETS_BASE_URL` **zur Laufzeit** über `_base()`; Modul-Level-Konstanten würden die Env-Variable verpassen. `object_storage_backend.py` ist das Replit-Object-Storage-STORAGES-Backend.

**Hintergrundjobs.** `game/tasks.py` + `core/celery.py`. Tasks rufen meist Management-Commands über `call_command` — die werfen `SystemExit` auch im Erfolgsfall und müssen abgefangen werden.

**Management-Commands** sind das Hauptwerkzeug für Betrieb und Datenpflege: ~90 Stück unter `game/management/commands/`, von `play_matchday` und `fast_season` über die `finance_*`-Reihe bis zu diversen `seed_*`/`backfill_*`/`import_*`-Jobs. Bei Datenlücken in der UI zuerst prüfen, ob ein idempotenter Seed-Command schlicht nie gelaufen ist — das war schon mehrfach die Ursache für vermeintliche Template-Bugs.

**Frontend** sind Django-Templates plus handgeschriebenes CSS, kein JS-Framework. Layout-Grenze ist 1440×900 als Golden Master.

## Harte Regeln

- **Match-Engine-Freeze (seit 2026-06-12).** Konstanten, Formeln und Modifikatoren in `match_engine.py` und `tactic_compiler.py` sind eingefroren und gegen eine abgenommene 50-Saisons-Baseline validiert. Änderungen nur mit Abweichungs-Evidenz aus ≥50 Saisons **und** expliziter Nutzer-Freigabe, danach erneute Validierung. Details und Baseline-Werte: `.agents/memory/match-engine-v2-freeze.md`. Dasselbe gilt für die eingefrorenen `SET_PIECE_*`- und Freshness-V1-Konstanten.
- **Geld nur über `book()`.** Nie `club.budget` direkt mutieren. `log_club_transaction()` ist ein Legacy-Wrapper, der mitbucht. Geldbewegende Pfade brauchen Locks in fester Reihenfolge (Verein sortiert, dann Spielerzeile) gegen Doppelkauf-Races.
- **Neue Tests nach `game/tests/test_*.py`.** `game/tests.py` existiert noch, wird aber vom gleichnamigen Package überlagert und komplett ignoriert — Edits dort gehen ins Leere.
- **Cache-Bust bei jedem Template-Asset-Edit.** `?v=` in der Template-Referenz hochzählen, CSS und gepaartes JS immer zusammen.
- **Ökonomie-Änderungen gegen die Balancing-Checkliste prüfen** (`.agents/memory/economy-design-principles.md`), bevor Geld-Features gebaut werden.
- **Werte nie erfinden.** Fehlende Daten bleiben `NULL`, nicht `0` — die Import-Pipeline unterscheidet das bewusst.
