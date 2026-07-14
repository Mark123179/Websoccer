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
> Deployments immer zuerst ein Backup ziehen (siehe nächster Abschnitt
> „Backups", inkl. Restore-Anleitung).

## Backups

### PostgreSQL — automatisiert (empfohlen)

Das Skript `scripts/backup_postgres.sh` zieht einen `pg_dump` der laufenden
Datenbank, komprimiert ihn mit gzip und räumt alte Backups auf (behält die
neuesten N). Der Dump läuft **im** db-Container (`docker compose exec`), daher
wird kein DB-Passwort auf dem Host benötigt und nichts Geheimes geloggt.

```bash
cd /opt/websoccer
./scripts/backup_postgres.sh
```

- Zielverzeichnis: `/opt/websoccer/backups/postgres` (per `BACKUP_DIR`
  überschreibbar). Liegt unter `backups/` und ist **gitignored** — echte Dumps
  werden nie committet.
- Dateiname mit Zeitstempel: `websoccer-<db>-YYYYmmdd-HHMMSS.sql.gz`.
- Aufbewahrung: standardmäßig die **letzten 14** Backups (per `BACKUP_KEEP`
  überschreibbar). Ältere werden automatisch gelöscht.

**Täglich per Cron** (z. B. 03:30 Uhr) — `crontab -e` auf dem Server:

```cron
30 3 * * * cd /opt/websoccer && mkdir -p backups/postgres && ./scripts/backup_postgres.sh >> backups/postgres/backup.log 2>&1
```

**Oder als systemd-Timer** (Dateien unter `/etc/systemd/system/`):

```ini
# websoccer-backup.service
[Unit]
Description=Websoccer PostgreSQL backup
[Service]
Type=oneshot
WorkingDirectory=/opt/websoccer
ExecStart=/opt/websoccer/scripts/backup_postgres.sh

# websoccer-backup.timer
[Unit]
Description=Daily Websoccer PostgreSQL backup
[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
[Install]
WantedBy=timers.target
```

Aktivieren: `systemctl enable --now websoccer-backup.timer`.

### PostgreSQL — Restore

> Achtung: Der Restore überschreibt die aktuelle Datenbank. Vorher idealerweise
> Web-/Celery-Dienste stoppen, damit währenddessen nichts schreibt.

```bash
cd /opt/websoccer
# DB-Name/-User (nicht geheim) aus der .env in die Host-Shell laden:
export POSTGRES_USER="$(sed -n 's/^POSTGRES_USER=//p' .env | tr -d ' "')"
export POSTGRES_DB="$(sed -n 's/^POSTGRES_DB=//p' .env | tr -d ' "')"
docker compose stop web celeryworker celerybeat          # Schreibzugriffe pausieren
gunzip -c backups/postgres/websoccer-<db>-<ts>.sql.gz \
  | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose start web celeryworker celerybeat
```

Die Dumps enthalten `--clean --if-exists`, d. h. bestehende Objekte werden vor
dem Wiedereinspielen sauber entfernt — der Restore ist damit wiederholbar.

### PostgreSQL — manueller Einzel-Dump (ad hoc)

```bash
cd /opt/websoccer
export POSTGRES_USER="$(sed -n 's/^POSTGRES_USER=//p' .env | tr -d ' "')"
export POSTGRES_DB="$(sed -n 's/^POSTGRES_DB=//p' .env | tr -d ' "')"
mkdir -p backups/postgres
docker compose exec -T db pg_dump --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip > backups/postgres/manual_$(date +%F_%H%M).sql.gz
```

**Media-Dateien** (Volume `media_data`):

```bash
docker run --rm -v websoccer_media_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/media_$(date +%F).tar.gz -C /data .
```

> Der Volume-Präfix (`websoccer_`) entspricht dem Compose-Projektnamen
> (Verzeichnisname). Mit `docker volume ls` prüfen.

## Bild-Assets (`/assets/`) auf dem Server

Bild-Assets (Spielergesichter, Club-Logos, Trophäen …) liegen NICHT im
Docker-Image, sondern auf dem Host unter `/var/www/assets` und werden von
nginx direkt serviert (Bind-Mount `/var/www/assets:/app/assets:ro`,
Location `/assets/` in `nginx/default.conf.template`). Fehlende Dateien
liefern 404, die UI zeigt dann automatisch den Platzhalter.

Erwartete Struktur (siehe auch `DATEN_UND_ASSETS.md`):

```text
/var/www/assets/
  players/face_<player_fm_inside_id>.png
  clubs/logos/<club_fm_inside_id>_club.png
  clubs/stadiums/  clubs/cities/  clubs/jerseys/
  trophies/<trophy_asset_id>.png
  flags/  competitions/  avatars/  backgrounds/  icons/
```

Einrichtung + Live-Test in einem Schritt (auf dem Server, in `/opt/websoccer`):

```bash
sudo ./scripts/setup_assets_server.sh
```

Das Skript:

1. prüft, ob `ASSETS_BASE_URL=/assets/` in der server-lokalen `.env` steht
   (es schreibt die `.env` nie selbst — fehlt der Eintrag, ergänzen und
   danach `docker compose up -d web` ausführen),
2. legt die Ordnerstruktur unter `/var/www/assets` an,
3. synct die im Repo versionierten Assets aus `game/static/assets/` dorthin
   (nur hinzufügen/aktualisieren, nie löschen — zusätzliche, nur lokal
   vorhandene Bilder auf dem Server bleiben erhalten),
4. setzt Leserechte und lädt nginx neu,
5. testet live: vorhandene Dateien → HTTP 200, fehlende Datei → HTTP 404.

Nur den Live-Test (ohne Änderungen) ausführen:

```bash
./scripts/setup_assets_server.sh --check
```

Weitere Assets (z. B. neue Spielergesichter aus dem lokalen
`Images/`-Bestand) können jederzeit per `rsync`/`scp` direkt nach
`/var/www/assets/...` kopiert werden — ein Deploy oder Container-Neustart
ist dafür nicht nötig, nginx liest den Host-Ordner direkt.

```bash
# Beispiel vom lokalen Rechner aus:
rsync -av Images/Players/face_*.png root@49.13.5.151:/var/www/assets/players/
```

## Nützliche Befehle

```bash
docker compose ps                  # Status aller Services
docker compose logs -f web         # Web-Logs verfolgen
docker compose logs -f nginx       # nginx-Logs
docker compose down                # Stack stoppen (Volumes bleiben erhalten)
docker compose restart web         # nur web neu starten
docker compose logs -f celeryworker # Celery-Worker-Logs (Hintergrund-Jobs)
docker compose logs -f celerybeat   # Celery-Beat-Logs (geplante Auslösungen)
./scripts/backup_postgres.sh        # DB-Backup ziehen (gzip + Rotation)
./scripts/setup_assets_server.sh    # /var/www/assets einrichten + Live-Test
```

## Offene Folgeaufgaben (nicht Teil von V1)

- **Domain-Setup:** DNS auf `49.13.5.151` zeigen lassen, Domain in
  `ALLOWED_HOSTS` und `CSRF_TRUSTED_ORIGINS` eintragen (Voraussetzung für HTTPS,
  siehe Abschnitt „HTTPS/TLS aktivieren").
- **CMTracker Live:** Hetzner-IP `49.13.5.151` direkt bei CMTracker für den
  Live-Import registrieren.
- **Datenmigration:** Falls produktive Daten von Replit übernommen werden
  sollen, separat per `pg_dump`/`pg_restore` planen.
