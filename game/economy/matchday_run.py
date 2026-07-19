"""finance_matchday_run — Finanz-Spieltagslauf (Spec Kap. 15, Phase 2).

Reihenfolge je Verein (Cashflow-Design Kap. 12.2: Einnahmen VOR Gehältern):
  1. TV-Sockel-Spieltagsrate buchen (echte Landeskoeffizienten, game.economy.tv)
  2. Sponsor: Fixrate + Sieggeld (Ligasieg) buchen
  3. Heimspiel: Ticketeinnahmen buchen + Zuschauer-Sponsorbonus
  4. Gehälter aller Kaderspieler buchen (Pflichtbuchung, aggregiert)
  5. Betriebskosten: Sockel-Rate + BETRIEBSQUOTE × Einnahmen seit letztem Lauf

Idempotenz: FinanceMatchdayRun (unique je Verein+Saison+Spieltag) — ein
zweiter Aufruf für denselben Spieltag ist ein No-op. Der gesamte Lauf eines
Vereins ist EINE Transaktion: bricht ein Schritt ab, wird auch der
Idempotenz-Marker zurückgerollt.

Sponsor: Ohne gewähltes Angebot pickt get_active_offer() automatisch das
Sicherheits-Angebot (KI-Vereine & zögerliche Manager). Sieggeld für
Pokalsiege bucht der Pokal-Hook (cup_service), nicht dieser Lauf.
"""
from decimal import Decimal

from django.db import transaction

from .booking import book
from .params import get_decimal
from .salary import gehalt_pro_pflichtspiel, load_salary_params
from .snapshot import ensure_season_snapshot
from .tv import tv_sockel_rate

# Laufende Einnahmen für die Betriebskosten-Quote (Spec Kap. 10).
# Bewusst OHNE Transfers/Ausbildungsabgabe (Zirkulation) und ohne
# KORREKTUR_ADMIN (Admin-Eingriffe sind kein Umsatz).
OPERATIVE_EINNAHME_TYPEN = (
    'TICKET', 'UMFELD', 'SPONSOR_FIX', 'SPONSOR_VARIABEL',
    'TV_SOCKEL', 'TV_PLATZ', 'TV_KOEFF', 'FALLSCHIRM',
    'PRAEMIE_POKAL', 'PRAEMIE_SUPERCUP', 'PRAEMIE_INTL',
)


def _opponent_strength(club) -> float:
    """Ø base_strength der Top-11 des Gegners (Fallback 65)."""
    from game.season_goals import club_squad_strength
    total = club_squad_strength(club)
    if not total:
        return 65.0
    return float(total) / 11.0


def _book_salaries(club, saison, matchday, anker, salary_params):
    from game.models import Player

    mws = list(Player.objects.filter(club=club).values_list('market_value', flat=True))
    if not mws:
        return None

    total = sum(
        (gehalt_pro_pflichtspiel(mw, anker, salary_params) for mw in mws),
        Decimal('0.00'),
    )
    if total <= 0:
        return None

    return book(
        club, 'GEHALT', -total,
        beschreibung=f'Gehälter Spieltag {matchday} ({len(mws)} Spieler)',
        saison=saison, spieltag=matchday,
        referenz_typ='matchday', pflicht=True,
    )


def _book_tickets(club, fixture, saison, matchday):
    """Ticketeinnahmen fürs Heimspiel (einfacher Nachfragefaktor, Phase 1)."""
    from game.stadium_revenue import record_matchday_revenue

    try:
        club.stadium
    except Exception:
        return None  # Kein Stadion → keine Ticketeinnahmen (Phase 1).

    opponent_strength = _opponent_strength(fixture.away_club)
    entry = record_matchday_revenue(
        club=club,
        match_result=None,
        opponent_strength=opponent_strength,
        competition_name=fixture.league.name if fixture.league_id else 'Liga',
        saison=saison,
        spieltag=matchday,
    )
    return entry


