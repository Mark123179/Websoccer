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

echo "==> Starting the full stack"
docker compose up -d

echo "==> Done. Follow logs with:  docker compose logs -f web"
