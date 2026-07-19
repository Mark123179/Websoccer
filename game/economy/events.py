"""finance_event — Prämien-Buchungen (Spec Kap. 8 + 15).

Nationalpokal (8.1, Verdopplungsprinzip):
    Basis = POKAL_BASIS_ANTEIL × Landestopf
    Prämie(Runde r) = Basis × 2^(r−1)
    Titelgeld = Basis × POKAL_TITEL_FAKTOR
Supercup: Einzelspiel, Sieger 5× Basis, Verlierer 2,5× (SUPERCUP_FAKTOR).

International (8.2): fester Europatopf aus PRAEMIE_INTL (CL / EL),
NICHT koeffizientenabhängig. Es existiert noch keine Europapokal-
Simulation — book_intl() ist der Servicepfad ohne automatischen Hook.

Idempotenz: Jede Prämie trägt einen eindeutigen (referenz_typ,
referenz_id)-Anker; sync_cup_premiums() kann beliebig oft laufen
(z. B. nach jedem Rundenfortschritt UND als Backfill-Command).
"""
from decimal import Decimal

from .params import get_param


# ── Nationalpokal ────────────────────────────────────────────────────────────

def pokal_basis(cup_season, saison: str | None = None) -> Decimal:
    """Basisprämie des Pokals = POKAL_BASIS_ANTEIL × Landestopf (DE: ~410k)."""
    from .tv import tv_pot_gesamt

    saison = str(saison) if saison is not None else str(cup_season.season)
    land = cup_season.competition.country
    anteil = Decimal(str(get_param('POKAL_BASIS_ANTEIL', saison)))
    return (anteil * tv_pot_gesamt(land, saison)).quantize(Decimal('0.01'))


def sync_cup_premiums(cup_season) -> dict:
    """Bucht alle fälligen Pokalprämien einer Pokalsaison (idempotent).

    Für jede existierende Runde r erhält jeder Teilnehmer (Vereine der
    Fixtures, Freilos zählt als Teilnahme) einmalig Basis × 2^(r−1).
    Ist der Pokal abgeschlossen, erhält der Sieger zusätzlich das
    Titelgeld (Basis × POKAL_TITEL_FAKTOR).
    """
    from game.models import FinanceTransaction
    from .booking import book

    saison = str(cup_season.season)
    basis = pokal_basis(cup_season, saison)
    if basis <= 0:
        return {'booked': 0, 'errors': ['Pokal-Basis ist 0 — keine Prämien.']}

    vorhandene = set(
        FinanceTransaction.objects.filter(
            typ='PRAEMIE_POKAL',
            referenz_id=cup_season.pk,
            saison=saison,
        ).values_list('club_id', 'referenz_typ')
    )

    booked, errors = 0, []
    runden = cup_season.rounds.prefetch_related(
        'fixtures__home_club', 'fixtures__away_club',
    ).order_by('round_number')

    for runde in runden:
        referenz_typ = f'pokal_runde:{runde.round_number}'
        betrag = (basis * (2 ** (runde.round_number - 1))).quantize(Decimal('0.01'))
        teilnehmer = {}
        for f in runde.fixtures.all():
            if f.home_club_id:
                teilnehmer[f.home_club_id] = f.home_club
            if f.away_club_id:
                teilnehmer[f.away_club_id] = f.away_club

        for club_id, club in sorted(teilnehmer.items()):
            if (club_id, referenz_typ) in vorhandene:
                continue
            try:
                book(
                    club, 'PRAEMIE_POKAL', betrag,
                    beschreibung=(
                        f'Pokalprämie {cup_season.competition.name} '
                        f'Runde {runde.round_number}'
                    ),
                    saison=saison,
                    referenz_typ=referenz_typ, referenz_id=cup_season.pk,
                    pflicht=True,
                )
                booked += 1
            except Exception as exc:  # Ein Vereinsfehler stoppt nicht den Sync.
                errors.append(f'{club.name} R{runde.round_number}: {exc}')

    if cup_season.status == cup_season.STATUS_COMPLETED and cup_season.winner_club_id:
        if (cup_season.winner_club_id, 'pokal_titel') not in vorhandene:
            faktor = Decimal(str(get_param('POKAL_TITEL_FAKTOR', saison)))
            try:
                book(
                    cup_season.winner_club, 'PRAEMIE_POKAL',
                    (basis * faktor).quantize(Decimal('0.01')),
                    beschreibung=f'Titelgeld {cup_season.competition.name}',
                    saison=saison,
                    referenz_typ='pokal_titel', referenz_id=cup_season.pk,
                    pflicht=True,
                )
                booked += 1
            except Exception as exc:
                errors.append(f'Titelgeld {cup_season.winner_club}: {exc}')

    return {'booked': booked, 'errors': errors}


