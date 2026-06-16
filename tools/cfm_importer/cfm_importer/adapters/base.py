"""Gemeinsame Helfer für die Quell-Adapter (keine quellspezifischen Selektoren)."""

import re


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


def detect_block(page):
    """Erkennt typische Blockier-/Captcha-Seiten und wirft ``BlockedError``."""
    try:
        title = (page.title() or '').lower()
    except Exception:
        title = ''
    markers = ('zugriff verweigert', 'access denied', 'are you a robot',
               'attention required', 'just a moment', 'captcha', 'rate limit')
    if any(m in title for m in markers):
        raise BlockedError(f'Quelle blockiert den Zugriff (Titel: {title!r}).')
