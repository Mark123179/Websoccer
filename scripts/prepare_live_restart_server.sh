#!/usr/bin/env bash
# Operator-only backup/restore preparation. Never resets or overwrites live.
set -euo pipefail
umask 077

if [[ $# != 2 || "$1" != "--writers-paused" || "$2" != "--backup-and-verify" ]]; then
    echo "Nur auf dem Hetzner-Server in /opt/websoccer ausführen."
    echo "Erst externe Schreiber pausieren, Beat stoppen, Jobs auslaufen lassen,"
    echo "dann Worker/Web stoppen. Dadurch ist die App vorübergehend nicht erreichbar."
    echo "Danach: bash scripts/prepare_live_restart_server.sh --writers-paused --backup-and-verify"
    echo "Erzeugt private Sicherung und neue Prüf-DB; kein Reset, Import oder Moduswechsel."
    exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
command -v docker >/dev/null
[[ -f .env ]] || { echo "Serverkonfiguration fehlt." >&2; exit 1; }
RUNNING="$(docker compose ps --status running --services)"
for SERVICE in web celeryworker celerybeat; do
    if grep -Fxq "$SERVICE" <<< "$RUNNING"; then
        echo "Abbruch: $SERVICE läuft noch. Keine Sicherung begonnen." >&2
        exit 1
    fi
done
grep -Fxq db <<< "$RUNNING" || { echo "Datenbankdienst läuft nicht." >&2; exit 1; }

# Deliberately fixed outside the repository; no reusable directory is overwritten.
BASE="${WS_PRIVATE_BACKUP_ROOT:-/opt/private-backups}"
BASE="$(realpath -m "$BASE")"
[[ "$BASE" = /* && "$BASE" != / && "$BASE" != "$ROOT" && "$BASE" != "$ROOT/"* ]] || {
    echo "Private Sicherung braucht einen absoluten Pfad außerhalb des Projekts." >&2
    exit 1
}
mkdir -p "$BASE"
BACKUP="$(mktemp -d "$BASE/live-restart-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")"
chmod 700 "$BACKUP"
CHECK="import_restore_check_$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
printf '%s\n' "$CHECK" > "$BACKUP/check-database-name.txt"
trap 'echo "Abbruch: Sicherungsdateien/Prüf-DB bleiben privat erhalten. Kein Reset. Dienste bleiben gestoppt." >&2' ERR
echo "Private Sicherung: $BACKUP"
echo "Kein automatisches Neustarten von Diensten oder Löschen von Prüfkopien."
df -h "$BASE"

web_python() {
    docker compose run --rm -T --no-deps --entrypoint python \
        -e RUN_MIGRATIONS=0 -e IMPORT_PACKAGE_MODE=0 \
        -e 'PGOPTIONS=-c default_transaction_read_only=on' web "$@"
}

web_python manage.py preview_club_reset > "$BACKUP/live-before.json"
web_python manage.py live_restart_scene_backup > "$BACKUP/scenes-before.json"
docker compose exec -T db sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP/db.dump"
docker compose exec -T db pg_restore --list < "$BACKUP/db.dump" > "$BACKUP/db-contents.txt"

# Use the actual configured container paths, not an assumed /app/assets path.
web_python - > "$BACKUP/asset-paths.json" <<'PY'
import json, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()
from django.conf import settings
from pathlib import Path
roots = {"assets": str(Path(settings.ASSETS_ROOT).resolve()),
         "media": str(Path(settings.MEDIA_ROOT).resolve())}
for root in roots.values():
    if root == "/" or not Path(root).is_dir():
        raise SystemExit("Asset-/Medienwurzel fehlt oder ist unzulässig.")
print(json.dumps(roots))
PY

for KIND in assets media; do
    # The path file contains only public filesystem roots, never environment values.
    docker compose run --rm -T --no-deps --entrypoint python \
        -e RUN_MIGRATIONS=0 \
        -e 'PGOPTIONS=-c default_transaction_read_only=on' \
        web - "$KIND" > "$BACKUP/$KIND.tar.gz" <<'PY'
import os, sys, tarfile
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()
from django.conf import settings
from pathlib import Path
kind = sys.argv[1]
root = Path(settings.ASSETS_ROOT if kind == "assets" else settings.MEDIA_ROOT).resolve()
if root == Path("/") or not root.is_dir():
    raise SystemExit("Asset-/Medienwurzel fehlt oder ist unzulässig.")
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    archive.add(root, arcname=kind)
PY
    tar -tzf "$BACKUP/$KIND.tar.gz" > "$BACKUP/$KIND-contents.txt"
done
cp --preserve=mode .env "$BACKUP/server.env"
chmod 600 "$BACKUP/server.env"
git rev-parse HEAD > "$BACKUP/code-version.txt"

docker compose exec -T db sh -c \
    'createdb -U "$POSTGRES_USER" "$1"' sh "$CHECK"
docker compose exec -T db sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error' sh "$CHECK" < "$BACKUP/db.dump"
web_python manage.py preview_club_reset --restore-check-name "$CHECK" > "$BACKUP/restore-preview.json"
web_python manage.py live_restart_scene_backup --restore-check-name "$CHECK" > "$BACKUP/restore-scenes.json"
web_python manage.py preview_club_reset > "$BACKUP/live-after.json"
web_python manage.py live_restart_scene_backup > "$BACKUP/scenes-after.json"

# Host needs only python3, not Django or server secrets. Runs pure comparisons.
python3 scripts/compare_live_restart_backups.py \
    "$BACKUP/live-before.json" "$BACKUP/live-after.json" \
    "$BACKUP/scenes-before.json" "$BACKUP/scenes-after.json" > "$BACKUP/live-stability.txt"
python3 scripts/compare_live_restart_backups.py \
    "$BACKUP/live-before.json" "$BACKUP/restore-preview.json" \
    "$BACKUP/scenes-before.json" "$BACKUP/restore-scenes.json" > "$BACKUP/restore-check.txt"
(
    cd "$BACKUP"
    sha256sum db.dump assets.tar.gz media.tar.gz server.env \
        live-before.json live-after.json restore-preview.json \
        scenes-before.json scenes-after.json restore-scenes.json \
        code-version.txt check-database-name.txt asset-paths.json \
        live-stability.txt restore-check.txt > checksums.txt
    sha256sum -c checksums.txt > checksum-check.txt
)
trap - ERR
echo "Private Sicherung und DB-Wiederherstellungsvergleich erfolgreich."
echo "Dateiprüfsummen/Archivlesbarkeit geprüft; Dateien noch separat visuell kontrollieren."
echo "Kein Reset, kein Import, keine Live-Freigabe. Dienste bleiben gestoppt."
echo "Prüf-DB und Sicherung bleiben erhalten. Keine privaten Dateien hochladen."
