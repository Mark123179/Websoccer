#!/usr/bin/env bash
# =============================================================
# Websoccer — PostgreSQL-Backup (Hetzner-Produktion)
#
# Zieht einen pg_dump der LAUFENDEN Datenbank, komprimiert ihn mit gzip
# und räumt alte Backups auf (behält die neuesten N).
#
# - pg_dump läuft IM db-Container (docker compose exec), daher wird auf
#   dem Host KEIN DB-Passwort benötigt und nichts Geheimes geloggt.
# - Schreibt nach BACKUP_DIR (Standard: <repo>/backups/postgres), das
#   gitignored ist — echte Dumps werden nie committet.
# - Dumps enthalten --clean --if-exists, d. h. der Restore ist wiederholbar.
#
# Verwendung (auf dem Server, in /opt/websoccer):
#   ./scripts/backup_postgres.sh
#
# Einstellbar (Env):
#   BACKUP_DIR    Zielverzeichnis        (Standard: <repo>/backups/postgres)
#   BACKUP_KEEP   Anzahl behalten        (Standard: 14)
# =============================================================
set -euo pipefail

# Repo-Wurzel ermitteln (dieses Skript liegt in <repo>/scripts) und von dort
# arbeiten, damit "docker compose" die docker-compose.yml findet — unabhängig
# vom Aufruf-Verzeichnis (z. B. aus Cron).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Dumps enthalten vollständige Produktivdaten -> nur für den Eigentümer lesbar.
umask 077

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups/postgres}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
if ! [[ "$BACKUP_KEEP" =~ ^[1-9][0-9]*$ ]]; then
    echo "FEHLER: BACKUP_KEEP muss eine positive ganze Zahl sein (war: '$BACKUP_KEEP')." >&2
    exit 1
fi

if [ ! -f .env ]; then
    echo "FEHLER: .env nicht in $ROOT gefunden — DB-Name/-User unbekannt." >&2
    exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "FEHLER: docker nicht im PATH gefunden." >&2
    exit 1
fi

# Nur die NICHT-geheimen DB-Bezeichner aus der .env lesen (niemals das Passwort).
DB_NAME="$(sed -n 's/^POSTGRES_DB=//p' .env | head -n1 | tr -d ' "\r')"
DB_USER="$(sed -n 's/^POSTGRES_USER=//p' .env | head -n1 | tr -d ' "\r')"
if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    echo "FEHLER: POSTGRES_DB / POSTGRES_USER fehlen in der .env." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" 2>/dev/null || true

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/websoccer-$DB_NAME-$TS.sql.gz"
TMP="$OUT.partial"

echo "==> Sichere Datenbank '$DB_NAME' -> $OUT"
# pipefail sorgt dafür, dass ein pg_dump-Fehler die Pipeline (und damit den
# if-Zweig) scheitern lässt, bevor eine unvollständige Datei behalten wird.
if docker compose exec -T db \
        pg_dump --clean --if-exists -U "$DB_USER" -d "$DB_NAME" \
        | gzip -c > "$TMP"; then
    mv "$TMP" "$OUT"
else
    rc=$?
    rm -f "$TMP"
    echo "FEHLER: Backup fehlgeschlagen (Exit $rc); Teil-Datei entfernt." >&2
    exit "$rc"
fi

echo "==> Backup OK ($(du -h "$OUT" | cut -f1))"

# --- Aufbewahrung: neueste BACKUP_KEEP behalten, ältere löschen -------------
echo "==> Räume alte Backups auf (behalte neueste $BACKUP_KEEP)"
mapfile -t _backups < <(ls -1t "$BACKUP_DIR"/websoccer-*.sql.gz 2>/dev/null || true)
if (( ${#_backups[@]} > BACKUP_KEEP )); then
    for old in "${_backups[@]:BACKUP_KEEP}"; do
        echo "    entferne $(basename "$old")"
        rm -f -- "$old"
    done
fi

echo "==> Fertig."
