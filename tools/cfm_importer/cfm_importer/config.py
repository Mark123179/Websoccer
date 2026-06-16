"""Laden und Validieren der lokalen ``config.json``.

Alle Pfade werden relativ zum Tool-Verzeichnis (``tools/cfm_importer/``)
aufgelöst, damit das Tool unabhängig vom aktuellen Arbeitsverzeichnis und ohne
benutzerspezifische absolute Pfade funktioniert.
"""

import json
import os

# tools/cfm_importer/  (eine Ebene über diesem Paket)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
EXAMPLE_PATH = os.path.join(BASE_DIR, 'config.example.json')

LOG_DIR = os.path.join(BASE_DIR, 'logs')
STATE_DIR = os.path.join(BASE_DIR, 'state')

_REQUIRED = ('api_base_url', 'api_token')
_PLACEHOLDERS = {
    'HIER-DEN-CFM_IMPORTER_TOKEN-EINTRAGEN',
    'https://DEIN-REPL.example.replit.app',
    '',
}


class ConfigError(Exception):
    """Fehlerhafte oder unvollständige Konfiguration."""


class Config:
    """Typisierter Zugriff auf die Konfigurationswerte mit sinnvollen Defaults."""

    def __init__(self, data):
        self._data = data or {}

    @property
    def api_base_url(self):
        return str(self._data['api_base_url']).rstrip('/')

    @property
    def api_token(self):
        return str(self._data['api_token'])

    @property
    def browser_channel(self):
        return str(self._data.get('browser_channel') or 'msedge')

    @property
    def headless(self):
        return bool(self._data.get('headless', False))

    @property
    def user_data_dir(self):
        raw = str(self._data.get('user_data_dir') or 'edge_import_profile')
        if os.path.isabs(raw):
            return raw
        return os.path.join(BASE_DIR, raw)

    @property
    def heartbeat_seconds(self):
        return int(self._data.get('heartbeat_seconds', 25))

    def pause(self, key, default_ms):
        pauses = self._data.get('pauses') or {}
        try:
            return int(pauses.get(key, default_ms)) / 1000.0
        except (TypeError, ValueError):
            return default_ms / 1000.0

    def _request(self, key, default):
        req = self._data.get('request') or {}
        try:
            return type(default)(req.get(key, default))
        except (TypeError, ValueError):
            return default

    @property
    def request_timeout(self):
        return self._request('timeout_seconds', 30)

    @property
    def max_retries(self):
        return self._request('max_retries', 4)

    @property
    def backoff_base(self):
        return self._request('backoff_base_seconds', 2)


def load_config(path=None):
    """Lädt und prüft die Konfiguration. Wirft ``ConfigError`` bei Problemen."""
    path = path or CONFIG_PATH
    if not os.path.exists(path):
        raise ConfigError(
            f'Konfigurationsdatei nicht gefunden: {path}\n'
            'Bitte config.example.json nach config.json kopieren und ausfüllen.'
        )
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (ValueError, OSError) as exc:
        raise ConfigError(f'config.json konnte nicht gelesen werden: {exc}')

    if not isinstance(data, dict):
        raise ConfigError('config.json muss ein JSON-Objekt enthalten.')

    for key in _REQUIRED:
        value = str(data.get(key, '')).strip()
        if not value or value in _PLACEHOLDERS:
            raise ConfigError(
                f'Pflichtfeld "{key}" fehlt oder ist noch der Platzhalterwert. '
                'Bitte config.json vollständig ausfüllen.'
            )

    return Config(data)


def ensure_runtime_dirs():
    """Legt die lokalen Laufzeitverzeichnisse (logs/, state/) an."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
