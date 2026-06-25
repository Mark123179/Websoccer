"""Celery-Tasks für wiederkehrende Hintergrund-Jobs.

Der zentrale Task :func:`run_management_command` führt ein bestehendes Django-
Management-Command im Worker aus. Welche Commands wann laufen, legt der
Beat-Zeitplan ``CELERY_BEAT_SCHEDULE`` in core/settings.py fest (server-seitige,
vertrauenswürdige Konfiguration — nicht durch Nutzer-Eingaben steuerbar).

Viele Commands signalisieren ihr Ergebnis über ``SystemExit(code)`` (0 = ok,
z. B. ``check_city_pins`` oder ``revalidate_clubs``). Das wird hier abgefangen,
die Ausgabe geloggt und ein Nicht-Null-Exit-Code als Task-Fehler gemeldet, damit
fehlgeschlagene Läufe im Worker-Log und im Result-Backend sichtbar werden.
"""

import io
import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


class ManagementCommandFailed(Exception):
    """Ein per Celery ausgeführtes Management-Command endete mit Fehler-Code."""


def _exit_code(exc: SystemExit) -> int:
    """Normalisiert ``SystemExit.code`` (None/int/str) auf einen int-Exit-Code."""
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    # String- oder sonstiger Code → als Fehler werten.
    return 1


@shared_task(name='game.tasks.run_management_command', bind=True)
def run_management_command(self, command_name, *args, fail_on_exit_code=True):
    """Führt ``manage.py <command_name> <args…>`` im Celery-Worker aus.

    Gibt ein Ergebnis-Dict zurück (Command, Args, Exit-Code, gekürzte Ausgabe).
    Bei ``fail_on_exit_code`` und einem Exit-Code ≠ 0 wird
    :class:`ManagementCommandFailed` geworfen, sodass Celery den Lauf als
    fehlgeschlagen erfasst.
    """
    out = io.StringIO()
    exit_code = 0
    logger.info('Celery startet Management-Command: %s %s', command_name, args)
    try:
        call_command(command_name, *args, stdout=out, stderr=out)
    except SystemExit as exc:
        exit_code = _exit_code(exc)

    output = out.getvalue().strip()
    if output:
        logger.info('Ausgabe von %s:\n%s', command_name, output)
    logger.info(
        'Management-Command %s beendet (Exit-Code %s).', command_name, exit_code
    )

    if fail_on_exit_code and exit_code != 0:
        raise ManagementCommandFailed(
            f'{command_name} endete mit Exit-Code {exit_code}'
        )

    return {
        'command': command_name,
        'args': list(args),
        'exit_code': exit_code,
        'output': output,
    }
