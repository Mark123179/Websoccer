"""finance_matchday_run — Finanz-Spieltagslauf (Spec Kap. 15, Phase-1-Umfang).

Reihenfolge je Verein (Cashflow-Design Kap. 12.2: Einnahmen VOR Gehältern):
  1. TV-Sockel-Spieltagsrate buchen (Einnahme)
  2. Gehälter aller Kaderspieler buchen (Pflichtbuchung, aggregiert)
  3. Heimspiel: Ticketeinnahmen buchen (einfacher Nachfragefaktor, Phase 1)
  4. Betriebskosten: Sockel-Rate + BETRIEBSQUOTE × Einnahmen seit letztem Lauf

Idempotenz: FinanceMatchdayRun (unique je Verein+Saison+Spieltag) — ein
zweiter Aufruf für denselben Spieltag ist ein No-op. Der gesamte Lauf eines
Vereins ist EINE Transaktion: bricht ein Schritt ab, wird auch der
Idempotenz-Marker zurückgerollt.

Phase-2+-Posten (Sponsor-Fix, Unterhalt, Spieltagskosten, Sieggeld-Sponsor)
fehlen hier bewusst.

TV-Interim (Phase 1): Der Ländertopf-Rang kommt aus dem Interim-Parameter
TV_INTERIM_RANG_JE_LAND (Land → Rang), bis Phase 2 die echten
Landeskoeffizienten einführt. Alle Ligen gelten interim als „liga1“.
"""
from decimal import Decimal

from django.db import transaction

from .booking import book
from .params import get_decimal, get_param
from .salary import gehalt_pro_pflichtspiel, load_salary_params
from .snapshot import ensure_season_snapshot

# Laufende Einnahmen für die Betriebskosten-Quote (Spec Kap. 10).
# Bewusst OHNE Transfers/Ausbildungsabgabe (Zirkulation) und ohne
# KORREKTUR_ADMIN (Admin-Eingriffe sind kein Umsatz).
OPERATIVE_EINNAHME_TYPEN = (
    'TICKET', 'UMFELD', 'SPONSOR_FIX', 'SPONSOR_VARIABEL',
    'TV_SOCKEL', 'TV_PLATZ', 'TV_KOEFF', 'FALLSCHIRM',
    'PRAEMIE_POKAL', 'PRAEMIE_SUPERCUP', 'PRAEMIE_INTL',
)

TV_INTERIM_DEFAULT_RANG = 6


def _tv_sockel_rate(league, saison: str) -> Decimal:
    """TV-Sockel-Rate je Verein und Spieltag (Interim-Rangzuordnung)."""
    from game.models import SeasonFixture

    rang_map = get_param('TV_INTERIM_RANG_JE_LAND', saison) or {}
    rang = str(rang_map.get(league.country, TV_INTERIM_DEFAULT_RANG))

    toepfe = get_param('TV_TOEPFE', saison)
    topf = Decimal(str(toepfe.get(rang, toepfe.get(str(TV_INTERIM_DEFAULT_RANG)))))

    split = Decimal(str(get_param('TV_SPLIT_LIGA', saison)['liga1']))
    sockel_anteil = Decimal(str(get_param('TV_VERTEILUNG', saison)['sockel']))

    fixtures = SeasonFixture.objects.filter(league=league, season=saison)
    club_ids = set(fixtures.values_list('home_club_id', flat=True))
    n_clubs = len(club_ids) or 1
    max_md = (
        fixtures.order_by('-matchday').values_list('matchday', flat=True).first()
        or 1
    )

    return (topf * split * sockel_anteil / n_clubs / max_md).quantize(Decimal('0.01'))


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


def run_club_finance(club, league, saison: str, matchday: int,
                     home_fixture=None, tv_rate=None,
                     anker=None, salary_params=None) -> dict:
    """Kompletter Finanz-Spieltagslauf für EINEN Verein (idempotent)."""
    from game.models import FinanceMatchdayRun

    saison = str(saison)

    if FinanceMatchdayRun.objects.filter(
        club=club, saison=saison, spieltag=matchday,
    ).exists():
        return {'club': club.name, 'skipped': True}

    if tv_rate is None:
        tv_rate = _tv_sockel_rate(league, saison)
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

        gehalt_tx = _book_salaries(club, saison, matchday, anker, salary_params)
        result['gehalt'] = gehalt_tx.betrag if gehalt_tx else Decimal('0.00')

        if home_fixture is not None:
            entry = _book_tickets(club, home_fixture, saison, matchday)
            if entry is not None:
                result['tickets'] = entry.revenue_total

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

    tv_rate = _tv_sockel_rate(league, saison)
    anker = ensure_season_snapshot(saison).gehalts_anker
    salary_params = load_salary_params(saison)

    home_by_club = {f.home_club_id: f for f in fixtures}
    clubs = {}
    for f in fixtures:
        clubs[f.home_club_id] = f.home_club
        clubs[f.away_club_id] = f.away_club

    results, errors = [], []
    for club_id, club in sorted(clubs.items()):
        try:
            results.append(run_club_finance(
                club, league, saison, matchday,
                home_fixture=home_by_club.get(club_id),
                tv_rate=tv_rate, anker=anker, salary_params=salary_params,
            ))
        except Exception as exc:  # Ein Vereinsfehler stoppt nicht den Spieltag.
            errors.append(f'{club.name}: {exc}')

    return {'clubs': results, 'errors': errors}
