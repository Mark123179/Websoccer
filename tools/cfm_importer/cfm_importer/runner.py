"""Ablaufsteuerung des Importers.

Flow: Verbindung prüfen → offenen Auftrag holen → Rückfrage → Auftrag claimen →
Kaderseite öffnen → alle Spieler sammeln → je Spieler TM/FMInside
erfassen und an die API übertragen → Auftrag abschließen.

SoFIFA-/EA-Ratings (Stärke/Potenzial/Attribute) werden hier **nicht** live
ausgelesen — SoFIFA und cmtracker.net sind Cloudflare-geschützt und serverseitig
nicht verifizierbar. Diese Werte kommen stattdessen zuverlässig über den
CMTracker-/SoFIFA-CSV-Export (``game/sofifa_import.py``) in die Datenbank.

Robustheit:
    * Heartbeats halten die Lease während langer Schritte aufrecht.
    * Einzelne Spielerfehler überspringen den Spieler mit konkreter Meldung.
    * Blockaden (403/429/Captcha) halten den Lauf an und melden ``fail``.
    * Wiederaufnahme über lokalen State (bereits übertragene TM-IDs).
"""

import time

from .api_client import ApiError, FatalApiError, ImporterApiClient, NoJobAvailable
from .adapters.base import BlockedError, PageError, is_closed_error
from .adapters.fminside import FMInsideAdapter
from .adapters.transfermarkt import TransfermarktAdapter
from .browser import Browser
from .roster_match import RosterMatcher
from .state import JobState


class _BrowserGone(Exception):
    """Interner Signalfehler: Browser/Kontext/Page verloren — Neustart nötig."""


