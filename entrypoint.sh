#!/usr/bin/env bash
# =============================================================
# Websoccer — Container entrypoint (production / Hetzner)
#
# Starts Gunicorn with production defaults.
#
# Migrations & collectstatic are NOT run automatically by default.
# The recommended production workflow is to run them MANUALLY before
# bringing the web container up (see docs/production-deployment.md),
# so that breaking schema changes never run unattended on container start.
#
# Set RUN_MIGRATIONS=1 to opt in to automatic migrate + collectstatic
# at startup (only advisable for simple, non-breaking changes).
# =============================================================
set -euo pipefail

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "[entrypoint] RUN_MIGRATIONS=1 — applying migrations and collecting static files"
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
else
    echo "[entrypoint] RUN_MIGRATIONS not set — skipping migrate/collectstatic (run them manually)"
fi

echo "[entrypoint] Starting Gunicorn on 0.0.0.0:8000"
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile -
