"""Manager-Notizen API — persönlicher Notizblock (Tablet-Overlay).

Notizen sind manager-gebunden (vereinsunabhängig): Auflösung strikt über
``request.user.manager_profile`` — niemals über einen Club-Fallback-Helper.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import ManagerNotes

MAX_BODY_BYTES = 256 * 1024   # 256 KB Gesamt-Payload
MAX_NOTES = 200
MAX_TODOS_PER_NOTE = 100
MAX_TITLE_LEN = 300
MAX_CONTENT_LEN = 20_000
MAX_TODO_TEXT_LEN = 500
MAX_ID_LEN = 64


def _clean_todo(raw):
    if not isinstance(raw, dict):
        return None
    return {
        'id': str(raw.get('id', ''))[:MAX_ID_LEN],
        'text': str(raw.get('text', ''))[:MAX_TODO_TEXT_LEN],
        'done': bool(raw.get('done', False)),
    }


def _clean_note(raw):
    if not isinstance(raw, dict):
        return None
    todos_raw = raw.get('todos', [])
    if not isinstance(todos_raw, list):
        todos_raw = []
    todos = [t for t in (_clean_todo(x) for x in todos_raw[:MAX_TODOS_PER_NOTE]) if t]
    try:
        updated_at = int(raw.get('updatedAt', 0))
    except (TypeError, ValueError):
        updated_at = 0
    return {
        'id': str(raw.get('id', ''))[:MAX_ID_LEN],
        'title': str(raw.get('title', ''))[:MAX_TITLE_LEN],
        'content': str(raw.get('content', ''))[:MAX_CONTENT_LEN],
        'todos': todos,
        'updatedAt': updated_at,
    }


@login_required
def notizen_api(request):
    manager = getattr(request.user, 'manager_profile', None)
    if manager is None:
        return JsonResponse({'error': 'Kein Managerprofil vorhanden.'}, status=403)

    if request.method == 'PUT':
        if len(request.body) > MAX_BODY_BYTES:
            return JsonResponse({'error': 'Payload zu groß.'}, status=413)
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Ungültiges JSON.'}, status=400)
        notes_raw = payload.get('notes') if isinstance(payload, dict) else None
        if not isinstance(notes_raw, list):
            return JsonResponse({'error': '"notes" muss eine Liste sein.'}, status=400)
        notes = [n for n in (_clean_note(x) for x in notes_raw[:MAX_NOTES]) if n]
        obj, _ = ManagerNotes.objects.get_or_create(manager=manager)
        obj.data = notes
        obj.save(update_fields=['data', 'updated_at'])
        return JsonResponse({'ok': True, 'count': len(notes)})

    if request.method == 'GET':
        obj = ManagerNotes.objects.filter(manager=manager).first()
        return JsonResponse({'notes': obj.data if obj else []})

    return JsonResponse({'error': 'Methode nicht erlaubt.'}, status=405)
