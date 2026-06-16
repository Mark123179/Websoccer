"""Logging mit täglichen Logdateien — ohne Secrets (Token/Cookies).

Eine ``SecretRedactingFilter`` ersetzt den API-Token in jeder Log-Nachricht
durch ``***``. Cookies werden grundsätzlich nicht geloggt.
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler

from . import config


class SecretRedactingFilter(logging.Filter):
    """Maskiert bekannte Geheimnisse in Log-Nachrichten."""

    def __init__(self, secrets):
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 6]

    def filter(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return True
        for secret in self._secrets:
            if secret in msg:
                msg = msg.replace(secret, '***')
                record.msg = msg
                record.args = ()
        return True


def setup_logging(secrets=None, level=logging.INFO):
    """Konfiguriert Konsole + tägliche Logdatei und gibt den Logger zurück."""
    config.ensure_runtime_dirs()
    logger = logging.getLogger('cfm_importer')
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    redactor = SecretRedactingFilter(secrets or [])
    fmt = logging.Formatter(
        '%(asctime)s %(levelname)-7s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(redactor)
    logger.addHandler(console)

    log_file = os.path.join(config.LOG_DIR, 'cfm_importer.log')
    file_handler = TimedRotatingFileHandler(
        log_file, when='midnight', backupCount=30, encoding='utf-8')
    file_handler.suffix = '%Y-%m-%d'
    file_handler.setFormatter(fmt)
    file_handler.addFilter(redactor)
    logger.addHandler(file_handler)

    return logger
