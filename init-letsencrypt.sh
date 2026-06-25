#!/usr/bin/env bash
# =============================================================
# Websoccer — Let's Encrypt bootstrap (run ONCE on the server)
#
# Solves the chicken-and-egg problem (nginx needs a cert to start, certbot
# needs nginx on port 80 to answer the ACME challenge):
#   1. create a throwaway self-signed cert so nginx can boot,
#   2. start nginx (serves the ACME challenge on port 80),
#   3. delete the throwaway cert,
#   4. request the real Let's Encrypt certificate via the webroot,
#   5. reload nginx with the real certificate.
#
# Afterwards the certbot service renews automatically and nginx reloads
# every 6h to pick up renewed certs (see docker-compose.yml).
#
# Prerequisites:
#   - A real domain whose DNS A-record points to this server
#     (Let's Encrypt cannot issue certificates for a bare IP).
#   - DOMAIN and CERTBOT_EMAIL set in the server-local .env.
#
# Usage (on the server, in /opt/websoccer):
#   ./init-letsencrypt.sh
# =============================================================
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "ERROR: .env not found in $(pwd)."
    echo "Create it first:  cp .env.example .env  (then fill in DOMAIN/CERTBOT_EMAIL)."
    exit 1
fi

# Load DOMAIN / CERTBOT_EMAIL / CERTBOT_STAGING from the server-local .env.
set -a
# shellcheck disable=SC1091
. ./.env
set +a

: "${DOMAIN:?DOMAIN must be set in .env (a real domain pointing to this server)}"
: "${CERTBOT_EMAIL:?CERTBOT_EMAIL must be set in .env}"
staging="${CERTBOT_STAGING:-0}"

cert_path="/etc/letsencrypt/live/$DOMAIN"

echo "==> Building images"
docker compose build

echo "==> Starting database, redis and web"
docker compose up -d db redis web

echo "==> Creating a temporary self-signed certificate so nginx can start"
docker compose run --rm --entrypoint sh certbot -c "\
    apk add --no-cache openssl >/dev/null 2>&1 || true; \
    mkdir -p '$cert_path'; \
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout '$cert_path/privkey.pem' \
        -out '$cert_path/fullchain.pem' \
        -subj '/CN=localhost'"

echo "==> Starting nginx with the temporary certificate"
docker compose up -d nginx

echo "==> Removing the temporary certificate"
docker compose run --rm --entrypoint sh certbot -c "\
    rm -rf '/etc/letsencrypt/live/$DOMAIN' \
           '/etc/letsencrypt/archive/$DOMAIN' \
           '/etc/letsencrypt/renewal/$DOMAIN.conf'"

staging_arg=""
if [ "$staging" != "0" ]; then
    echo "==> Using Let's Encrypt STAGING environment (test certificates)"
    staging_arg="--staging"
fi

echo "==> Requesting the real Let's Encrypt certificate for $DOMAIN"
# Override the entrypoint: the certbot service's default entrypoint is the
# renewal loop, which would ignore these one-shot args.
docker compose run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    --email "$CERTBOT_EMAIL" \
    -d "$DOMAIN" \
    --rsa-key-size 4096 \
    --agree-tos \
    --no-eff-email \
    --non-interactive

echo "==> Reloading nginx with the real certificate"
docker compose exec nginx nginx -s reload

echo "==> Done. HTTPS should now be active at https://$DOMAIN/"
echo "    Remember: set ENABLE_HTTPS=True and COOKIE_SECURE=True in .env,"
echo "    then redeploy (./deploy.sh) to enable Django's HTTPS hardening."