def _book_betriebskosten(club, saison, matchday, window_start, window_end):
    """Betriebskosten: Sockel-Rate + Quote auf Einnahmen im Fenster.

    Fenster = (window_start, window_end] — halboffen, damit jede Einnahme
    genau EINMAL belastet wird: Die Einnahmen des laufenden Spieltagslaufs
    (created_at > window_end) fallen erst in den Folgelauf.
    """
    from django.db.models import Sum
    from game.models import FinanceTransaction

    sockel = get_decimal('BETRIEB_SOCKEL', saison)
    divisor = get_decimal('GEHALT_DIVISOR', saison)
    quote = get_decimal('BETRIEBSQUOTE', saison)

    sockel_rate = (sockel / divisor).quantize(Decimal('0.01'))

    einnahmen = (
        FinanceTransaction.objects.filter(
            club=club,
            typ__in=OPERATIVE_EINNAHME_TYPEN,
            betrag__gt=0,
            created_at__gt=window_start,
            created_at__lte=window_end,
        ).aggregate(s=Sum('betrag'))['s']
        or Decimal('0.00')
    )

    total = (sockel_rate + quote * einnahmen).quantize(Decimal('0.01'))
    if total <= 0:
        return None

    return book(
        club, 'BETRIEB', -total,
        beschreibung=(
            f'Betriebskosten Spieltag {matchday} '
            f'(Sockel {sockel_rate:,.0f} € + {quote * 100:.0f} % '
            f'auf {einnahmen:,.0f} € Einnahmen)'
        ),
        saison=saison, spieltag=matchday,
        referenz_typ='matchday', pflicht=True,
    )


def _club_won_fixture(club, fixture) -> bool:
    """True, wenn der Verein das (gespielte) Liga-Fixture gewonnen hat."""
    if fixture is None or not fixture.is_played:
        return False
    if fixture.home_goals is None or fixture.away_goals is None:
        return False
    if fixture.home_club_id == club.pk:
        return fixture.home_goals > fixture.away_goals
    if fixture.away_club_id == club.pk:
        return fixture.away_goals > fixture.home_goals
    return False


def _book_sponsor_income(club, saison, matchday, fixture, result):
    """Sponsor-Fixrate + Sieggeld für den Spieltag (Spec Kap. 6)."""
    from .sponsors import get_active_offer, sponsor_fix_rate, book_sieg_bonus

    offer = get_active_offer(club, saison, autopick=True)
    if offer is None:
        return None

    fix_rate = sponsor_fix_rate(offer, saison)
    if fix_rate > 0:
        tx = book(
            club, 'SPONSOR_FIX', fix_rate,
            beschreibung=f'{offer.sponsor_name}: Fixrate Spieltag {matchday}',
            saison=saison, spieltag=matchday,
            referenz_typ='matchday', referenz_id=offer.pk,
            pflicht=True,
        )
        result['sponsor_fix'] = tx.betrag

    if fixture is not None and _club_won_fixture(club, fixture):
        sieg_tx = book_sieg_bonus(
            club, offer, saison,
            beschreibung=f'{offer.sponsor_name}: Siegprämie Spieltag {matchday}',
            referenz_typ='sponsor_sieg_liga', referenz_id=fixture.pk,
            spieltag=matchday,
        )
        if sieg_tx is not None:
            result['sponsor_sieg'] = sieg_tx.betrag

    return offer


