"""Stellt sicher, dass die Celery-App beim Django-Start geladen wird.

Damit sind ``@shared_task``-Tasks registriert und der Beat-Schedule findet sie.
"""

from core.celery import app as celery_app

__all__ = ('celery_app',)
