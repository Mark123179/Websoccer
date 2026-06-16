"""HTTP-Client für die geschützte Importer-Token-API.

Authentifizierung ausschließlich über ``Authorization: Bearer <token>``. Das
Lease-Token eines übernommenen Auftrags wird im Header ``X-Lease-Token``
mitgesendet. Bei vorübergehenden Fehlern (429, 5xx, Netzwerk) wird mit
exponentiellem Backoff erneut versucht; ein dauerhaftes Auth-/Lease-Problem
(401, 403) oder ein 503 (Server-API nicht konfiguriert) führt sofort zum Stopp.
"""

import time

import requests


class ApiError(Exception):
    """Fehler bei der Kommunikation mit der Importer-API."""


class FatalApiError(ApiError):
    """Nicht behebbarer Fehler (Auth/Lease/Konfiguration) — sofort abbrechen."""


class NoJobAvailable(Exception):
    """Kein übernehmbarer Auftrag vorhanden (HTTP 204)."""


class ImporterApiClient:
    """Dünner Wrapper um die ``creator-api/import-jobs/``-Endpunkte."""

    def __init__(self, base_url, token, logger,
                 timeout=30, max_retries=4, backoff_base=2):
        self.base = base_url.rstrip('/')
        self.token = token
        self.log = logger
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.lease_token = ''
        self._session = requests.Session()
        self._session.headers['Authorization'] = f'Bearer {token}'
        self._session.headers['Accept'] = 'application/json'

    # ── interne Ausführung mit Backoff ──────────────────────────────────────
    def _url(self, path):
        return f'{self.base}/{path.lstrip("/")}'

    def _headers(self, with_lease):
        headers = {}
        if with_lease and self.lease_token:
            headers['X-Lease-Token'] = self.lease_token
        return headers

    def _request(self, method, path, json_body=None, with_lease=True,
                 allow_204=False):
        url = self._url(path)
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._session.request(
                    method, url, json=json_body,
                    headers=self._headers(with_lease), timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt > self.max_retries:
                    raise ApiError(f'Netzwerkfehler bei {method} {path}: {exc}')
                self._sleep_backoff(attempt, f'Netzwerkfehler: {exc}')
                continue

            if allow_204 and resp.status_code == 204:
                raise NoJobAvailable()

            if resp.status_code in (401, 403, 503):
                raise FatalApiError(self._describe(resp))

            if resp.status_code == 409:
                # Lease-/Statuskonflikt — vom Aufrufer behandelt.
                raise ApiError(self._describe(resp))

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt > self.max_retries:
                    raise ApiError(self._describe(resp))
                self._sleep_backoff(attempt, self._describe(resp),
                                    retry_after=resp.headers.get('Retry-After'))
                continue

            if resp.status_code >= 400:
                raise ApiError(self._describe(resp))

            if not resp.content:
                return {}
            try:
                return resp.json()
            except ValueError:
                return {}

    def _describe(self, resp):
        try:
            body = resp.json()
            detail = body.get('error') or body
        except ValueError:
            detail = (resp.text or '')[:200]
        return f'HTTP {resp.status_code}: {detail}'

    def _sleep_backoff(self, attempt, reason, retry_after=None):
        if retry_after:
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                delay = self.backoff_base ** attempt
        else:
            delay = self.backoff_base ** attempt
        delay = min(delay, 60)
        self.log.warning('Wiederhole nach %.0fs (Versuch %d): %s',
                         delay, attempt, reason)
        time.sleep(delay)

    # ── öffentliche Endpunkte ───────────────────────────────────────────────
    def check_connection(self):
        """Prüft Erreichbarkeit + Token. Gibt den nächsten Auftrag oder None."""
        try:
            return self._request('GET', 'creator-api/import-jobs/next/',
                                  with_lease=False, allow_204=True)
        except NoJobAvailable:
            return None

    def next_job(self):
        """Holt den nächsten übernehmbaren Auftrag oder wirft ``NoJobAvailable``."""
        return self._request('GET', 'creator-api/import-jobs/next/',
                             with_lease=False, allow_204=True)

    def claim_job(self, job_id):
        data = self._request(
            'POST', f'creator-api/import-jobs/{job_id}/claim/', with_lease=False)
        self.lease_token = data.get('lease_token', '')
        return data

    def heartbeat(self, job_id):
        return self._request('POST', f'creator-api/import-jobs/{job_id}/heartbeat/')

    def progress(self, job_id, current=None, total=None, step=None):
        body = {}
        if current is not None:
            body['progress_current'] = current
        if total is not None:
            body['progress_total'] = total
        if step is not None:
            body['current_step'] = step
        return self._request(
            'POST', f'creator-api/import-jobs/{job_id}/progress/', json_body=body)

    def send_candidate(self, job_id, candidate):
        return self._request(
            'POST', f'creator-api/import-jobs/{job_id}/candidates/',
            json_body={'candidate': candidate})

    def complete(self, job_id):
        return self._request('POST', f'creator-api/import-jobs/{job_id}/complete/')

    def fail(self, job_id, error):
        return self._request(
            'POST', f'creator-api/import-jobs/{job_id}/fail/',
            json_body={'error': str(error)[:2000]})