def run_club_finance(club, league, saison: str, matchday: int,
                     home_fixture=None, fixture=None, tv_rate=None,
                     anker=None, salary_params=None) -> dict:
    """Kompletter Finanz-Spieltagslauf für EINEN Verein (idempotent).

    ``fixture`` = das Fixture des Vereins an diesem Spieltag (heim ODER
    auswärts) — Basis für das Sponsor-Sieggeld. ``home_fixture`` bleibt
    separat, weil nur Heimspiele Tickets erzeugen.
    """
    from game.models import FinanceMatchdayRun

    saison = str(saison)

    if FinanceMatchdayRun.objects.filter(
        club=club, saison=saison, spieltag=matchday,
    ).exists():
        return {'club': club.name, 'skipped': True}

    if tv_rate is None:
        tv_rate = tv_sockel_rate(league, saison)
    if anker is None:
        anker = ensure_season_snapshot(saison).gehalts_anker
    if salary_params is None:
        salary_params = load_salary_params(saison)

    result = {'club': club.name, 'skipped': False, 'tickets': None}

    with transaction.atomic():
        run = FinanceMatchdayRun.objects.create(
            club=club, saison=saison, spieltag=matchday,
        )
        prev = (
            FinanceMatchdayRun.objects
            .filter(club=club, run_at__lt=run.run_at)
            .exclude(pk=run.pk)
            .order_by('-run_at')
            .first()
        )
        window_start = prev.run_at if prev else run.run_at

        if tv_rate > 0:
            tx = book(
                club, 'TV_SOCKEL', tv_rate,
                beschreibung=f'TV-Gelder Sockelrate Spieltag {matchday}',
                saison=saison, spieltag=matchday,
                referenz_typ='matchday', pflicht=True,
            )
            result['tv_sockel'] = tx.betrag

        offer = _book_sponsor_income(club, saison, matchday, fixture, result)

        if home_fixture is not None:
            entry = _book_tickets(club, home_fixture, saison, matchday)
            if entry is not None:
                result['tickets'] = entry.revenue_total
                if offer is not None:
                    from .sponsors import book_zuschauer_bonus
                    zs_tx = book_zuschauer_bonus(
                        club, offer, entry.attendance, saison,
                        spieltag=matchday,
                    )
                    if zs_tx is not None:
                        result['sponsor_zuschauer'] = zs_tx.betrag

        gehalt_tx = _book_salaries(club, saison, matchday, anker, salary_params)
        result['gehalt'] = gehalt_tx.betrag if gehalt_tx else Decimal('0.00')

        betrieb_tx = _book_betriebskosten(
            club, saison, matchday, window_start, run.run_at)
        result['betrieb'] = betrieb_tx.betrag if betrieb_tx else Decimal('0.00')

    return result


def run_matchday_finance(league, saison: str, matchday: int) -> dict:
    """Finanz-Spieltagslauf für alle Vereine eines gespielten Spieltags.

    Läuft NACH der sportlichen Simulation (Hook in season_service /
    play_matchday) oder manuell via Management-Command. Idempotent je
    Verein+Spieltag — Doppel-Hooks sind unschädlich.
    """
    from game.models import SeasonFixture

    saison = str(saison)
    fixtures = list(
        SeasonFixture.objects
        .filter(league=league, season=saison, matchday=matchday)
        .select_related('home_club', 'away_club', 'league')
    )
    if not fixtures:
        return {'clubs': [], 'errors': [f'Keine Fixtures für Spieltag {matchday}.']}

    tv_rate = tv_sockel_rate(league, saison)
    anker = ensure_season_snapshot(saison).gehalts_anker
    salary_params = load_salary_params(saison)

    home_by_club = {f.home_club_id: f for f in fixtures}
    fixture_by_club = {}
    clubs = {}
    for f in fixtures:
        clubs[f.home_club_id] = f.home_club
        clubs[f.away_club_id] = f.away_club
        fixture_by_club[f.home_club_id] = f
        fixture_by_club[f.away_club_id] = f

    results, errors = [], []
    for club_id, club in sorted(clubs.items()):
        try:
            results.append(run_club_finance(
                club, league, saison, matchday,
                home_fixture=home_by_club.get(club_id),
                fixture=fixture_by_club.get(club_id),
                tv_rate=tv_rate, anker=anker, salary_params=salary_params,
            ))
        except Exception as exc:  # Ein Vereinsfehler stoppt nicht den Spieltag.
            errors.append(f'{club.name}: {exc}')

    return {'clubs': results, 'errors': errors}
