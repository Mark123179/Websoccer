#!/bin/sh
# Websoccer nginx entrypoint
#
# Selects the correct nginx config and starts the server:
#
#   - Certificate present  →  renders the production HTTPS template via
#                             envsubst and starts nginx in full HTTPS mode.
#   - No certificate yet   →  copies the HTTP-only bootstrap config so nginx
#                             can start, serve the ACME HTTP-01 challenge, and
#                             let init-letsencrypt.sh obtain the first cert.
#
# After a certificate is obtained for the first time, restart the nginx
# container so the entrypoint switches to HTTPS:
#   docker compose restart nginx
set -e

CERT_FILE="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
TEMPLATE="/etc/nginx/templates/default.conf.template"
CONF="/etc/nginx/conf.d/default.conf"
BOOTSTRAP="/etc/nginx/bootstrap.conf"

if [ -n "${DOMAIN}" ] && [ -f "${CERT_FILE}" ]; then
    echo "[nginx] Certificate found — rendering HTTPS config for '${DOMAIN}'"
    # Only substitute ${DOMAIN}; nginx runtime vars ($host etc.) are left as-is.
    envsubst '${DOMAIN}' < "${TEMPLATE}" > "${CONF}"
else
    echo "[nginx] No certificate yet — using HTTP-only bootstrap config"
    cp "${BOOTSTRAP}" "${CONF}"
fi

# Reload every 6 h in the background so renewed certificates are picked up
# without manual intervention.
while :; do
    sleep 6h &
    wait ${!}
    nginx -s reload
done &

exec nginx -g 'daemon off;'