class Runner:
    # Wie oft der Browser nach Verlust (Absturz/externes Schließen) neu
    # gestartet wird, bevor der Lauf endgültig abgebrochen wird.
    MAX_BROWSER_RELAUNCH = 3

    def __init__(self, config, logger):
        self.config = config
        self.log = logger
        self.api = ImporterApiClient(
            config.api_base_url, config.api_token, logger,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
            backoff_base=config.backoff_base)
        self._last_heartbeat = 0.0
        self._roster_matcher = None

    # ── Verbindungs- und Auswahlphase ───────────────────────────────────────
    def run(self, auto_yes=False):
        self.log.info('Prüfe Verbindung zur Importer-API ...')
        try:
            job = self.api.check_connection()
        except FatalApiError as exc:
            self.log.error('Verbindung/Authentifizierung fehlgeschlagen: %s', exc)
            return 2
        except ApiError as exc:
            self.log.error('Verbindung fehlgeschlagen: %s', exc)
            return 2

        if not job:
            self.log.info('Kein offener Importauftrag vorhanden. Nichts zu tun.')
            return 0

        self.log.info('Offener Auftrag #%s: %s (TM-Verein %s, Saison %s)',
                      job.get('id'), job.get('ws_club', {}).get('name'),
                      job.get('tm_club_id'), job.get('season_label'))

        if not auto_yes and not self._confirm():
            self.log.info('Abgebrochen durch Benutzer.')
            return 0

        return self._process(job)

    def _confirm(self):
        try:
            answer = input('Diesen Auftrag jetzt starten? [j/N] ').strip().lower()
        except EOFError:
            return False
        return answer in ('j', 'ja', 'y', 'yes')

    # ── Verarbeitung ────────────────────────────────────────────────────────
    def _process(self, job):
        job_id = job['id']
        try:
            claimed = self.api.claim_job(job_id)
        except FatalApiError as exc:
            self.log.error('Auftrag konnte nicht übernommen werden: %s', exc)
            return 2
        except ApiError as exc:
            self.log.error('Auftrag bereits vergeben oder Fehler: %s', exc)
            return 1

        self.log.info('Auftrag #%s übernommen.', job_id)
        self._roster_matcher = RosterMatcher(claimed.get('roster', []))
        self.log.info('%d Vereinsspieler mit FM-ID für das Matching erhalten.',
                      len(self._roster_matcher))
        state = JobState(job_id)
        self._last_heartbeat = time.time()

        try:
            return self._run_job(job_id, claimed, state)
        except FatalApiError as exc:
            self.log.error('Abbruch (Auth/Lease): %s', exc)
            return 2
        except BlockedError as exc:
            self.log.error('Abbruch (Quelle blockiert): %s', exc)
            self._safe_fail(job_id, f'Blockiert: {exc}')
            return 1
        except Exception as exc:
            self.log.exception('Unerwarteter Fehler: %s', exc)
            self._safe_fail(job_id, f'Unerwarteter Fehler: {exc}')
            return 1

    def _run_job(self, job_id, claimed, state):
        """Führt den Auftrag aus und nimmt bei Browser-Verlust den Lauf neu auf.

        Stirbt der gesteuerte Edge mitten im Lauf (Absturz oder externes
        Schließen, z. B. weil parallel ein normales Edge offen ist), wird der
        Browser neu gestartet und über den lokalen State (bereits übertragene
        Spieler) fortgesetzt — statt eine tote Seite endlos neu zu laden.
        """
        relaunches = 0
        browser = Browser(self.config, self.log)
        browser.__enter__()
        try:
            while True:
                try:
                    return self._scrape_squad(job_id, claimed, state, browser)
                except _BrowserGone as exc:
                    if relaunches >= self.MAX_BROWSER_RELAUNCH:
                        self.log.error('Browser wiederholt verloren — Abbruch.')
                        self._safe_fail(job_id, 'Browser wiederholt verloren.')
                        return 1
                    relaunches += 1
                    self.log.warning(
                        'Browser verloren (%s) — Neustart %d/%d, Wiederaufnahme '
                        'über lokalen State.', exc, relaunches,
                        self.MAX_BROWSER_RELAUNCH)
                    browser.restart()
        finally:
            browser.__exit__(None, None, None)

    def _scrape_squad(self, job_id, claimed, state, browser):
        """Liest den Kader und überträgt jeden Spieler einzeln.

        Wird nach einem Browser-Neustart erneut aufgerufen; die Adapter werden
        deshalb hier (mit der aktuellen ``browser.page``) gebildet und der Kader
        wird erneut gelesen. Bereits übertragene Spieler überspringt der State.
        """
        tm = TransfermarktAdapter(browser.page, self.config, self.log)
        fmi = FMInsideAdapter(browser.page, self.config, self.log)

        self._progress(job_id, step='Lese Kaderseite ...')
        try:
            squad = tm.collect_squad(claimed['tm_club_id'], claimed['tm_season_id'])
        except Exception as exc:
            if is_closed_error(exc):
                raise _BrowserGone(exc)
            raise
        total = len(squad)
        state.set_total(total)
        self.log.info('%d Spieler im Kader gefunden.', total)
        self._progress(job_id, current=0, total=total,
                       step=f'{total} Spieler gefunden')

        done = 0
        for entry in squad:
            done += 1
            pid = entry['tm_player_id']
            if state.is_sent(pid):
                self.log.info('[%d/%d] %s bereits übertragen — überspringe.',
                              done, total, entry.get('display_name'))
                self._progress(job_id, current=done, total=total)
                continue

            self._heartbeat_if_due(job_id)
            self._progress(job_id, current=done, total=total,
                           step=f'Spieler {done}/{total}: '
                                f'{entry.get("display_name", "")}')
            try:
                candidate = self._build_candidate(tm, fmi, entry)
            except BlockedError as exc:
                self.log.error('Quelle blockiert — Lauf wird angehalten: %s', exc)
                self.api.fail(job_id, f'Blockiert: {exc}')
                return 1
            except PageError as exc:
                # ``safe_goto`` verpackt auch Navigationsfehler eines toten
                # Browsers als PageError — diese dürfen NICHT als „Spieler
                # überspringen" gewertet werden, sonst würde jeder Spieler an
                # einer toten Seite scheitern. Stattdessen Neustart auslösen.
                if is_closed_error(exc):
                    raise _BrowserGone(exc)
                self.log.warning('[%d/%d] Übersprungen (%s): %s',
                                 done, total, entry.get('display_name'), exc)
                continue
            except Exception as exc:  # robust gegen einzelne Parserfehler
                if is_closed_error(exc):
                    raise _BrowserGone(exc)
                self.log.warning('[%d/%d] Übersprungen (Fehler): %s',
                                 done, total, exc)
                continue

            try:
                self.api.send_candidate(job_id, candidate)
                state.mark_sent(pid)
                self.log.info('[%d/%d] %s übertragen.',
                              done, total, entry.get('display_name'))
            except FatalApiError as exc:
                self.log.error('Lease/Authentifizierung verloren: %s', exc)
                return 2

            self.page_pause()

        self._progress(job_id, current=total, total=total,
                       step='Übertragung abgeschlossen')
        self.api.complete(job_id, tm_club_name=getattr(
            tm, 'squad_club_name', ''))
        state.clear()
        self.log.info('Auftrag #%s abgeschlossen — bereit zur Kontrolle.', job_id)
        return 0

    # ── Kandidatenaufbau ────────────────────────────────────────────────────
    def _build_candidate(self, tm, fmi, entry):
        details = tm.player_details(entry)
        tm_data = details['tm']
        warnings = list(details.get('warnings', []))
        errors = list(details.get('errors', []))

        # FM-ID-Quelle: direkt vorhandene ID, sonst Zuordnung über den vom Server
        # gelieferten Vereinskader (Name + Geburtsdatum). Erst diese ID aktiviert
        # den eindeutigen FMInside-Lookup per Unique ID.
        matched_id = None
        if self._roster_matcher is not None:
            matched_id = self._roster_matcher.match(
                tm_data.get('display_name', ''),
                tm_data.get('date_of_birth', ''))
        fmi_raw = fmi.lookup(
            display_name=tm_data.get('display_name', ''),
            date_of_birth=tm_data.get('date_of_birth', ''),
            nationality=tm_data.get('primary_nationality', ''),
            fmi_id=tm_data.get('fmi_id') or entry.get('fmi_id') or matched_id,
            warnings=warnings)

        candidate = {
            'tm_player_id': entry['tm_player_id'],
            'tm': tm_data,
            'club_assignment': details.get('club_assignment', {}),
            'positions': details.get('positions', {}),
            'warnings': warnings,
            'errors': errors,
        }
        if fmi_raw:
            candidate['fmi'] = fmi_raw
        return candidate

    # ── Heartbeat / Fortschritt ─────────────────────────────────────────────
    def _heartbeat_if_due(self, job_id):
        if time.time() - self._last_heartbeat >= self.config.heartbeat_seconds:
            try:
                self.api.heartbeat(job_id)
                self._last_heartbeat = time.time()
            except ApiError as exc:
                self.log.warning('Heartbeat fehlgeschlagen: %s', exc)

    def _progress(self, job_id, current=None, total=None, step=None):
        try:
            self.api.progress(job_id, current=current, total=total, step=step)
            self._last_heartbeat = time.time()
        except ApiError as exc:
            self.log.warning('Fortschritt konnte nicht gesendet werden: %s', exc)

    def _safe_fail(self, job_id, message):
        try:
            self.api.fail(job_id, message)
        except ApiError:
            pass

    def page_pause(self):
        time.sleep(self.config.pause('between_players_ms', 2500))