# ── Supercup ─────────────────────────────────────────────────────────────────

def book_supercup(sieger, verlierer, land: str, saison: str | None = None,
                  referenz_id: int | None = None) -> dict:
    """Supercup-Prämien: Sieger 5× Basis, Verlierer 2,5× (Servicepfad).

    Es existiert noch keine Supercup-Simulation. Idempotent je
    (Verein, Saison) über referenz_typ='supercup'.
    """
    from game.models import FinanceTransaction
    from .booking import book
    from .params import current_season
    from .tv import tv_pot_gesamt

    saison = str(saison) if saison is not None else current_season()
    anteil = Decimal(str(get_param('POKAL_BASIS_ANTEIL', saison)))
    basis = (anteil * tv_pot_gesamt(land, saison)).quantize(Decimal('0.01'))
    faktoren = get_param('SUPERCUP_FAKTOR', saison)

    ergebnis = {'booked': [], 'skipped': []}
    for club, key in ((sieger, 'sieger'), (verlierer, 'verlierer')):
        if FinanceTransaction.objects.filter(
            club=club, saison=saison, typ='PRAEMIE_SUPERCUP',
            referenz_typ='supercup',
        ).exists():
            ergebnis['skipped'].append(club.name)
            continue
        betrag = (basis * Decimal(str(faktoren[key]))).quantize(Decimal('0.01'))
        book(
            club, 'PRAEMIE_SUPERCUP', betrag,
            beschreibung=f'Supercup-Prämie ({key.capitalize()})',
            saison=saison,
            referenz_typ='supercup', referenz_id=referenz_id,
            pflicht=True,
        )
        ergebnis['booked'].append(club.name)
    return ergebnis


# ── International (CL / EL) ──────────────────────────────────────────────────

INTL_EINMALIG = ('start', 'achtelfinale', 'viertelfinale',
                 'halbfinale', 'finale', 'titel')
INTL_WIEDERHOLBAR = ('sieg', 'remis')


def book_intl(club, wettbewerb: str, ereignis: str,
              saison: str | None = None,
              referenz_id: int | None = None):
    """Bucht eine internationale Prämie (PRAEMIE_INTL, Spec 8.2).

    Args:
        wettbewerb: 'CL' oder 'EL'.
        ereignis: Schlüssel der PRAEMIE_INTL-Tabelle ('start', 'sieg',
                  'remis', 'achtelfinale', …, 'titel').
        referenz_id: Für wiederholbare Ereignisse (sieg/remis) die
                     Spiel-ID — dann idempotent je Spiel. Einmalige
                     Ereignisse sind je (Verein, Saison, Ereignis)
                     idempotent.

    Servicepfad: Es existiert noch keine Europapokal-Simulation, der
    Aufruf erfolgt manuell bzw. aus dem künftigen Europapokal-Modul.
    """
    from game.models import FinanceTransaction
    from .booking import book
    from .params import current_season

    wettbewerb = wettbewerb.upper()
    tabelle = get_param('PRAEMIE_INTL', saison)
    if wettbewerb not in tabelle:
        raise ValueError(f'Unbekannter Wettbewerb: {wettbewerb!r}')
    if ereignis not in tabelle[wettbewerb]:
        raise ValueError(f'Unbekanntes Ereignis: {ereignis!r}')

    saison = str(saison) if saison is not None else current_season()
    referenz_typ = f'intl:{wettbewerb}:{ereignis}'[:32]

    guard = FinanceTransaction.objects.filter(
        club=club, saison=saison, typ='PRAEMIE_INTL', referenz_typ=referenz_typ,
    )
    if ereignis in INTL_WIEDERHOLBAR:
        if referenz_id is None:
            raise ValueError(
                f'Ereignis {ereignis!r} braucht eine referenz_id (Spiel-ID) '
                f'für die Idempotenz.'
            )
        guard = guard.filter(referenz_id=referenz_id)
    if guard.exists():
        return None

    betrag = Decimal(str(tabelle[wettbewerb][ereignis])).quantize(Decimal('0.01'))
    labels = {
        'start': 'Startgeld Gruppenphase', 'sieg': 'Gruppensieg',
        'remis': 'Gruppenremis', 'achtelfinale': 'Achtelfinale',
        'viertelfinale': 'Viertelfinale', 'halbfinale': 'Halbfinale',
        'finale': 'Finalteilnahme', 'titel': 'Titel',
    }
    return book(
        club, 'PRAEMIE_INTL', betrag,
        beschreibung=f'{wettbewerb}-Prämie: {labels.get(ereignis, ereignis)}',
        saison=saison,
        referenz_typ=referenz_typ, referenz_id=referenz_id,
        pflicht=True,
    )
