"""Disposable local PostgreSQL oracle. Never derives a DB target from secrets."""
import os
from pathlib import Path

from .package_test_settings import *

_socket = Path(os.environ["WS_RESTART_VERIFY_SOCKET"]).resolve()
if (_socket.name != "socket" or _socket.parent.parent != Path("/tmp")
        or not _socket.parent.name.startswith("ws-restart-pg-")):
    raise RuntimeError("Only a disposable /tmp/ws-restart-pg-*/socket is allowed.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "ws_restart_verify",
        "USER": "ws_restart_check",
        "PASSWORD": "",
        "HOST": str(_socket),
        "PORT": "55439",
        "OPTIONS": {"options": "-c search_path=public"},
        "CONN_MAX_AGE": 0,
    }
}
LIVE_RESTART_VERIFY_ONLY = True
LIVE_RESTART_VERIFY_POSTGRES = True
# Unlike the fast SQLite oracle, exercise the actual PostgreSQL migrations.
MIGRATION_MODULES = {}
