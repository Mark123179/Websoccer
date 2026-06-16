"""Namensnormalisierung für das Quell-Matching (Spiegel der Server-Engine).

Identisch zu ``game/club_import/normalization.py``, damit FMInside-Treffer
nach denselben Regeln wie serverseitig verglichen werden.
"""

import html
import re
import unicodedata


def normalize_name(value):
    """Normalisiert einen Namen für robusten Vergleich.

    Entfernt HTML-Entities, diakritische Zeichen (NFKD -> ASCII) und alle
    Nicht-Buchstaben; gibt Kleinbuchstaben zurück.
    """
    value = html.unescape(value or '')
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z]', '', value).lower()


def normalize_dob(value):
    """Bringt ein Geburtsdatum auf das Vergleichsformat ``YYYY-MM-DD``.

    Akzeptiert deutsche (``TT.MM.JJJJ``) und ISO-Eingaben; gibt bei
    Unklarheit ``''`` zurück (kein Raten).
    """
    if not value:
        return ''
    text = str(value).strip()
    m = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
    if m:
        d, mo, y = m.groups()
        return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
    if m:
        y, mo, d = m.groups()
        return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    return ''
