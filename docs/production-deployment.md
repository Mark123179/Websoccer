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
| redis   | redis:7-alpine       | Celery-Broker + Result-Backend (`REDIS_URL`)       |
| celeryworker | (Build aus Dockerfile) | Celery-Worker, führt Hintergrund-Jobs aus     |
| celerybeat   | (Build aus Dockerfile) | Celery-Beat, plant wiederkehrende Jobs        |
| nginx   | nginx:1.27-alpine    | Reverse Proxy auf `web:8000` (Port 80/443), TLS-Terminierung, Static/Media |
| certbot | certbot/certbot      | Let's-Encrypt-Zertifikate ausstellen & automatisch erneuern |

Static- und Media-Dateien liegen in den Volumes `static_data` bzw. `media_data`
und werden von nginx direkt ausgeliefert. TLS-Zertifikate liegen im Volume
`certbot_certs`, die ACME-Challenge im Volume `certbot_www`.

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
- `COOKIE_SECURE=False` (solange noch kein HTTPS aktiv ist — sonst geht der Login nicht;
  mit HTTPS auf `True`, siehe Abschnitt „HTTPS/TLS aktivieren")
- `DOMAIN`, `CERTBOT_EMAIL`, `ENABLE_HTTPS` — nur für HTTPS nötig (siehe Abschnitt „HTTPS/TLS aktivieren")
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
```

> **Wichtig:** Der nginx-Reverse-Proxy terminiert TLS und benötigt deshalb ein
> Zertifikat, bevor der vollständige Stack startet. Führe beim ersten Start
> direkt **Abschnitt 3 (HTTPS/TLS aktivieren)** aus — `./init-letsencrypt.sh`
> fährt `web` + `nginx` mit einem Zertifikat hoch. `deploy.sh` bricht bewusst
> ab, solange kein Zertifikat vorhanden ist, damit ein laufender Server nicht
> ausfällt — ein nacktes `docker compose up -d` darf vor `./init-letsencrypt.sh`
> nicht verwendet werden (nginx würde ohne Zertifikat crashen).

Logs nach dem Start verfolgen:

```bash
docker compose logs -f web
```

Danach ist die App unter `https://deine-domain.de/` erreichbar; Port 80 leitet
automatisch auf 443 um.

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

> Mit aktiviertem HTTPS (`ENABLE_HTTPS=True` **und** `COOKIE_SECURE=True`)
> verschwinden W004, W008, W012 und W016. Es bleibt nur `security.W019`
> (`X_FRAME_OPTIONS=SAMEORIGIN`, bewusst gewählt, damit die iframe-Einbettung
> erlaubt bleibt).

## 3. HTTPS/TLS aktivieren (Let's Encrypt)

HTTPS wird über nginx (TLS-Terminierung) und Certbot (Zertifikate) abgewickelt.
Die Zertifikate liegen im persistenten Volume `certbot_certs`, die
ACME-Challenge im Volume `certbot_www`.

### Voraussetzungen

- Eine **echte Domain**, deren DNS-A-Record auf `49.13.5.151` zeigt.
  Let's Encrypt stellt **keine** Zertifikate für eine nackte IP aus.
- In der `.env` gesetzt:
  - `DOMAIN=deine-domain.de`
  - `CERTBOT_EMAIL=you@example.com`
  - `ALLOWED_HOSTS=49.13.5.151,deine-domain.de`
  - `CSRF_TRUSTED_ORIGINS=https://deine-domain.de`
  - `CERTBOT_STAGING=1` für die ersten Testläufe (verhindert Rate-Limits),
    danach `0` für das echte Zertifikat.

### Erstausstellung der Zertifikate

```bash
cd /opt/websoccer
chmod +x init-letsencrypt.sh   # einmalig
./init-letsencrypt.sh
```

Das Skript löst das Henne-Ei-Problem (nginx braucht ein Zertifikat zum Start,
Certbot braucht nginx auf Port 80 für die ACME-Challenge): Es legt ein
temporäres Self-signed-Zertifikat an, startet nginx, fordert das echte
Zertifikat an und lädt nginx neu.

> Tipp: Erst mit `CERTBOT_STAGING=1` testen. Klappt alles, `CERTBOT_STAGING=0`
> setzen und das Skript erneut ausführen, um das produktive Zertifikat zu holen.

### Django-HTTPS-Härtung einschalten

Sobald das echte Zertifikat aktiv ist, in der `.env` setzen:

```dotenv
ENABLE_HTTPS=True
COOKIE_SECURE=True
```

und neu ausrollen:

```bash
./deploy.sh
```

`ENABLE_HTTPS=True` aktiviert SSL-Redirect, HSTS und wertet den von nginx
gesetzten `X-Forwarded-Proto`-Header aus (nginx terminiert TLS).
`COOKIE_SECURE=True` sorgt für Secure-Cookies. Danach schließt
`manage.py check --deploy` die Warnungen W004/W008/W012/W016.

### Automatische Erneuerung

- Der **certbot**-Service versucht alle 12 h `certbot renew` (erneuert nur bei
  nahender Ablauffrist).
- Der **nginx**-Service lädt alle 6 h neu, damit erneuerte Zertifikate ohne
  Downtime übernommen werden.

Erneuerung testen, ohne ein Zertifikat zu verbrauchen:

```bash
docker compose run --rm --entrypoint certbot certbot renew --dry-run
```

## 4. Reguläres Re-Deployment

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

## Hintergrund-Jobs (Celery-Worker & Beat)

Wiederkehrende Aufgaben laufen über **Celery** auf dem vorhandenen
Redis-Broker. Zwei Services aus `docker-compose.yml`:

- **celeryworker** — führt die Tasks aus (`celery -A core worker`).
- **celerybeat** — plant die wiederkehrenden Jobs (`celery -A core beat`) und
  legt die Task-Nachrichten in Redis ab, von wo der Worker sie abholt.

Beide nutzen dasselbe Image wie `web`, überspringen aber den Gunicorn-Entrypoint
(`entrypoint: []`) und starten direkt Celery. Sie kommen mit
`restart: unless-stopped` automatisch mit dem Stack hoch und erholen sich nach
Abstürzen/Neustarts selbst.

### Start & Stopp

Die Services starten zusammen mit dem übrigen Stack:

```bash
docker compose up -d                 # startet auch celeryworker + celerybeat
docker compose up -d celeryworker celerybeat   # nur die Worker-Dienste
docker compose restart celeryworker celerybeat # nach Code-/Schedule-Änderungen
```

> Nach Änderungen an Tasks (`game/tasks.py`) oder am Zeitplan
> (`CELERY_BEAT_SCHEDULE` in `core/settings.py`) müssen die Images neu gebaut
> (`docker compose build`) und die beiden Dienste neu gestartet werden —
> `deploy.sh` erledigt Build + Hochfahren bereits mit.

### Logs & Überwachung

```bash
docker compose logs -f celeryworker   # Worker-Logs (Task-Ausführung)
docker compose logs -f celerybeat     # Beat-Logs (geplante Auslösungen)

# Lebt der Worker? Pingt alle laufenden Worker:
docker compose exec celeryworker celery -A core inspect ping

# Aktuell laufende bzw. registrierte Tasks und der aktive Zeitplan:
docker compose exec celeryworker celery -A core inspect active
docker compose exec celeryworker celery -A core inspect registered
docker compose exec celeryworker celery -A core inspect scheduled
```

Der Worker selbst hat einen Healthcheck (`celery inspect ping`); `docker compose
ps` zeigt ihn als `healthy`, sobald er Tasks annimmt.

### Geplanter Job (V1)

In V1 ist ein Job eingebunden: der **City-Pin-Check**
(`manage.py check_city_pins`, ein leseseitiger Datenqualitäts-/Golden-Master-
Check). Er läuft standardmäßig **täglich**. Das Intervall ist per Env steuerbar:

```dotenv
# In der .env, Sekunden; Standard 86400 (täglich):
CELERY_CITY_PIN_CHECK_INTERVAL=86400
```

Der Job wird vom generischen Task `game.tasks.run_management_command`
ausgeführt. Dieser fängt das `SystemExit` der Commands ab, loggt deren Ausgabe
und meldet einen Nicht-Null-Exit-Code als fehlgeschlagenen Task (im Worker-Log
und Result-Backend sichtbar).

### Weitere Jobs einbinden

Neue wiederkehrende Jobs werden als Einträge in `CELERY_BEAT_SCHEDULE`
(`core/settings.py`) ergänzt — sie rufen denselben Task mit anderem
Command/Argumenten auf, z. B.:

```python
CELERY_BEAT_SCHEDULE = {
    'datenqualitaet-taeglich': {
        'task': 'game.tasks.run_management_command',
        'schedule': 24 * 60 * 60,
        'args': ('revalidate_clubs',),
    },
}
```

### Task manuell anstoßen (Test/Debug)

```bash
# debug_task (Worker-Anbindung prüfen):
docker compose exec celeryworker \
  celery -A core call core.celery.debug_task

# Ein Management-Command sofort über den Worker laufen lassen:
docker compose exec celeryworker \
  celery -A core call game.tasks.run_management_command --args='["check_city_pins"]'
```

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
docker compose logs -f celeryworker # Celery-Worker-Logs (Hintergrund-Jobs)
docker compose logs -f celerybeat   # Celery-Beat-Logs (geplante Auslösungen)
```

## Offene Folgeaufgaben (nicht Teil von V1)

- **Domain-Setup:** DNS auf `49.13.5.151` zeigen lassen, Domain in
  `ALLOWED_HOSTS` und `CSRF_TRUSTED_ORIGINS` eintragen (Voraussetzung für HTTPS,
  siehe Abschnitt „HTTPS/TLS aktivieren").
- **CMTracker Live:** Hetzner-IP `49.13.5.151` direkt bei CMTracker für den
  Live-Import registrieren.
- **Datenmigration:** Falls produktive Daten von Replit übernommen werden
  sollen, separat per `pg_dump`/`pg_restore` planen.
