# Websoccer — Production Deployment (Hetzner)

Diese Anleitung beschreibt den produktiven Betrieb von Websoccer auf einem
eigenen Hetzner-Server mit Docker Compose. Replit bleibt die Entwicklungs- und
Testumgebung, GitHub ist die Source of Truth, Hetzner ist die Produktion.

```
Replit (Entwicklung/Test)  →  GitHub (Source of Truth)  →  Hetzner (Produktion)
```

## Architektur

| Service | Image                | Aufgabe                                            |
|---------|----------------------|----------------------------------------------------|
| web     | (Build aus Dockerfile) | Django + Gunicorn, intern Port 8000              |
| db      | postgres:16          | PostgreSQL, persistentes Volume `pg_data`          |
| redis   | redis:7-alpine       | Cache/Celery-Vorbereitung (in V1 nicht aktiv)      |
| nginx   | nginx:1.27-alpine    | Reverse Proxy auf `web:8000`, liefert Static/Media |

Static- und Media-Dateien liegen in den Volumes `static_data` bzw. `media_data`
und werden von nginx direkt ausgeliefert.

## Voraussetzungen auf dem Server (bereits erfüllt)

- Ubuntu 26.04 LTS, IPv4 `49.13.5.151`
- Docker + Docker Compose V2 installiert
- Git installiert, Repository unter `/opt/websoccer`
- Eine **server-lokale `.env`** unter `/opt/websoccer/.env`

> **Wichtig:** Die `.env` bleibt ausschließlich auf dem Server. Sie wird niemals
> committet und von keinem Skript überschrieben. `deploy.sh` bricht ab, wenn
> keine `.env` vorhanden ist.

## 1. Einmalige Erstkonfiguration

```bash
cd /opt/websoccer

# .env aus der Vorlage anlegen (nur falls noch nicht vorhanden) und befüllen:
cp .env.example .env
nano .env          # echte Werte eintragen (siehe unten)
```

Mindestens zu setzen:

- `SECRET_KEY` — langer Zufallswert. Erzeugen mit:
  ```bash
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
- `DEBUG=False`
- `ALLOWED_HOSTS=49.13.5.151` (plus spätere Domain)
- `COOKIE_SECURE=False` (solange noch kein HTTPS aktiv ist — sonst geht der Login nicht)
- `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (konsistent halten)
- `REDIS_URL=redis://redis:6379/0`
- `REPLIT_OBJECT_STORAGE=0`
- `RUN_MIGRATIONS=0`
- `CMTRACKER_API_KEY`, `OPENAI_API_KEY` (echte Secrets)

## 2. Erststart

```bash
cd /opt/websoccer

# Images bauen
docker compose build

# Datenbank & Redis hochfahren
docker compose up -d db redis

# Datenbank-Migrationen anwenden (manuell — empfohlener Standardweg)
docker compose run --rm web python manage.py migrate

# Static-Dateien einsammeln
docker compose run --rm web python manage.py collectstatic --noinput

# Komplette Anwendung starten (web + nginx)
docker compose up -d

# Logs verfolgen
docker compose logs -f web
```

Danach ist die App unter `http://49.13.5.151/` erreichbar.

Optional vorab prüfen:

```bash
docker compose config                                  # Compose-Datei validieren
docker compose run --rm web python manage.py check     # Django-Checks
docker compose run --rm web python manage.py check --deploy   # Produktions-Checks
```

### Erwartete `check --deploy`-Restwarnungen (V1)

`manage.py check --deploy` läuft fehlerfrei durch (Exit-Code 0), zeigt aber
einige Sicherheitswarnungen. Diese sind in V1 (HTTP, ohne HTTPS, im iframe
einbettbar) bewusst akzeptiert:

