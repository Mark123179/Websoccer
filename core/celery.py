"""Celery-App für Websoccer.

Broker und Result-Backend kommen aus ``REDIS_URL`` (siehe core/settings.py,
Einstellungen mit Präfix ``CELERY_``). In Produktion laufen Worker und
Beat-Scheduler als eigene Compose-Services (``celeryworker`` / ``celerybeat``)
auf demselben Image wie ``web``.

Die App wird in core/__init__.py importiert, damit sie beim Django-Start
verfügbar ist und ``@shared_task``-Tasks korrekt registriert werden.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('websoccer')

# Konfiguration aus den Django-Settings lesen (alle Keys mit Präfix CELERY_).
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tasks in allen INSTALLED_APPS automatisch finden (z. B. game/tasks.py).
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Mini-Task zum manuellen Prüfen der Worker-Anbindung."""
    print(f'Celery debug_task ok: {self.request!r}')
