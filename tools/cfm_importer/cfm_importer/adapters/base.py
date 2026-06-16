"""Gemeinsame Helfer für die Quell-Adapter (keine quellspezifischen Selektoren)."""

import re
import time


class PageError(Exception):
    """Eine erwartete Seite/Struktur fehlt — Spieler überspringen, nicht raten."""


class BlockedError(Exception):
    """Quelle blockiert den Zugriff (403/429/Captcha) — Lauf anhalten."""


def text_or_empty(locator):
    """Liefert getrimmten Text eines Locators oder ''. Wirft nie."""
    try:
        if locator.count() == 0:
            return ''
        return (locator.first.inner_text() or '').strip()
    except Exception:
        return ''


def attr_or_empty(locator, name):
    try:
        if locator.count() == 0:
            return ''
        return (locator.first.get_attribute(name) or '').strip()
    except Exception:
        return ''


def first_int(text):
    """Erste Ganzzahl in einem Text (Tausenderpunkte werden entfernt)."""
    if not text:
        return None
    cleaned = str(text).replace('.', '').replace('\u202f', '').replace('\xa0', '')
    m = re.search(r'-?\d+', cleaned)
    return int(m.group(0)) if m else None


def id_from_url(url, segment):
    """Extrahiert die Zahl nach ``/<segment>/`` aus einer URL (z. B. spieler)."""
    if not url:
        return None
    m = re.search(rf'/{re.escape(segment)}/(\d+)', url)
    return int(m.group(1)) if m else None


_BLOCK_MARKERS = (
    'zugriff verweigert', 'access denied', 'are you a robot',
    'attention required', 'just a moment', 'captcha', 'rate limit',
    'einen moment', 'checking your browser', 'verifying you are human',
)


def is_blocked(page):
    """True, wenn die Seite wie eine Blockier-/Challenge-Seite aussieht."""
    try:
        title = (page.title() or '').lower()
    except Exception:
        title = ''
    return any(m in title for m in _BLOCK_MARKERS)


def detect_block(page):
    """Erkennt typische Blockier-/Captcha-Seiten und wirft ``BlockedError``."""
    if is_blocked(page):
        try:
            title = (page.title() or '')
        except Exception:
            title = ''
        raise BlockedError(f'Quelle blockiert den Zugriff (Titel: {title!r}).')


_CLOSED_MARKERS = (
    'has been closed', 'target closed', 'target page, context or browser',
    'browser has been closed', 'connection closed',
)


def is_closed_error(exc):
    """True, wenn ein Fehler auf einen geschlossenen Page/Kontext/Browser deutet.

    Tritt z. B. auf, wenn der gesteuerte Edge abstürzt oder extern beendet wird
    (etwa weil parallel ein normales Edge geöffnet ist). Solche Fehler sind
    **nicht** durch erneutes Navigieren auf dieselbe tote Seite behebbar — der
    Browser muss neu gestartet werden.
    """
    msg = str(exc or '').lower()
    return any(m in msg for m in _CLOSED_MARKERS)


def _backoff_sleep(config, attempt, log, reason):
    """Wartet mit exponentiellem Backoff vor dem nächsten Versuch."""
    delay = float(config.backoff_base) * (2 ** (attempt - 1))
    log.warning('%s — neuer Versuch in %.1fs (Versuch %d).', reason, delay, attempt + 1)
    time.sleep(delay)


def _wait_out_challenge(page, config, log):
    """Wartet, bis sich eine Challenge von selbst auflöst.

    Gibt ``True`` zurück, sobald die Seite nicht mehr blockiert wirkt, sonst
    ``False`` nach Ablauf von ``challenge_wait_seconds``.
    """
    deadline = time.time() + max(0, int(config.challenge_wait_seconds))
    log.warning('Challenge/Block erkannt — warte bis zu %ds auf Auflösung ...',
                int(config.challenge_wait_seconds))
    while time.time() < deadline:
        page.wait_for_timeout(1000)
        if not is_blocked(page):
            log.info('Challenge automatisch aufgelöst — fahre fort.')
            return True
    return False


def _resolve_block(page, config, log):
    """Versucht, eine erkannte Blockade aufzulösen (automatisch + ggf. manuell).

    Reihenfolge: erst auf automatische Auflösung warten; gelingt das nicht und
    ist ein sichtbarer Browser samt manuellem Entsperren erlaubt, den Nutzer
    bitten, die Challenge selbst zu lösen. Gibt ``True`` zurück, wenn die Seite
    danach frei ist.
    """
    if _wait_out_challenge(page, config, log):
        return True
    if config.manual_unblock and not config.headless:
        log.warning('Bitte die Challenge im sichtbaren Browser-Fenster lösen.')
        try:
            input('>>> Challenge gelöst? Dann ENTER drücken, um fortzufahren ... ')
        except EOFError:
            pass
        page.wait_for_timeout(500)
        return not is_blocked(page)
    return False


def safe_goto(page, url, config, log):
    """Navigiert robust zu ``url`` mit Retry/Backoff und Challenge-Handling.

    - HTTP 403/429 oder erkannte Challenge → erst auf Auflösung warten, dann
      (sichtbarer Browser) manuell lösen lassen; sonst Backoff + neuer Versuch.
    - HTTP 5xx und Navigations-/Timeoutfehler → Backoff + neuer Versuch.
    - HTTP 404/410 → endgültig ``PageError`` (kein Raten, kein Retry).
    Schlägt alles fehl: ``BlockedError`` (Blockade) bzw. ``PageError``.
    """
    attempts = max(1, int(config.nav_retries) + 1)
    page_pause_ms = int(config.pause('page_load_ms', 1500) * 1000)
    last_reason = 'Navigation fehlgeschlagen'

    for attempt in range(1, attempts + 1):
        status = 0
        try:
            response = page.goto(
                url, wait_until='domcontentloaded',
                timeout=int(config.request_timeout) * 1000)
            status = response.status if response is not None else 0
            page.wait_for_timeout(page_pause_ms)
        except Exception as exc:  # Timeout / Navigationsfehler
            last_reason = f'Navigationsfehler: {exc}'
            if attempt < attempts:
                _backoff_sleep(config, attempt, log, last_reason)
                continue
            raise PageError(last_reason)

        if status in (404, 410):
            raise PageError(f'Seite nicht vorhanden (HTTP {status}): {url}')

        challenge = is_blocked(page)
        if challenge or status in (403, 429):
            # Nur eine echte Challenge-Seite (am Titel erkennbar) lässt sich
            # automatisch/manuell auflösen. Ein reiner 403/429 ohne Challenge
            # wird sonst fälschlich als „frei" gewertet — daher hier getrennt.
            if challenge and _resolve_block(page, config, log):
                return
            last_reason = f'Blockiert (HTTP {status or "?"})'
            if attempt < attempts:
                _backoff_sleep(config, attempt, log, last_reason)
                continue
            raise BlockedError(f'{last_reason} bei {url}.')

        if status >= 500:
            last_reason = f'Serverfehler (HTTP {status})'
            if attempt < attempts:
                _backoff_sleep(config, attempt, log, last_reason)
                continue
            raise PageError(f'{last_reason} bei {url}.')

        return
