"""Prove the PostgreSQL destination is our own temporary local cluster."""
import json
from pathlib import Path

from .restart_export import HandoffError


def assert_disposable_postgres(connection, settings):
    config = connection.settings_dict
    socket = Path(config.get("HOST", "")).resolve()
    root = socket.parent
    expected = {
        "database": "ws_restart_verify",
        "user": "ws_restart_check",
        "port": "55439",
        "data_directory": str(root / "data"),
    }
    if (not getattr(settings, "LIVE_RESTART_VERIFY_ONLY", False)
            or not getattr(settings, "LIVE_RESTART_VERIFY_POSTGRES", False)
            or settings.SETTINGS_MODULE != "core.live_restart_postgres_verify_settings"
            or connection.vendor != "postgresql"
            or socket.name != "socket" or root.parent != Path("/tmp")
            or not root.name.startswith("ws-restart-pg-")
            or config.get("NAME") != expected["database"]
            or config.get("USER") != expected["user"]
            or str(config.get("PORT")) != expected["port"]):
        raise HandoffError("PostgreSQL-Prüfung ausschließlich im eigenen lokalen Wegwerf-Cluster erlaubt.")
    try:
        marker = json.loads((root / "verification-only.json").read_text())
    except (OSError, ValueError) as exc:
        raise HandoffError("Prüfcluster-Kennzeichnung fehlt.") from exc
    if marker != expected:
        raise HandoffError("Prüfcluster-Kennzeichnung stimmt nicht.")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT current_database(), current_user,
                   current_setting('data_directory'), current_setting('port'),
                   inet_server_addr()
        """)
        database, user, data_directory, port, server_address = cursor.fetchone()
    if ((database, user, data_directory, port) != (
            expected["database"], expected["user"], expected["data_directory"], expected["port"])
            or server_address is not None):
        raise HandoffError("Tatsächlicher PostgreSQL-Server ist nicht der lokale Prüfcluster.")
