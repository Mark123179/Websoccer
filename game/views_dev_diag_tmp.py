"""TEMPORAER: Empfaengt Client-Diagnosedaten der Sponsoring-Seite (nur DEBUG).
Wird nach der Diagnose wieder geloescht."""
import json
import time

from django.conf import settings
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def dev_diag_report(request):
    if not settings.DEBUG or request.method != 'POST':
        raise Http404()
    try:
        payload = json.loads(request.body.decode('utf-8')[:20000])
    except Exception:
        payload = {'parse_error': True, 'raw': request.body.decode('utf-8', 'replace')[:2000]}
    payload['_ts'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open('.local/diag_reports.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False) + '\n')
    return HttpResponse('ok')
