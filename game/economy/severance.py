"""Abfindungen bei Karriereende & Todesfall (Spec Kap. 4).

Karriereende: KEINE Zahlung (ABFINDUNG_KARRIEREENDE = 0) — alternde
Kader sind ein bewusstes Risiko. Der Aufruf bleibt trotzdem erlaubt
(einheitlicher Ereignispfad), bucht aber nichts, solange der Parameter 0 ist.

Todesfall: Entschädigung = Altersfaktor × Marktwert (ABFINDUNG_TOD,
WSC-Alterstabelle), Buchungstyp ABFINDUNG. Geldschöpfung, wegen der
Seltenheit ökonomisch unbedenklich.

Es gibt kein Todesfall-Event in der Sim — book_abfindung() ist der
Servicepfad für die Monats-Realdaten-Pflege (Admin/Importer).
Karriereende-Spieler wandern zum Pseudo-Verein „Karrierende"
(game.club_history.is_career_end_club); der ABGEBENDE Verein erhält
die (Null-)Abfindung.
"""
from decimal import Decimal

from .params import get_decimal, get_param

# (Tabellen-Key, Mindestalter, Höchstalter) — Reihenfolge = Prüfreihenfolge.
_ALTERS_STAFFEL = [
    ('16-17', 0, 17),
    ('18-20', 18, 20),
    ('21-22', 21, 22),
    ('23-24', 23, 24),
    ('25-28', 25, 28),
    ('29-32', 29, 32),
    ('33+', 33, 999),
]

GRUND_TOD = 'tod'
GRUND_KARRIEREENDE = 'karriereende'


def _faktor_tod(alter: int, saison: str) -> Decimal:
    tabelle = get_param('ABFINDUNG_TOD', saison)
    for key, lo, hi in _ALTERS_STAFFEL:
        if lo <= alter <= hi:
            return Decimal(str(tabelle[key]))
    return Decimal(str(tabelle['33+']))


def book_abfindung(player, grund: str, saison: str | None = None):
    """Bucht die Abfindung für den (Ex-)Verein eines Spielers.

    Args:
        player: Player-Instanz — der Verein wird aus player.club gelesen,
                daher VOR dem Umhängen auf den Karrierende-Pseudo-Verein
                aufrufen (oder das Club-Objekt vorher sichern und einen
                Player mit gesetztem club übergeben).
        grund:  'tod' oder 'karriereende'.

    Rückgabe: FinanceTransaction oder None (keine Zahlung fällig /
    bereits gebucht / kein Verein). Idempotent je (Spieler, Grund).
    """
    from game.models import FinanceTransaction
    from .booking import book
    from .params import current_season

    if grund not in (GRUND_TOD, GRUND_KARRIEREENDE):
        raise ValueError(f'Unbekannter Abfindungsgrund: {grund!r}')

    club = player.club
    if club is None:
        return None

    saison = str(saison) if saison is not None else current_season()

    if grund == GRUND_KARRIEREENDE:
        faktor = get_decimal('ABFINDUNG_KARRIEREENDE', saison)
        beschreibung = f'Abfindung Karriereende {player.first_name} {player.last_name}'
    else:
        alter = int(player.age or 0)
        faktor = _faktor_tod(alter, saison)
        beschreibung = f'Abfindung Todesfall {player.first_name} {player.last_name}'

    if faktor <= 0:
        return None

    mw = player.market_value
    if mw is None or mw <= 0:
        mw = get_decimal('MW_MINIMUM', saison)

    referenz_typ = f'abfindung:{grund}'
    if FinanceTransaction.objects.filter(
        club=club, typ='ABFINDUNG',
        referenz_typ=referenz_typ, referenz_id=player.pk,
    ).exists():
        return None

    betrag = (faktor * Decimal(mw)).quantize(Decimal('0.01'))
    return book(
        club, 'ABFINDUNG', betrag,
        beschreibung=beschreibung[:200],
        saison=saison,
        referenz_typ=referenz_typ, referenz_id=player.pk,
        pflicht=True,
    )