| Warnung | Grund | Behebung |
|---------|-------|----------|
| `security.W004` (HSTS) | Nur sinnvoll mit HTTPS | mit HTTPS-Folgeaufgabe |
| `security.W008` (SSL-Redirect) | Kein HTTPS in V1 | mit HTTPS-Folgeaufgabe |
| `security.W012` (SESSION_COOKIE_SECURE) | `COOKIE_SECURE=False` nötig, sonst Login über HTTP unmöglich | auf `True` setzen, sobald HTTPS aktiv ist |
| `security.W016` (CSRF_COOKIE_SECURE) | wie W012 | wie W012 |
| `security.W019` (X_FRAME_OPTIONS) | bewusst `SAMEORIGIN` (Einbettung erlaubt) statt `DENY` | nur ändern, falls Einbettung nicht gewünscht |

Die Warnung `security.W009` (schwacher SECRET_KEY) darf **nicht** auftreten,
wenn in der `.env` ein langer, zufälliger `SECRET_KEY` gesetzt ist.

## 3. Reguläres Re-Deployment

Bequem per Skript:

```bash
cd /opt/websoccer
./deploy.sh
```

`deploy.sh` macht: `.env`-Prüfung → `git pull` → `build` → `migrate` →
`collectstatic` → `up -d`. Es fasst die `.env` nie an.

Manuell entspricht das:

```bash
cd /opt/websoccer
git pull --ff-only
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d
```

## Migrationen: manueller Weg (empfohlen) vs. automatisch

- **Empfohlen (Produktion):** Migrationen **manuell** vor dem Hochfahren des
  Web-Containers ausführen (siehe oben). So laufen größere/breaking
  Schema-Änderungen nie unbeaufsichtigt beim Containerstart.
- **Automatisch (opt-in):** `RUN_MIGRATIONS=1` in der `.env` lässt den
  Entrypoint beim Start automatisch `migrate` + `collectstatic` ausführen.
  Nur für einfache, non-breaking Änderungen sinnvoll. Standard ist `0` (aus).

## Rollback

Auf einen vorherigen Stand zurückgehen:

```bash
cd /opt/websoccer
git log --oneline -n 10            # Ziel-Commit finden
git checkout <commit-sha>          # auf gewünschten Stand wechseln
docker compose build
docker compose up -d
```

> Datenbank-Migrationen sind nicht automatisch reversibel. Vor riskanten
> Deployments immer zuerst ein Backup ziehen (siehe nächster Abschnitt).
> Ein eingespieltes Backup kann mit `pg_restore` wiederhergestellt werden.

## Backups

**PostgreSQL** (vor jedem riskanten Deployment):

```bash
cd /opt/websoccer
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > backup_$(date +%F_%H%M).sql
```

Wiederherstellen:

```bash
cat backup_DATEI.sql | docker compose exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

**Media-Dateien** (Volume `media_data`):

```bash
docker run --rm -v websoccer_media_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/media_$(date +%F).tar.gz -C /data .
```

> Der Volume-Präfix (`websoccer_`) entspricht dem Compose-Projektnamen
> (Verzeichnisname). Mit `docker volume ls` prüfen.

## Nützliche Befehle

```bash
docker compose ps                  # Status aller Services
docker compose logs -f web         # Web-Logs verfolgen
docker compose logs -f nginx       # nginx-Logs
docker compose down                # Stack stoppen (Volumes bleiben erhalten)
docker compose restart web         # nur web neu starten
```

## Offene Folgeaufgaben (nicht Teil von V1)

- **HTTPS / Let's Encrypt:** 443-Server-Block in nginx ergänzen, Certbot/
  Zertifikate mounten, Port 80 → 443 umleiten, danach `COOKIE_SECURE=True`
  setzen.
- **Domain-Setup:** DNS auf `49.13.5.151` zeigen lassen, Domain in
  `ALLOWED_HOSTS` und `CSRF_TRUSTED_ORIGINS` eintragen.
- **Celery:** Worker-Service ergänzen; Redis ist bereits als Broker vorbereitet.
- **CMTracker Live:** Hetzner-IP `49.13.5.151` direkt bei CMTracker für den
  Live-Import registrieren.
- **Datenmigration:** Falls produktive Daten von Replit übernommen werden
  sollen, separat per `pg_dump`/`pg_restore` planen.
