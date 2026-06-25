#!/usr/bin/env bash
# =============================================================
# Websoccer — Hetzner deploy helper
#
# Pulls the latest code, rebuilds the image, runs migrations and
# collectstatic MANUALLY (the safe production path), then (re)starts
# the stack.
#
# This script NEVER creates or overwrites .env. It only checks that a
# server-local .env exists and aborts otherwise.
#
# Usage (on the server, in /opt/websoccer):
#   ./deploy.sh
# =============================================================
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "ERROR: .env not found in $(pwd)."
    echo "Create it once from the template:  cp .env.example .env  (then fill in real values)."
    echo "Aborting — refusing to deploy without a configured .env."
    exit 1
fi

echo "==> Pulling latest code from GitHub"
git pull --ff-only

echo "==> Building images"
docker compose build

echo "==> Starting database & redis"
docker compose up -d db redis

echo "==> Applying database migrations"
docker compose run --rm web python manage.py migrate --noinput

echo "==> Collecting static files"
docker compose run --rm web python manage.py collectstatic --noinput

# HTTPS guard — nginx terminates TLS and needs a certificate to start. Refuse to
# (re)create the stack without one, so a premature deploy never crash-loops nginx
# and takes a running site down. Issue certs once with ./init-letsencrypt.sh.
DOMAIN="$(sed -n 's/^DOMAIN=//p' .env | head -n1 | tr -d ' "\r')"
if [ -z "$DOMAIN" ]; then
    echo "ERROR: DOMAIN is not set in .env — HTTPS requires a real domain."
    echo "Set DOMAIN and CERTBOT_EMAIL, then run ./init-letsencrypt.sh once."
    exit 1
fi
if ! docker compose run --rm --entrypoint sh certbot \
        -c "test -s /etc/letsencrypt/live/$DOMAIN/fullchain.pem" >/dev/null 2>&1; then
    echo "ERROR: No TLS certificate found for $DOMAIN."
    echo "Run ./init-letsencrypt.sh once to issue the Let's Encrypt certificate,"
    echo "then re-run ./deploy.sh."
    exit 1
fi

echo "==> Starting the full stack"
docker compose up -d

echo "==> Done. Follow logs with:  docker compose logs -f web"
