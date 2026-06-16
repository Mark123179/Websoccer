"""Automatische Transfermarkt-Saisonlogik (Europe/Berlin).

Regel (Spec §5):
    01.01.–30.06. eines Jahres → Saison-ID = Jahr − 1
    ab 01.07.     eines Jahres → Saison-ID = Jahr

Beispiele:
    16.06.2026 → 2025 → "2025/26"
    01.07.2026 → 2026 → "2026/27"

Die Saison-ID wird bei Auftragserstellung einmalig bestimmt und danach im
Auftrag eingefroren (sie darf nicht nachträglich neu berechnet werden).
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

BERLIN_TZ = ZoneInfo('Europe/Berlin')


def get_current_tm_season_id(reference_date=None):
    """Bestimmt die Transfermarkt-Saison-ID für ein Datum (Default: heute, Berlin).

    Args:
        reference_date: ``date``, ``datetime`` oder ``None``. Ein tz-bewusstes
            ``datetime`` wird nach Europe/Berlin konvertiert; ein naives
            ``datetime`` bzw. ``date`` wird als Berliner Datum interpretiert.

    Returns:
        int: Saison-ID (= Startjahr der Saison).
    """
    if reference_date is None:
        reference_date = datetime.now(BERLIN_TZ).date()
    elif isinstance(reference_date, datetime):
        if reference_date.tzinfo is not None:
            reference_date = reference_date.astimezone(BERLIN_TZ)
        reference_date = reference_date.date()
    elif not isinstance(reference_date, date):
        raise TypeError('reference_date muss date, datetime oder None sein.')

    if reference_date.month <= 6:
        return reference_date.year - 1
    return reference_date.year


def season_label(season_id):
    """Formatiert eine Saison-ID als Anzeige-Label, z. B. 2025 → "2025/26"."""
    season_id = int(season_id)
    next_two = (season_id + 1) % 100
    return f'{season_id}/{next_two:02d}'
