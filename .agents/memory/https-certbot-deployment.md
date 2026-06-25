---
name: HTTPS/certbot on Docker Compose
description: Gotchas for the Let's Encrypt + nginx HTTPS setup on the Hetzner Compose stack (certbot entrypoint, cert-before-nginx ordering, nginx -t validation).
---

# HTTPS / certbot on the Hetzner Docker Compose stack

## certbot service entrypoint is a renewal loop — one-shot commands need --entrypoint
The `certbot` service's `entrypoint` runs `sh -c "while :; do certbot renew; ...; done"`.
`docker compose run --rm certbot certonly ...` does NOT override an `entrypoint`; it
appends `certonly ...` as args to that loop's `sh -c`, which silently ignores them.
**Rule:** every one-shot certbot invocation must override the entrypoint, e.g.
`docker compose run --rm --entrypoint certbot certbot certonly --webroot ...` and
`docker compose run --rm --entrypoint certbot certbot renew --dry-run`.
The dummy-cert / rm steps use `--entrypoint sh` for the same reason.
**Why:** `run`'s positional args become `command`, not `entrypoint`; a loop entrypoint eats them.

## nginx HTTPS config hard-requires certs — issue them BEFORE any `up -d`
The 443 server block references `/etc/letsencrypt/live/$DOMAIN/{fullchain,privkey}.pem`.
A bare `docker compose up -d` (or recreating nginx) with no cert / empty DOMAIN
crash-loops nginx and takes a running site down.
**How to apply:** first HTTPS start always goes through `init-letsencrypt.sh`
(dummy self-signed -> start nginx -> real certonly -> reload). `deploy.sh` has a
guard that parses DOMAIN from `.env` read-only and aborts before `up -d` if DOMAIN
is unset or `live/$DOMAIN/fullchain.pem` is missing. `deploy.sh` never writes `.env`.

## `nginx -t` resolves upstreams — validate with a resolvable host
Running `nginx -t` in a standalone container fails with `host not found in upstream "web:8000"`
because the compose network isn't present. To validate the rest of the config, render
the template and temporarily swap `server web:8000;` for `server 127.0.0.1:8000;`,
then `nginx -t` passes. The official nginx image renders `*.template` via envsubst on
startup, so `${DOMAIN}` is substituted while runtime vars like `$host` survive.

## ENABLE_HTTPS is opt-in (default off)
`ENABLE_HTTPS` gates `SECURE_PROXY_SSL_HEADER` + `SECURE_SSL_REDIRECT` + HSTS. Default
False keeps Replit dev (runserver behind the iframe proxy) working unchanged. Prod
`manage.py check --deploy` with ENABLE_HTTPS=True + COOKIE_SECURE=True leaves only
W019 (X_FRAME_OPTIONS=SAMEORIGIN kept intentionally).
