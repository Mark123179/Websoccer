#!/usr/bin/env bash
# =============================================================
# Websoccer — Asset-Ordner auf dem Hetzner-Server einrichten
#
# Erstellt /var/www/assets mit der erwarteten Struktur, synct die im
# Repo versionierten Assets (game/static/assets/) dorthin, prüft die
# ASSETS_BASE_URL in der server-lokalen .env und testet nach dem
# nginx-Reload die Live-Auslieferung (200 für vorhandene Dateien,
# 404 für fehlende).
#
# Usage (auf dem Server, in /opt/websoccer):
#   sudo ./scripts/setup_assets_server.sh          # einrichten + testen
#   sudo ./scripts/setup_assets_server.sh --check  # nur Live-Test
#
# Das Skript schreibt NIEMALS die .env — es meldet nur, wenn
# ASSETS_BASE_URL fehlt oder falsch gesetzt ist.
# =============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

ASSETS_DIR="/var/www/assets"
REPO_ASSETS="game/static/assets"
CHECK_ONLY="${1:-}"

# ---- 1. .env prüfen (nur lesen, nie schreiben) ----------------------------
if [ ! -f .env ]; then
    echo "ERROR: .env nicht gefunden in $(pwd). Abbruch."
    exit 1
fi

ASSETS_BASE_URL="$(sed -n 's/^ASSETS_BASE_URL=//p' .env | head -n1 | tr -d ' "\r')"
if [ "$ASSETS_BASE_URL" != "/assets/" ]; then
    echo "WARNUNG: ASSETS_BASE_URL ist nicht '/assets/' (aktuell: '${ASSETS_BASE_URL:-<nicht gesetzt>}')."
    echo "Bitte in .env ergänzen:  ASSETS_BASE_URL=/assets/"
    echo "Danach:  docker compose up -d web   (web-Container neu erstellen)"
    ENV_OK=0
else
    echo "OK: ASSETS_BASE_URL=/assets/ ist in .env gesetzt."
    ENV_OK=1
fi

DOMAIN="$(sed -n 's/^DOMAIN=//p' .env | head -n1 | tr -d ' "\r')"

if [ "$CHECK_ONLY" != "--check" ]; then
    # ---- 2. Ordnerstruktur anlegen ----------------------------------------
    echo "==> Lege Struktur unter $ASSETS_DIR an"
    mkdir -p \
        "$ASSETS_DIR/players" \
        "$ASSETS_DIR/clubs/logos" \
        "$ASSETS_DIR/clubs/stadiums" \
        "$ASSETS_DIR/clubs/cities" \
        "$ASSETS_DIR/clubs/jerseys" \
        "$ASSETS_DIR/trophies" \
        "$ASSETS_DIR/flags" \
        "$ASSETS_DIR/competitions" \
        "$ASSETS_DIR/avatars" \
        "$ASSETS_DIR/backgrounds" \
        "$ASSETS_DIR/icons"

    # ---- 3. Repo-Assets syncen (nur hinzufügen/aktualisieren, nie löschen) --
    if [ -d "$REPO_ASSETS" ]; then
        echo "==> Synce $REPO_ASSETS → $ASSETS_DIR"
        if command -v rsync >/dev/null 2>&1; then
            rsync -av "$REPO_ASSETS/" "$ASSETS_DIR/"
        else
            cp -rv "$REPO_ASSETS/." "$ASSETS_DIR/"
        fi
    else
        echo "Hinweis: $REPO_ASSETS existiert nicht im Repo — überspringe Sync."
    fi

    # ---- 4. Leserechte für nginx (Container liest read-only als non-root) --
    echo "==> Setze Leserechte"
    chmod -R a+rX "$ASSETS_DIR"

    # ---- 5. nginx neu laden, damit der Bind-Mount sicher aktiv ist ---------
    # Nur reloaden, wenn nginx bereits läuft — dieses Skript startet den
    # Stack absichtlich NICHT selbst (das macht deploy.sh mit HTTPS-Guard).
    if [ -n "$(docker compose ps -q nginx 2>/dev/null)" ]; then
        echo "==> Lade nginx neu"
        docker compose exec nginx nginx -s reload
    else
        echo "Hinweis: nginx-Container läuft nicht — Stack ggf. mit ./deploy.sh starten."
    fi
fi

# ---- 6. Live-Smoke-Test ----------------------------------------------------
echo "==> Bestandsübersicht unter $ASSETS_DIR"
if [ ! -d "$ASSETS_DIR" ]; then
    echo "ERROR: $ASSETS_DIR existiert nicht — Skript einmal ohne --check ausführen."
    exit 1
fi
find "$ASSETS_DIR" -type f 2>/dev/null | wc -l | xargs echo "Dateien gesamt:"
ls "$ASSETS_DIR/players" 2>/dev/null | head -3 || true
ls "$ASSETS_DIR/clubs/logos" 2>/dev/null | head -3 || true

if [ -n "$DOMAIN" ]; then
    BASE="https://$DOMAIN/assets"
    echo "==> Live-Test gegen $BASE"
    pass=1
    for path in "clubs/logos/915_club.png" "clubs/logos/907_club.png" "players/face_28049320.png"; do
        if [ -f "$ASSETS_DIR/$path" ]; then
            code="$(curl -sk -o /dev/null -w '%{http_code}' "$BASE/$path")"
            if [ "$code" = "200" ]; then
                echo "  OK  200  /assets/$path"
            else
                echo "  FAIL $code /assets/$path (erwartet 200)"
                pass=0
            fi
        fi
    done
    code="$(curl -sk -o /dev/null -w '%{http_code}' "$BASE/players/face_0000000_missing.png")"
    if [ "$code" = "404" ]; then
        echo "  OK  404  fehlende Datei liefert 404 (Platzhalter-Pfad)"
    else
        echo "  FAIL $code fehlende Datei (erwartet 404)"
        pass=0
    fi
    if [ "$pass" = "1" ] && [ "$ENV_OK" = "1" ]; then
        echo "==> ALLES OK: /assets/-Auslieferung funktioniert."
    else
        echo "==> Es gibt offene Punkte — siehe FAIL/WARNUNG oben."
        exit 1
    fi
else
    echo "Hinweis: DOMAIN nicht in .env gesetzt — Live-Test übersprungen."
fi
