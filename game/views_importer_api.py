"""Token-geschützte JSON-API für den lokalen Vereins-/Spielerimporter (Spec §28).

Reine Django-``JsonResponse``-Views (kein DRF). Authentifizierung ausschließlich
über ``Authorization: Bearer <CFM_IMPORTER_TOKEN>``. CSRF ist NUR auf diesen
Endpunkten deaktiviert; die Creator-Weboberfläche bleibt CSRF-geschützt.

Sicherheits-Härtung (Spec §38):
    * Token aus Umgebungsvariable, nie im Repo/Log, konstant-zeit-Vergleich.
    * Payload-Größenlimit, Rate-Limit, ID-Validierung.
    * Serverseitig fest verdrahtete erlaubte Felder — der Importer darf keine
      beliebigen Modellfelder bestimmen; unbekannte JSON-Schlüssel werden verworfen.
    * Sichere Fehlerausgaben ohne Secrets.

Diese API konsumiert nur die Datenmodelle aus Task „Import-Engine & Datenmodelle";
sie berechnet keine finalen Attribute und führt keinen DB-Import durch.
"""

import hmac
import json
import os
from datetime import timedelta
from functools import wraps

from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import ClubPlayerImportJob, PlayerImportCandidate

# ── Konfiguration ───────────────────────────────────────────────────────────

ENV_TOKEN_KEY = 'CFM_IMPORTER_TOKEN'

# Lease-/Heartbeat-Parameter (Spec §28.2: Heartbeat 30 s, Lease 3 min).
LEASE_DURATION = timedelta(minutes=3)

# Härtung
MAX_PAYLOAD_BYTES = 1_000_000          # 1 MB pro Request
MAX_BATCH_CANDIDATES = 50              # Kandidaten pro Batch-Aufruf
RATE_LIMIT_MAX = 240                   # erlaubte Requests pro Fenster und Client
RATE_LIMIT_WINDOW = 60                 # Sekunden

_CLAIMABLE_STATUSES = (
    ClubPlayerImportJob.STATUS_PENDING,
    ClubPlayerImportJob.STATUS_CLAIMED,
    ClubPlayerImportJob.STATUS_RUNNING,
)


# ── Serverseitig fest verdrahtete erlaubte Felder ───────────────────────────

_ALLOWED_TM = {
    'profile_url', 'display_name', 'first_name', 'last_name', 'date_of_birth',
    'height_cm', 'preferred_foot', 'primary_nationality', 'nationalities',
    'market_value_eur', 'profile_position',
}
_ALLOWED_POSITION_KEYS = {'appearances', 'main_positions', 'secondary_positions'}
_ALLOWED_APPEARANCE = {'source_position', 'mapped_position', 'matches'}
_ALLOWED_CLUB_ASSIGNMENT = {'real_club', 'loaned_from'}
_ALLOWED_CLUB_SUB = {'tm_club_id', 'name', 'url'}
_ALLOWED_RATING = {'id', 'url', 'rating', 'potential', 'attrs'}


def _pick(value, allowed):
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if k in allowed}


def _sanitize_tm(value):
    out = _pick(value, _ALLOWED_TM)
    nats = out.get('nationalities')
    if isinstance(nats, list):
        out['nationalities'] = [str(x)[:60] for x in nats[:10]]
    return out


def _sanitize_positions(value):
    if not isinstance(value, dict):
        return {}
    out = {}
    appearances = value.get('appearances')
    if isinstance(appearances, list):
        out['appearances'] = [
            _pick(a, _ALLOWED_APPEARANCE)
            for a in appearances[:60] if isinstance(a, dict)
        ]
    for key in ('main_positions', 'secondary_positions'):
        seq = value.get(key)
        if isinstance(seq, list):
            out[key] = [str(x)[:10] for x in seq[:20]]
    return out


def _sanitize_club_assignment(value):
    if not isinstance(value, dict):
        return {}
    out = {}
    for key in _ALLOWED_CLUB_ASSIGNMENT:
        sub = value.get(key)
        if isinstance(sub, dict):
            out[key] = _pick(sub, _ALLOWED_CLUB_SUB)
        elif sub is None and key in value:
            out[key] = None
    return out


