---
name: Celery production setup
description: How Celery worker/beat are wired into the Docker-Compose prod stack, and the SystemExit gotcha when running management commands programmatically.
---

# Celery in Produktion (Docker Compose)

- Broker + Result-Backend = `REDIS_URL` (Compose-Service `redis`). Settings-Präfix `CELERY_` in `core/settings.py`; `core/celery.py` hält die App, die in `core/__init__.py` importiert wird (Standard-Django-Pattern). Dadurch importiert auch der Dev-runserver Celery — unkritisch, da beim Import keine Broker-Verbindung aufgebaut wird.

## Entrypoint-Override ist Pflicht
Der Dockerfile-`ENTRYPOINT` (`entrypoint.sh`) exect IMMER gunicorn und ignoriert `$@`. Die Celery-Services (`celeryworker`/`celerybeat`) MÜSSEN deshalb `entrypoint: []` + `command: celery ...` setzen — sonst startet statt Celery wieder gunicorn.

## SystemExit-Falle bei Management-Commands
Viele Commands signalisieren ihr Ergebnis über `raise SystemExit(code)` (z. B. `check_city_pins`, `revalidate_clubs` — auch bei Erfolg `code 0`). Wer sie programmatisch via `call_command` ausführt (Celery-Task, View, …) MUSS `SystemExit` abfangen, sonst reißt es den aufrufenden Prozess/Task mit. Referenz: `game/tasks.py` → `run_management_command`.

**Why:** `SystemExit` erbt von `BaseException`, nicht von `Exception` — ein normales `except Exception` fängt es NICHT.

## Beat-Schedule
`CELERY_BEAT_SCHEDULE` in den Settings; Intervall per Env (`CELERY_CITY_PIN_CHECK_INTERVAL`, Sekunden, Standard 86400 = täglich). Der generische Task wird nur über den vertrauenswürdigen, server-seitigen Beat-Schedule getrieben (kein externer Producer; Redis ist von Compose nicht veröffentlicht). Eine Command-Allowlist wird erst nötig, sobald Tasks per UI/API auslösbar werden.
