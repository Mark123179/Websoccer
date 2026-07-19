"""Orchestrierende Schreibpfade des Scouting-Systems.

Alle geldbewegenden / zustandsändernden Operationen laufen in
``transaction.atomic()`` mit ``select_for_update`` auf Club / aktive Gebote /
Player / HoenessCoin. Reine Logik (Filter, Ziehung, Preise, Abdeckung) liegt in
den Nachbarmodulen; hier wird nur koordiniert und persistiert.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from game.club_import.season import get_current_tm_season_id
from game.finance import log_club_transaction

from . import coverage, department, draw, pricing
from .constants import (
    BASE_COMMITMENT_SLOTS,
    COUNTRIES,
    REGIONS,
    FINDS_PER_ASSIGNMENT,
    OBSERVER_MIN,
    OBSERVER_MAX,
    COMMUNITY_WEEKLY_LIMIT,
    COMMUNITY_COUNTRY_WEEK_CAP,
    COMMUNITY_ACTIVITY_POINTS,
    COMMUNITY_APPROVE_POINTS,
)
from .windows import window_for_bid


class ScoutingError(Exception):
    """Fachliche Validierungsfehler (für Anzeige als deutsche Meldung)."""


# ── kleine Helfer ────────────────────────────────────────────────────────────
def _today(today=None):
    return today or timezone.localdate()


def _week_key(d):
    iso = d.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def _player_name(player):
    return f'{player.first_name} {player.last_name}'.strip()


def _scope_label(scope_type, scope_key):
    if scope_type == 'region':
        return REGIONS.get(scope_key, {}).get('name', scope_key)
    return COUNTRIES.get((scope_key or '').upper(), {}).get('name', scope_key)


# ── Budget-/Slot-/Coin-Aggregate ─────────────────────────────────────────────
def reserved_budget(club):
    """Summe aller aktiven Gebotsbeträge des Vereins (reserviertes Budget)."""
    from game.models import ScoutingBid
    agg = ScoutingBid.objects.filter(club=club, status=ScoutingBid.STATUS_ACTIVE).aggregate(s=Sum('amount'))
    return agg['s'] or Decimal('0.00')


def available_budget(club):
    return (club.budget or Decimal('0.00')) - reserved_budget(club)


def current_squad_count(club):
    from game.models import Player
    return Player.objects.filter(club=club).count()


def reserved_slots(club):
    from game.models import ScoutingBid
    return ScoutingBid.objects.filter(club=club, status=ScoutingBid.STATUS_ACTIVE).count()


def commitment_used(club, season_id):
    """Verbrauchte Verpflichtungs-Slots dieser Saison = aktive Gebote + gewonnene Transfers."""
    from game.models import ScoutingBid
    return ScoutingBid.objects.filter(
        club=club, season_id=season_id,
        status__in=[ScoutingBid.STATUS_ACTIVE, ScoutingBid.STATUS_WON],
    ).count()


def coin_earmarked_count(manager, season_id):
    from game.models import ScoutingBid
    if manager is None:
        return 0
    return ScoutingBid.objects.filter(
        manager=manager, season_id=season_id,
        status=ScoutingBid.STATUS_ACTIVE, coin_earmarked=True,
    ).count()


def coin_available(manager, season_id):
    from game.models import HoenessCoin
    if manager is None:
        return 0
    coin = HoenessCoin.objects.filter(manager=manager).first()
    have = coin.amount if coin else 0
    return have - coin_earmarked_count(manager, season_id)


# ── Abteilung ────────────────────────────────────────────────────────────────
def upgrade_department(club, today=None):
    from game.models import Club
    today = _today(today)
    with transaction.atomic():
        club = Club.objects.select_for_update().get(pk=club.pk)
        dept = department.get_or_create_department(club)
        if not department.can_upgrade(dept.level):
            raise ScoutingError('Das Scoutingbüro ist bereits maximal ausgebaut.')
        cost = Decimal(department.upgrade_cost(dept.level))
        if available_budget(club) < cost:
            raise ScoutingError('Das verfügbare Budget reicht für den Ausbau nicht aus.')
        new_level = dept.level + 1
        club.budget = (club.budget or Decimal('0.00')) - cost
        club.save(update_fields=['budget'])
        dept.level = new_level
        dept.save(update_fields=['level', 'updated_at'])
        log_club_transaction(
            club, 'sonstige_ausgabe',
            f'Ausbau Scoutingbüro auf Stufe {new_level}',
            -cost, date=today,
        )
    return dept


# ── Auftrag starten ──────────────────────────────────────────────────────────
def start_assignment(club, manager, scope_type, scope_key, profile, position='', today=None):
    from game.models import Club, ScoutingAssignment
    today = _today(today)
    if scope_type == ScoutingAssignment.SCOPE_COUNTRY:
        scope_key = (scope_key or '').upper()

    if not coverage.is_scope_scoutable(scope_type, scope_key):
        raise ScoutingError('Dieses Suchgebiet ist derzeit nicht scoutbar.')

    with transaction.atomic():
        club = Club.objects.select_for_update().get(pk=club.pk)
        if ScoutingAssignment.objects.filter(club=club, status=ScoutingAssignment.STATUS_ACTIVE).exists():
            raise ScoutingError('Es läuft bereits ein aktiver Scoutingauftrag.')

        dept = department.get_or_create_department(club)
        level = dept.level
        cost = Decimal(department.order_cost(level))
        duration = department.order_duration(level)

        if available_budget(club) < cost:
            raise ScoutingError('Das verfügbare Budget reicht für die Auftragskosten nicht aus.')

        season_id = get_current_tm_season_id(today)
        assignment = ScoutingAssignment.objects.create(
            club=club, manager=manager,
            scope_type=scope_type, scope_key=scope_key,
            position=position or '', profile=profile,
            department_level=level, cost=cost, duration_days=duration,
            started_on=today, completes_on=today + timedelta(days=duration),
            season_id=season_id, status=ScoutingAssignment.STATUS_ACTIVE,
        )
        club.budget = (club.budget or Decimal('0.00')) - cost
        club.save(update_fields=['budget'])
        log_club_transaction(
            club, 'sonstige_ausgabe',
            f'Scoutingauftrag {_scope_label(scope_type, scope_key)}',
            -cost, date=today,
        )
    return assignment


# ── Funde erzeugen ───────────────────────────────────────────────────────────
def _assignment_precision(assignment):
    """Blend aus Abteilungs-Präzision (primär) und Community-Abdeckung."""
    dept_prec = department.precision(assignment.department_level)
    if assignment.scope_type == 'country':
        network = coverage.networks_by_iso().get(assignment.scope_key)
        cov = coverage.precision_factor(network)
    else:
        cov = 0.5
    return max(0.0, min(1.0, dept_prec * (0.7 + 0.3 * cov)))


def generate_finds(assignment, today=None, seed=None):
    from game.models import ScoutingAssignment, ScoutingFind
    today = _today(today)
    if assignment.status != ScoutingAssignment.STATUS_ACTIVE:
        raise ScoutingError('Für diesen Auftrag können keine Funde erzeugt werden.')
    if today < assignment.completes_on:
        raise ScoutingError('Der Scoutingauftrag ist noch nicht abgeschlossen.')
    if assignment.finds_generated:
        return list(assignment.finds.all())

    candidates = draw.eligible_players_filled(
        assignment.scope_type, assignment.scope_key, FINDS_PER_ASSIGNMENT
    )
    team_avg = draw.team_average_strength(assignment.club)
    precision = _assignment_precision(assignment)
    draw_seed = assignment.id if seed is None else seed
    chosen = draw.draw_candidates(
        candidates, team_avg, assignment.profile, assignment.position,
        precision, draw_seed, k=FINDS_PER_ASSIGNMENT,
    )

    obs_rng = random.Random(f'observers:{assignment.id}:{draw_seed}')
    with transaction.atomic():
        assignment = ScoutingAssignment.objects.select_for_update().get(pk=assignment.pk)
        if assignment.finds_generated:
            return list(assignment.finds.all())
        finds = []
        for order, player in enumerate(chosen):
            find = ScoutingFind.objects.create(
                assignment=assignment, player=player, order=order,
                observer_count=obs_rng.randint(OBSERVER_MIN, OBSERVER_MAX),
                min_bid=pricing.min_bid_for_player(player),
                status=ScoutingFind.STATUS_OFFERED,
            )
            finds.append(find)
        assignment.finds_generated = True
        assignment.save(update_fields=['finds_generated'])
    return finds


def reject_all_finds(assignment):
    from game.models import ScoutingAssignment, ScoutingFind
    with transaction.atomic():
        assignment = ScoutingAssignment.objects.select_for_update().get(pk=assignment.pk)
        if assignment.status != ScoutingAssignment.STATUS_ACTIVE:
            raise ScoutingError('Dieser Auftrag ist nicht mehr aktiv.')
        assignment.finds.filter(status=ScoutingFind.STATUS_OFFERED).update(status=ScoutingFind.STATUS_REJECTED)
        assignment.status = ScoutingAssignment.STATUS_COMPLETED
        assignment.save(update_fields=['status'])
    return assignment


# ── Watchlist ────────────────────────────────────────────────────────────────
def _upsert_watchlist(manager, player, status, only_if_absent=False):
    from game.models import WatchlistEntry
    if manager is None:
        return None
    entry, created = WatchlistEntry.objects.get_or_create(
        manager=manager, player=player, defaults={'status': status},
    )
    if not created and not only_if_absent:
        entry.status = status
        entry.save(update_fields=['status', 'updated_at'])
    return entry


def watch_find(club, manager, find):
    # Ein Fund darf nur vom eigenen Verein beobachtet werden (kein Cross-Club-Leak).
    if find.assignment.club_id != club.id:
        raise ScoutingError('Dieser Fund gehört nicht zu deinem Verein.')
    return _upsert_watchlist(manager, find.player, 'watched', only_if_absent=True)


def add_to_watchlist(manager, player):
    """Manuelles Hinzufügen eines beliebigen Spielers (managerseitig, kein Verein nötig).

    only_if_absent=True: ein bestehender Status ('bid'/'won') wird nicht überschrieben.
    """
    if manager is None:
        raise ScoutingError('Kein Manager-Profil vorhanden.')
    return _upsert_watchlist(manager, player, 'watched', only_if_absent=True)


def remove_from_watchlist(manager, player):
    """Entfernt einen Spieler aus der managergebundenen Beobachtungsliste."""
    from game.models import WatchlistEntry
    if manager is None:
        raise ScoutingError('Kein Manager-Profil vorhanden.')
    WatchlistEntry.objects.filter(manager=manager, player=player).delete()


# ── Gebot abgeben ────────────────────────────────────────────────────────────
def place_bid(club, manager, find, amount, today=None):
    from game.models import (
        Club, Player, ScoutingAssignment, ScoutingFind, ScoutingBid, HoenessCoin,
    )
    today = _today(today)
    amount = Decimal(amount)

    with transaction.atomic():
        club = Club.objects.select_for_update().get(pk=club.pk)
        find = ScoutingFind.objects.select_for_update().select_related('assignment').get(pk=find.pk)
        player = Player.objects.select_for_update().get(pk=find.player_id)
        assignment = find.assignment

        if assignment.club_id != club.id:
            raise ScoutingError('Dieser Fund gehört nicht zu deinem Verein.')
        if assignment.status != ScoutingAssignment.STATUS_ACTIVE:
            raise ScoutingError('Der zugehörige Auftrag ist nicht mehr aktiv.')
        if find.status != ScoutingFind.STATUS_OFFERED:
            raise ScoutingError('Auf diesen Fund kann nicht mehr geboten werden.')
        if player.club_id is not None or player.pool_status != Player.POOL_STATUS_SCOUTABLE:
            raise ScoutingError('Dieser Spieler ist nicht mehr verfügbar.')
        if amount < find.min_bid:
            raise ScoutingError('Das Gebot liegt unter dem Mindestgebot.')

        window_date = window_for_bid(today)
        season_id = get_current_tm_season_id(today)

        if ScoutingBid.objects.filter(
            club=club, player=player, window_date=window_date, status=ScoutingBid.STATUS_ACTIVE,
        ).exists():
            raise ScoutingError('Für diesen Spieler liegt bereits ein aktives Gebot vor.')

        if available_budget(club) < amount:
            raise ScoutingError('Das verfügbare Budget reicht für dieses Gebot nicht aus.')

        limit = department.effective_squad_limit(club)
        if current_squad_count(club) + reserved_slots(club) + 1 > limit:
            raise ScoutingError('Das Kaderlimit ist erreicht – kein freier Kaderplatz.')

        coin_earmarked = False
        if commitment_used(club, season_id) >= BASE_COMMITMENT_SLOTS:
            coin = None
            if manager is not None:
                coin, _ = HoenessCoin.objects.select_for_update().get_or_create(manager=manager)
            have = coin.amount if coin else 0
            if have - coin_earmarked_count(manager, season_id) <= 0:
                raise ScoutingError(
                    'Verpflichtungslimit erreicht. Für ein weiteres Gebot wird ein Hoeneß-Coin benötigt.'
                )
            coin_earmarked = True

        bid = ScoutingBid.objects.create(
            club=club, manager=manager, player=player, find=find,
            amount=amount, min_bid=find.min_bid,
            window_date=window_date, season_id=season_id,
            coin_earmarked=coin_earmarked, status=ScoutingBid.STATUS_ACTIVE,
        )

        find.status = ScoutingFind.STATUS_CHOSEN
        find.save(update_fields=['status'])
        assignment.finds.exclude(pk=find.pk).filter(
            status=ScoutingFind.STATUS_OFFERED,
        ).update(status=ScoutingFind.STATUS_EXPIRED)
        assignment.status = ScoutingAssignment.STATUS_COMPLETED
        assignment.save(update_fields=['status'])

        _upsert_watchlist(manager, player, 'bid')
    return bid


def withdraw_bid(bid):
    from game.models import ScoutingBid, WatchlistEntry
    with transaction.atomic():
        bid = ScoutingBid.objects.select_for_update().get(pk=bid.pk)
        if bid.status != ScoutingBid.STATUS_ACTIVE:
            raise ScoutingError('Nur aktive Gebote können zurückgezogen werden.')
        bid.status = ScoutingBid.STATUS_CANCELLED
        bid.save(update_fields=['status'])
        if bid.manager_id:
            WatchlistEntry.objects.filter(
                manager_id=bid.manager_id, player_id=bid.player_id, status='bid',
            ).update(status='watched')
    return bid


# ── Zuschlagstermin auflösen ─────────────────────────────────────────────────
def _format_eur(amount):
    try:
        v = int(round(float(amount)))
    except (TypeError, ValueError):
        return '—'
    return f'{v:,}'.replace(',', '.') + ' €'


def _emit_settlement_news(bid, player, won, today):
    """Erzeugt eine Vereinsnews-Meldung über das aufgelöste Scouting-Gebot."""
    from game.models import ClubNewsItem
    if not bid.club_id:
        return
    name = _player_name(player)
    amount = _format_eur(bid.amount)
    if won:
        title = f'Scouting-Coup: {name} für {amount} verpflichtet'
    else:
        title = f'Scouting-Gebot für {name} ({amount}) nicht erfolgreich'
    ClubNewsItem.objects.create(
        club_id=bid.club_id,
        title=title[:160],
        published_at=today,
    )


def _settle_loss(bid, today):
    from game.models import ScoutingBid
    bid.status = ScoutingBid.STATUS_LOST
    bid.settled_on = today
    bid.save(update_fields=['status', 'settled_on'])
    _upsert_watchlist(bid.manager, bid.player, 'lost')
    _emit_settlement_news(bid, bid.player, won=False, today=today)


def _settle_win(bid, today):
    from game.models import (
        Club, Player, ScoutingBid, HoenessCoin, CoinTransaction,
    )
    player = Player.objects.select_for_update().get(pk=bid.player_id)
    if player.club_id is not None or player.pool_status != Player.POOL_STATUS_SCOUTABLE:
        _settle_loss(bid, today)
        return False

    # Coin-belegte Gebote dürfen nur gewinnen, wenn beim Zuschlag wirklich ein
    # Coin verbraucht werden kann; sonst Verlust (kein Gratis-Transfer am Limit).
    coin = None
    if bid.coin_earmarked and bid.manager_id:
        coin = HoenessCoin.objects.select_for_update().filter(manager_id=bid.manager_id).first()
        if not coin or coin.amount <= 0:
            _settle_loss(bid, today)
            return False

    club = Club.objects.select_for_update().get(pk=bid.club_id)

    club.budget = (club.budget or Decimal('0.00')) - bid.amount
    club.save(update_fields=['budget'])
    log_club_transaction(
        club, 'transfer_ausgabe',
        f'Scouting-Transfer: {_player_name(player)}',
        -bid.amount, date=today,
    )

    mv = player.market_value if player.market_value is not None else bid.amount
    player.club = club
    player.pool_status = Player.POOL_STATUS_NONE
    player.salary_per_match = (Decimal(mv) / Decimal('1000000')) * Decimal('5000')
    player.save(update_fields=['club', 'pool_status', 'salary_per_match'])

    coin_used = False
    if coin is not None:  # nur gesetzt, wenn coin_earmarked und amount > 0 (oben geprüft)
        coin.amount -= 1
        coin.save(update_fields=['amount'])
        CoinTransaction.objects.create(
            manager_id=bid.manager_id, amount=-1,
            reason=CoinTransaction.REASON_SCOUT_TALENT,
            description=f'Scouting-Verpflichtung {_player_name(player)}',
        )
        coin_used = True

    bid.status = ScoutingBid.STATUS_WON
    bid.coin_used = coin_used
    bid.settled_on = today
    bid.save(update_fields=['status', 'coin_used', 'settled_on'])
    _upsert_watchlist(bid.manager, player, 'won')
    _emit_settlement_news(bid, player, won=True, today=today)
    return True


def resolve_due_windows(today=None):
    """Wertet alle fälligen Zuschlagstermine aus (höchstes Gebot gewinnt)."""
    from game.models import ScoutingBid
    today = _today(today)
    summary = {'windows': 0, 'won': 0, 'lost': 0}

    with transaction.atomic():
        due_dates = sorted(set(
            ScoutingBid.objects
            .filter(status=ScoutingBid.STATUS_ACTIVE, window_date__lte=today)
            .values_list('window_date', flat=True)
        ))
        for window_date in due_dates:
            summary['windows'] += 1
            bids = list(
                ScoutingBid.objects
                .select_for_update()
                .filter(status=ScoutingBid.STATUS_ACTIVE, window_date=window_date)
                .order_by('created_at')
            )
            by_player = {}
            for b in bids:
                by_player.setdefault(b.player_id, []).append(b)

            for plist in by_player.values():
                # höchstes Gebot gewinnt; bei Gleichstand das früher abgegebene
                winner = sorted(plist, key=lambda b: (-b.amount, b.created_at))[0]
                for b in plist:
                    if b.pk == winner.pk:
                        if _settle_win(b, today):
                            summary['won'] += 1
                        else:
                            summary['lost'] += 1
                    else:
                        _settle_loss(b, today)
                        summary['lost'] += 1
    return summary


# ── Community ────────────────────────────────────────────────────────────────
def _get_or_create_network(iso2):
    from game.models import CountryNetwork
    iso2 = (iso2 or '').upper()
    rec = COUNTRIES.get(iso2, {})
    net, _ = CountryNetwork.objects.get_or_create(
        iso2=iso2,
        defaults={
            'name': rec.get('name', iso2),
            'continent': rec.get('continent', ''),
            'region': rec.get('region', ''),
        },
    )
    return net


def submit_community_profile(manager, iso2, tm_url, player_name='', today=None):
    from game.models import CommunitySubmission, CountryNetwork
    today = _today(today)
    iso2 = (iso2 or '').upper()
    if iso2 not in COUNTRIES:
        raise ScoutingError('Dieses Land wird derzeit nicht unterstützt.')

    network = _get_or_create_network(iso2)
    if network.is_paused:
        raise ScoutingError('Einreichungen für dieses Land sind derzeit pausiert.')

    week_key = _week_key(today)
    with transaction.atomic():
        week_total = CommunitySubmission.objects.filter(manager=manager, week_key=week_key).count()
        if week_total >= COMMUNITY_WEEKLY_LIMIT:
            raise ScoutingError('Dein Wochenlimit an Einreichungen ist erreicht.')
        country_total = CommunitySubmission.objects.filter(
            manager=manager, week_key=week_key, iso2=iso2,
        ).count()
        if country_total >= COMMUNITY_COUNTRY_WEEK_CAP:
            raise ScoutingError('Für dieses Land hast du diese Woche bereits genug eingereicht.')

        submission = CommunitySubmission.objects.create(
            manager=manager, iso2=iso2, tm_url=tm_url,
            player_name=player_name or '', week_key=week_key,
            status=CommunitySubmission.STATUS_PENDING,
        )
        net = CountryNetwork.objects.select_for_update().get(pk=network.pk)
        net.activity_points = (net.activity_points or 0) + COMMUNITY_ACTIVITY_POINTS
        net.save(update_fields=['activity_points', 'updated_at'])
    return submission


def moderate_submission(submission, approve):
    from game.models import CommunitySubmission, CountryNetwork
    with transaction.atomic():
        submission = CommunitySubmission.objects.select_for_update().get(pk=submission.pk)
        if submission.status != CommunitySubmission.STATUS_PENDING:
            raise ScoutingError('Diese Einreichung wurde bereits bearbeitet.')
        network = _get_or_create_network(submission.iso2)
        if approve:
            submission.status = CommunitySubmission.STATUS_APPROVED
            net = CountryNetwork.objects.select_for_update().get(pk=network.pk)
            net.community_points = (net.community_points or 0) + COMMUNITY_APPROVE_POINTS
            net.save(update_fields=['community_points', 'updated_at'])
        else:
            submission.status = CommunitySubmission.STATUS_REJECTED
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=['status', 'reviewed_at'])
    return submission
