"""Isolated N46 test database: never connects to public or import_pilot."""
from .settings import *

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/ws-package-tests.sqlite3"}}
MIGRATION_MODULES = {"game": None, "showauction": None, "stadium_editor": None}
IMPORT_PACKAGE_MODE = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
ALLOWED_HOSTS = ["*"]
