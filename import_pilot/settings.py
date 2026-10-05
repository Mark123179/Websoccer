"""Standalone technical pilot settings: no game models, signals or Celery app."""
import hashlib
import hmac
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

if not (os.environ.get("REPL_ID") or os.environ.get("REPLIT_DEV_DOMAIN")):
    raise ImproperlyConfigured("Import pilot is restricted to the Replit workspace.")
for _key in ("DATABASE_URL", "PILOT_DB_PASSWORD", "PILOT_SECRET_KEY"):
    if not os.environ.get(_key):
        raise ImproperlyConfigured(f"{_key} is required for the import pilot.")
# Domain separation also works when the supplied pilot inputs are identical.
# Never use the existing application's signing key or unmodified DB password.
SECRET_KEY = hmac.new(
    os.environ["PILOT_SECRET_KEY"].encode(),
    b"websoccer/import-pilot/session-signing/v1",
    hashlib.sha256,
).hexdigest()
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
ROOT_URLCONF = "import_pilot.urls"
INSTALLED_APPS = [
    "import_pilot.apps.ImportPilotConfig",
    "django.contrib.sessions",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

# Reuse only the server/database location, not the maintenance identity.
_database = dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=0)
if _database["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Import pilot requires PostgreSQL.")
if _database.get("PASSWORD") == os.environ["PILOT_DB_PASSWORD"]:
    raise ImproperlyConfigured("Do not reuse the maintenance password for the pilot.")
_database.update(
    ENGINE="import_pilot.db_backend",
    USER="import_pilot_role",
    PASSWORD=os.environ["PILOT_DB_PASSWORD"],
    OPTIONS={"options": "-c search_path=import_pilot"},
)
DATABASES = {"default": _database}
del _database

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "import_pilot_sessionid"
CSRF_COOKIE_NAME = "import_pilot_csrftoken"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = True
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "websoccer-import-pilot",
        "KEY_PREFIX": "import_pilot",
    }
}
MEDIA_ROOT = BASE_DIR / ".local" / "import_pilot" / "uploads"
MEDIA_URL = "/import-pilot-media/"
ORIGINAL_ASSETS_ROOT = os.environ.get(
    "ASSETS_ROOT", str(BASE_DIR / "game" / "static" / "assets")
)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(MEDIA_ROOT), "base_url": MEDIA_URL},
    },
    "original_assets": {
        "BACKEND": "import_pilot.storage.ReadOnlyAssetStorage",
        "OPTIONS": {"location": ORIGINAL_ASSETS_ROOT},
    },
}

# Deliberately disconnected from existing Redis/RabbitMQ and scheduled jobs.
CELERY_BEAT_SCHEDULE = {}
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_DEFAULT_QUEUE = "import_pilot_disabled"
CELERY_IMPORTS = ()
CELERY_INCLUDE = ()
USE_TZ = True
TIME_ZONE = "Europe/Berlin"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
