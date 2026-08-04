"""Minimales Benachrichtigungs-System (Glocke im Header).

notify() erzeugt ungebündelte Einzel-Benachrichtigungen für Manager
(Spec Show-Auktion §12). Das Badge in der Kopfzeile zählt ungelesene
Einträge (Context Processor), die Liste unter /benachrichtigungen/
markiert beim Öffnen alles als gelesen.
"""


def notify(manager, title, body='', url=''):
    """Erzeugt eine Benachrichtigung für ein ManagerProfile (None = no-op)."""
    if manager is None:
        return None
    from game.models import Notification
    return Notification.objects.create(
        recipient=manager,
        title=(title or '')[:160],
        body=(body or '')[:240],
        url=(url or '')[:200],
    )


def notify_club(club, title, body='', url=''):
    """Benachrichtigt den Manager eines Vereins (kein Manager = no-op)."""
    manager = getattr(club, 'managed_by', None) if club else None
    if manager is None:
        return None
    return notify(manager, title, body=body, url=url)


def unread_count(manager):
    if manager is None:
        return 0
    from game.models import Notification
    return Notification.objects.filter(recipient=manager, is_read=False).count()
