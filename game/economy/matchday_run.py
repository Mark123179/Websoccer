"""finance_matchday_run — Finanz-Spieltagslauf (Spec Kap. 15, Phase 2).

Reihenfolge je Verein (Cashflow-Design Kap. 12.2: Einnahmen VOR Gehältern):
  1. TV-Sockel-Spieltagsrate buchen (echte Landeskoeffizienten, game.economy.tv)
  2. Sponsor: Fixrate + Sieggeld (Ligasieg) buchen
  3. Heimspiel: Ticketeinnahmen (volle Nachfrageformel Kap. 5.1) +
     Stadionumfeld-Zusatzeinnahme + Zuschauer-Sponsorbonus
  4. Gehälter aller Kaderspieler buchen (Pflichtbuchung, aggregiert)
  5. Stadionkosten: Unterhalt-Rate (jeder Spieltag) + Spieltagskosten (Heimspiel)
  6. Betriebskosten: Sockel-Rate + BETRIEBSQUOTE × Einnahmen seit letztem Lauf

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
    """Ticketeinnahmen fürs Heimspiel (volle Nachfrageformel, Kap. 5.1)."""
    from game.stadium_revenue import record_matchday_revenue

    try:
        club.stadium
    except Exception:
        return None  # Kein Stadion → keine Ticketeinnahmen.

    entry = record_matchday_revenue(
        club=club,
        match_result=None,
        opponent_club=fixture.away_club,
        competition_name=fixture.league.name if fixture.league_id else 'Liga',
        saison=saison,
        spieltag=matchday,
    )
    return entry


def _book_umfeld(club, stadium, zuschauer, saison, matchday):
    """Stadionumfeld-Zusatzeinnahme €/Besucher (Kap. 5.4)."""
    from .stadium import umfeld_einnahme, umfeld_stufen

    betrag = umfeld_einnahme(stadium, zuschauer, saison)
    if betrag <= 0:
        return None
    return book(
        club, 'UMFELD', betrag,
        beschreibung=(
            f'Stadionumfeld Spieltag {matchday} '
            f'({umfeld_stufen(stadium)} Stufen × {zuschauer:,} Besucher)'
        ),
        saison=saison, spieltag=matchday,
        referenz_typ='matchday', pflicht=True,
    )


def _book_stadionkosten(club, saison, matchday, zuschauer):
    """Stadion-Unterhalt (jeder Spieltag) + Spieltagskosten (nur Heimspiel).

    Unterhalt = Kapazität × UNTERHALT_PLATZ pro Saison, anteilig je Spieltag
    (GEHALT_DIVISOR-Raster); Spieltagskosten = Zuschauer × KOSTEN_BESUCHER.
    Beides Pflichtbuchungen (dürfen ins Minus).
    """
    from .stadium import spieltagskosten, unterhalt_rate

    try:
        stadium = club.stadium
    except Exception:
        return None, None

    unterhalt_tx = None
    rate = unterhalt_rate(stadium, saison)
    if rate > 0:
        unterhalt_tx = book(
            club, 'STADION_UNTERHALT', -rate,
            beschreibung=(
                f'Stadion-Unterhalt Spieltag {matchday} '
                f'({stadium.capacity_total:,} Plätze)'
            ),
            saison=saison, spieltag=matchday,
            referenz_typ='matchday', pflicht=True,
        )

    spieltag_tx = None
    if zuschauer:
        kosten = spieltagskosten(zuschauer, saison)
        if kosten > 0:
            spieltag_tx = book(
                club, 'STADION_SPIELTAG', -kosten,
                beschreibung=(
                    f'Spieltagskosten Spieltag {matchday} '
                    f'({zuschauer:,} Zuschauer)'
                ),
                saison=saison, spieltag=matchday,
                referenz_typ='matchday', pflicht=True,
            )

    return unterhalt_tx, spieltag_tx


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

    # Fällige Stadionausbauten fertigstellen, BEVOR Nachfrage und
    # Unterhalt gerechnet werden (Kapazität wirkt auf beides).
    from .stadium import resolve_due_expansions
    try:
        _stadium = club.stadium
    except Exception:
        _stadium = None
    if _stadium is not None:
        resolve_due_expansions(_stadium)

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

        zuschauer = 0
        if home_fixture is not None:
            entry = _book_tickets(club, home_fixture, saison, matchday)
            if entry is not None:
                result['tickets'] = entry.revenue_total
                zuschauer = entry.attendance
                umfeld_tx = _book_umfeld(
                    club, entry.stadium, zuschauer, saison, matchday)
                if umfeld_tx is not None:
                    result['umfeld'] = umfeld_tx.betrag
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

        unterhalt_tx, spieltag_tx = _book_stadionkosten(
            club, saison, matchday, zuschauer)
        if unterhalt_tx is not None:
            result['stadion_unterhalt'] = unterhalt_tx.betrag
        if spieltag_tx is not None:
            result['stadion_spieltag'] = spieltag_tx.betrag

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
