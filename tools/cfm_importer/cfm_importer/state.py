"""Lokale Wiederaufnahme nach Abbruch.

Pro Auftrag wird eine ``state/job_<id>.json`` geführt, die die bereits
erfolgreich übertragenen TM-Spieler-IDs festhält. Bei einem Neustart werden
diese übersprungen. Die Server-Datenbank bleibt maßgeblich; die lokale Datei
ist nur eine Wiederaufnahmehilfe und enthält keine Geheimnisse.
"""

import json
import os

from . import config


class JobState:
    """Persistenter Fortschritt eines einzelnen Auftrags."""

    def __init__(self, job_id):
        self.job_id = int(job_id)
        self.path = os.path.join(config.STATE_DIR, f'job_{self.job_id}.json')
        self.sent_ids = set()
        self.total = None
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            return
        self.sent_ids = {int(x) for x in data.get('sent_ids', []) if str(x).isdigit()}
        self.total = data.get('total')

    def _save(self):
        config.ensure_runtime_dirs()
        tmp = self.path + '.tmp'
        payload = {
            'job_id': self.job_id,
            'total': self.total,
            'sent_ids': sorted(self.sent_ids),
        }
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def is_sent(self, tm_player_id):
        return int(tm_player_id) in self.sent_ids

    def mark_sent(self, tm_player_id):
        self.sent_ids.add(int(tm_player_id))
        self._save()

    def set_total(self, total):
        self.total = int(total)
        self._save()

    def clear(self):
        """Entfernt die State-Datei (z. B. nach erfolgreichem Abschluss)."""
        try:
            os.remove(self.path)
        except OSError:
            pass