def _sanitize_rating(value):
    out = _pick(value, _ALLOWED_RATING)
    attrs = out.get('attrs')
    if isinstance(attrs, dict):
        out['attrs'] = {str(k)[:40]: v for k, v in list(attrs.items())[:60]}
    return out


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _json_error(message, status):
    return JsonResponse({'error': message}, status=status)


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def _extract_bearer(request):
    header = request.META.get('HTTP_AUTHORIZATION', '')
    prefix = 'Bearer '
    if header.startswith(prefix):
        return header[len(prefix):].strip()
    return ''


def _check_rate_limit(request):
    key = f'cfm_importer_rl:{_client_ip(request)}'
    try:
        if cache.add(key, 1, RATE_LIMIT_WINDOW):
            return True
        return cache.incr(key) <= RATE_LIMIT_MAX
    except ValueError:
        # Schlüssel zwischen add und incr abgelaufen → neu zählen.
        cache.set(key, 1, RATE_LIMIT_WINDOW)
        return True


def _load_json(request):
    """Liest und validiert den JSON-Body. Gibt (data, error_response) zurück."""
    body = request.body or b''
    if len(body) > MAX_PAYLOAD_BYTES:
        return None, _json_error('Payload zu groß.', 413)
    if not body:
        return {}, None
    try:
        data = json.loads(body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None, _json_error('Ungültiges JSON.', 400)
    if not isinstance(data, dict):
        return None, _json_error('JSON-Objekt erwartet.', 400)
    return data, None


def importer_api(view):
    """CSRF-Ausnahme + Bearer-Token-Prüfung + Rate-/Größenlimit (nur hier)."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        expected = os.environ.get(ENV_TOKEN_KEY, '')
        if not expected:
            return _json_error('Importer-API ist serverseitig nicht konfiguriert.', 503)

        provided = _extract_bearer(request)
        if not provided or not hmac.compare_digest(provided, expected):
            return _json_error('Ungültiger oder fehlender Token.', 401)

        if not _check_rate_limit(request):
            return _json_error('Zu viele Anfragen.', 429)

        content_length = request.META.get('CONTENT_LENGTH') or 0
        try:
            if int(content_length) > MAX_PAYLOAD_BYTES:
                return _json_error('Payload zu groß.', 413)
        except (TypeError, ValueError):
            pass

        return view(request, *args, **kwargs)

    # csrf_exempt-Markierung muss auf der final registrierten Funktion liegen.
    wrapper.csrf_exempt = True
    return wrapper


def _lease_active(job, now):
    return bool(job.lease_expires_at and job.lease_expires_at > now)


def _job_claimable(job, now):
    if job.status == ClubPlayerImportJob.STATUS_PENDING:
        return True
    if job.status in (ClubPlayerImportJob.STATUS_CLAIMED,
                      ClubPlayerImportJob.STATUS_RUNNING):
        return not _lease_active(job, now)
    return False


def _job_payload(job):
    return {
        'id': job.id,
        'tm_club_id': job.tm_club_id,
        'tm_season_id': job.tm_season_id,
        'season_label': job.season_label,
        'status': job.status,
        'progress_current': job.progress_current,
        'progress_total': job.progress_total,
        'ws_club': {'id': job.ws_club_id, 'name': job.ws_club.name},
    }


def _provided_lease_token(request, data):
    token = request.META.get('HTTP_X_LEASE_TOKEN', '').strip()
    if token:
        return token
    return str(data.get('lease_token', '') or '').strip()


def _get_leased_job(request, job_id, data):
    """Lädt den Auftrag mit Zeilensperre und prüft das Lease-Token.

    MUSS innerhalb eines ``transaction.atomic()``-Blocks aufgerufen werden: die
    Zeile wird per ``select_for_update`` gesperrt, damit Token-/Lease-Prüfung und
    der anschließende Schreibvorgang atomar sind. So kann ein veralteter Importer
    nach einer Lease-Übernahme keinen Zustand mehr überschreiben.

    Gibt ``(job, error_response)`` zurück.
    """
    from django.utils import timezone
    now = timezone.now()
    try:
        job = (
            ClubPlayerImportJob.objects
            .select_for_update()
            .select_related('ws_club')
            .get(pk=job_id)
        )
    except ClubPlayerImportJob.DoesNotExist:
        return None, _json_error('Auftrag nicht gefunden.', 404)

    token = _provided_lease_token(request, data)
    if not token or not job.lease_token or not hmac.compare_digest(token, job.lease_token):
        return None, _json_error('Ungültiges oder fehlendes Lease-Token.', 403)
    if not _lease_active(job, now):
        return None, _json_error('Lease abgelaufen — Auftrag erneut übernehmen.', 409)
    return job, None


def _positive_int(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _non_negative_int(value, default=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n >= 0 else default


# ── Endpunkte ───────────────────────────────────────────────────────────────

@importer_api
@require_GET
def importer_next_job(request):
    """Nächster übernehmbarer Auftrag (offen oder mit abgelaufener Lease)."""
    from django.utils import timezone
    now = timezone.now()
    qs = (
        ClubPlayerImportJob.objects
        .filter(status__in=_CLAIMABLE_STATUSES)
        .select_related('ws_club')
        .order_by('created_at')
    )
    for job in qs:
        if _job_claimable(job, now):
            return JsonResponse(_job_payload(job))
    return HttpResponse(status=204)


@importer_api
@require_POST
def importer_claim_job(request, job_id):
    """Übernimmt einen Auftrag exklusiv per zufälligem Lease-Token."""
    from django.utils import timezone
    now = timezone.now()
    with transaction.atomic():
        try:
            job = (
                ClubPlayerImportJob.objects
                .select_for_update()
                .select_related('ws_club')
                .get(pk=job_id)
            )
        except ClubPlayerImportJob.DoesNotExist:
            return _json_error('Auftrag nicht gefunden.', 404)

        if not _job_claimable(job, now):
            return _json_error('Auftrag ist bereits vergeben.', 409)

        job.lease_token = ClubPlayerImportJob.new_lease_token()
        job.status = ClubPlayerImportJob.STATUS_CLAIMED
        job.claimed_at = now
        job.heartbeat_at = now
        job.lease_expires_at = now + LEASE_DURATION
        job.error_message = ''
        job.save(update_fields=[
            'lease_token', 'status', 'claimed_at', 'heartbeat_at',
            'lease_expires_at', 'error_message', 'updated_at',
        ])

    payload = _job_payload(job)
    payload['lease_token'] = job.lease_token
    payload['lease_expires_at'] = job.lease_expires_at.isoformat()
    return JsonResponse(payload)


@importer_api
@require_POST
def importer_heartbeat(request, job_id):
    """Erneuert die Lease des Auftrags."""
    from django.utils import timezone
    data, err = _load_json(request)
    if err:
        return err
    with transaction.atomic():
        job, err = _get_leased_job(request, job_id, data)
        if err:
            return err
        now = timezone.now()
        job.heartbeat_at = now
        job.lease_expires_at = now + LEASE_DURATION
        job.save(update_fields=['heartbeat_at', 'lease_expires_at', 'updated_at'])
    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'lease_expires_at': job.lease_expires_at.isoformat(),
    })


@importer_api
@require_POST
def importer_progress(request, job_id):
    """Aktualisiert Fortschritt und aktuellen Schritt."""
    from django.utils import timezone
    data, err = _load_json(request)
    if err:
        return err
    with transaction.atomic():
        job, err = _get_leased_job(request, job_id, data)
        if err:
            return err

        update_fields = ['updated_at']
        if 'progress_current' in data:
            val = _non_negative_int(data.get('progress_current'))
            if val is None:
                return _json_error('progress_current muss eine nicht-negative Zahl sein.', 400)
            job.progress_current = val
            update_fields.append('progress_current')
        if 'progress_total' in data:
            val = _non_negative_int(data.get('progress_total'))
            if val is None:
                return _json_error('progress_total muss eine nicht-negative Zahl sein.', 400)
            job.progress_total = val
            update_fields.append('progress_total')
        if 'current_step' in data:
            job.current_step = str(data.get('current_step') or '')[:200]
            update_fields.append('current_step')

        if job.status == ClubPlayerImportJob.STATUS_CLAIMED:
            job.status = ClubPlayerImportJob.STATUS_RUNNING
            update_fields.append('status')

        now = timezone.now()
        job.heartbeat_at = now
        job.lease_expires_at = now + LEASE_DURATION
        update_fields += ['heartbeat_at', 'lease_expires_at']

        job.save(update_fields=update_fields)
    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'progress_current': job.progress_current,
        'progress_total': job.progress_total,
        'current_step': job.current_step,
    })


def _store_candidate(job, raw):
    """Speichert einen Kandidaten (Upsert je job+tm_player_id). Gibt (created, error)."""
    tm_player_id = _positive_int(raw.get('tm_player_id'))
    if tm_player_id is None:
        return None, 'tm_player_id fehlt oder ist ungültig.'

    tm_raw = _sanitize_tm(raw.get('tm'))
    club_assignment = _sanitize_club_assignment(raw.get('club_assignment'))
    if club_assignment:
        tm_raw['club_assignment'] = club_assignment

    defaults = {
        'tm_raw': tm_raw,
        'position_raw': _sanitize_positions(raw.get('positions')),
        'fmi_raw': _sanitize_rating(raw.get('fmi')),
        'sofifa_raw': _sanitize_rating(raw.get('sofifa')),
    }
    warnings = raw.get('warnings')
    if isinstance(warnings, list):
        defaults['source_warnings'] = [str(w)[:300] for w in warnings[:50]]
    errors = raw.get('errors')
    if isinstance(errors, list):
        defaults['validation_errors'] = [str(e)[:300] for e in errors[:50]]

    # Upsert: bereits übertragene Kandidaten bleiben bei Wiederaufnahme erhalten;
    # der Status wird bewusst NICHT überschrieben (z. B. ein bereits importierter
    # Kandidat behält seinen Status).
    _, created = PlayerImportCandidate.objects.update_or_create(
        job=job,
        tm_player_id=tm_player_id,
        defaults=defaults,
    )
    return created, None


@importer_api
@require_POST
def importer_candidates(request, job_id):
    """Überträgt einen oder mehrere Spielerkandidaten (Upsert je TM-ID)."""
    from django.utils import timezone
    data, err = _load_json(request)
    if err:
        return err

    if isinstance(data.get('candidates'), list):
        items = data['candidates']
    elif isinstance(data.get('candidate'), dict):
        items = [data['candidate']]
    elif 'tm_player_id' in data:
        items = [data]
    else:
        return _json_error('Kein Kandidat im Payload.', 400)

    if len(items) > MAX_BATCH_CANDIDATES:
        return _json_error(
            f'Zu viele Kandidaten pro Aufruf (max {MAX_BATCH_CANDIDATES}).', 400)

    created_count = 0
    updated_count = 0
    errors = []
    with transaction.atomic():
        job, err = _get_leased_job(request, job_id, data)
        if err:
            return err
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append({'index': index, 'error': 'Kandidat ist kein Objekt.'})
                continue
            created, item_error = _store_candidate(job, item)
            if item_error:
                errors.append({'index': index, 'error': item_error})
            elif created:
                created_count += 1
            else:
                updated_count += 1

        now = timezone.now()
        update_fields = ['heartbeat_at', 'lease_expires_at', 'updated_at']
        job.heartbeat_at = now
        job.lease_expires_at = now + LEASE_DURATION
        if job.status == ClubPlayerImportJob.STATUS_CLAIMED:
            job.status = ClubPlayerImportJob.STATUS_RUNNING
            update_fields.append('status')
        job.save(update_fields=update_fields)

    return JsonResponse({
        'id': job.id,
        'created': created_count,
        'updated': updated_count,
        'errors': errors,
        'total_candidates': job.candidates.count(),
    })


@importer_api
@require_POST
def importer_complete(request, job_id):
    """Markiert den Auftrag als abgeschlossen (zur Kontrolle bereit)."""
    from django.utils import timezone
    data, err = _load_json(request)
    if err:
        return err
    with transaction.atomic():
        job, err = _get_leased_job(request, job_id, data)
        if err:
            return err
        now = timezone.now()
        job.status = ClubPlayerImportJob.STATUS_REVIEW
        job.heartbeat_at = now
        job.current_step = 'Übertragung abgeschlossen'
        job.lease_token = ''
        job.lease_expires_at = None
        job.save(update_fields=[
            'status', 'heartbeat_at', 'current_step',
            'lease_token', 'lease_expires_at', 'updated_at',
        ])
    return JsonResponse({
        'id': job.id,
        'status': job.status,
        'total_candidates': job.candidates.count(),
    })


@importer_api
@require_POST
def importer_fail(request, job_id):
    """Markiert den Auftrag als fehlgeschlagen und gibt die Lease frei."""
    data, err = _load_json(request)
    if err:
        return err
    with transaction.atomic():
        job, err = _get_leased_job(request, job_id, data)
        if err:
            return err
        job.status = ClubPlayerImportJob.STATUS_FAILED
        job.error_message = str(data.get('error') or '')[:2000]
        job.lease_token = ''
        job.lease_expires_at = None
        job.save(update_fields=[
            'status', 'error_message', 'lease_token', 'lease_expires_at', 'updated_at',
        ])
    return JsonResponse({'id': job.id, 'status': job.status})
