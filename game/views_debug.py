"""Temporary debug-only views (wide-mode audit). Safe to remove afterwards."""
import json
import sys
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
def measure_log(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception as exc:
        payload = {"_parse_error": str(exc), "_raw": request.body[:500].decode("utf-8", "replace")}
    tag = payload.get("_tag", "measure")
    sys.stderr.write("\n===== MEASURE [" + str(tag) + "] =====\n")
    sys.stderr.write(json.dumps(payload, indent=2, ensure_ascii=False))
    sys.stderr.write("\n===== /MEASURE [" + str(tag) + "] =====\n")
    sys.stderr.flush()
    return JsonResponse({"ok": True, "tag": tag})
