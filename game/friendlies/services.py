"""Transactional lifecycle and simulation orchestration for friendly fixtures."""

from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
import logging
import uuid

from game.models import (
    Club,
    CupFixture,
    FriendlyFixture,
    Player,
    Referee,
    SeasonFixture,
    SimulatedMatch,
)
from game.notifications import notify_club

logger = logging.getLogger(__name__)


def get_squad(club, scope='pro'):
    """Return eligible players for a squad context (U21 is an extension point)."""
    if scope == FriendlyFixture.SQUAD_U21:
        return Player.objects.none()
    if scope != FriendlyFixture.SQUAD_PRO:
        raise ValidationError('Unbekannter Kader-Kontext.')
    return Player.objects.filter(
        club=club, ws_injury_days_remaining=0,
    ).order_by('id')


def _clubs_for_fixture(fixture):
    if not fixture.target_club_id:
        return []
    return [fixture.sender_club, fixture.target_club]


def _collision(club, kickoff_at, scope, exclude=None):
    # Community tournament matches share the same squad-context collision
    # window, while remaining outside the global calendar.
    from game.models import CommunityTournamentMatch
    tournament_matches = CommunityTournamentMatch.objects.filter(
        Q(home_entry__club=club) | Q(away_entry__club=club),
        round__phase__tournament__squad_scope=scope,
        friendly_fixture__status__in=[
            FriendlyFixture.STATUS_PLANNED, FriendlyFixture.STATUS_RUNNING,
        ],
        scheduled_at__gt=kickoff_at - timedelta(hours=3),
        scheduled_at__lt=kickoff_at + timedelta(hours=3),
    )
    if exclude and getattr(exclude, 'pk', None):
        if isinstance(exclude, FriendlyFixture):
            tournament_matches = tournament_matches.exclude(friendly_fixture_id=exclude.pk)
        else:
            tournament_matches = tournament_matches.exclude(pk=exclude.pk)
    if tournament_matches.exists():
        return True
    if CupFixture.objects.filter(
        Q(home_club=club) | Q(away_club=club),
        status=CupFixture.STATUS_SCHEDULED,
        cup_round__scheduled_date=kickoff_at.date(),
    ).exists():
        return True
    season_fixtures = SeasonFixture.objects.filter(
        Q(home_club=club) | Q(away_club=club),
        is_played=False,
        scheduled_date=kickoff_at.date(),
    ).values_list('scheduled_date', 'scheduled_time')
    for scheduled_date, scheduled_time in season_fixtures:
        if scheduled_time is None:
            return True
        scheduled_at = timezone.make_aware(
            datetime.combine(scheduled_date, scheduled_time)
        )
        if abs(scheduled_at - kickoff_at) < timedelta(hours=3):
            return True
    qs = FriendlyFixture.objects.filter(
        Q(sender_club=club) | Q(target_club=club),
        status__in=[FriendlyFixture.STATUS_PLANNED, FriendlyFixture.STATUS_RUNNING],
        kickoff_at__gt=kickoff_at - timedelta(hours=3),
        kickoff_at__lt=kickoff_at + timedelta(hours=3),
        squad_scope=scope,
    )
    if exclude:
        qs = qs.exclude(pk=exclude.pk)
    return qs.exists()


def _validate_fixture(fixture, clubs):
    if fixture.kickoff_at <= timezone.now():
        raise ValidationError('Der Spieltermin muss in der Zukunft liegen.')
    if fixture.penalties_after_90 and (not fixture.penalties or fixture.extra_time):
        raise ValidationError('Elfmeter nach 90 erfordern Elfmeterschießen ohne Verlängerung.')
    if fixture.squad_scope == FriendlyFixture.SQUAD_U21:
        # Deliberately report the actual count, including the empty U21 contract.
        counts = [(club, get_squad(club, fixture.squad_scope).count()) for club in clubs]
    else:
        counts = [(club, get_squad(club, fixture.squad_scope).count()) for club in clubs]
    short = [(club.name, count) for club, count in counts if count < 11]
    if short:
        raise ValidationError('; '.join(
            f'{name}: nur {count} von 11 benötigten einsatzfähigen Spielern'
            for name, count in short
        ))
    for club in clubs:
        if _collision(club, fixture.kickoff_at, fixture.squad_scope, fixture):
            raise ValidationError('Zu diesem Zeitpunkt findet bereits eine Spielsimulation statt.')


def _season():
    from game.models import GameSeasonState
    state = GameSeasonState.objects.order_by('-id').first()
    return str(state.current_season if state else 0)


def _notify_after_commit(clubs, title, body):
    for club in clubs:
        transaction.on_commit(lambda club=club: notify_club(club, title, body))


@transaction.atomic
def create_directed_request(*, sender_club, target_club, kickoff_at, squad_scope='pro',
                            venue_type='heim', neutral_stadium=None, extra_time=False,
                            penalties=False, penalties_after_90=False, comment=''):
    if sender_club.pk == target_club.pk:
        raise ValidationError('Ein Verein kann nicht gegen sich selbst spielen.')
    fixture = FriendlyFixture(
        sender_club=sender_club, target_club=target_club, kickoff_at=kickoff_at,
        squad_scope=squad_scope, venue_type=venue_type, neutral_stadium=neutral_stadium,
        extra_time=extra_time, penalties=penalties, penalties_after_90=penalties_after_90,
        comment=comment, season=_season(),
        status=FriendlyFixture.STATUS_PLANNED if target_club.managed_by_id is None
        else FriendlyFixture.STATUS_REQUESTED,
    )
    if fixture.status == FriendlyFixture.STATUS_PLANNED:
        list(Club.objects.select_for_update().filter(
            pk__in=[sender_club.pk, target_club.pk],
        ).order_by('pk'))
        _validate_fixture(fixture, [sender_club, target_club])
    fixture.full_clean()
    fixture.save()
    _notify_after_commit([target_club], 'Neue Freundschaftsspiel-Anfrage',
                         f'{sender_club.name} hat dich für den {kickoff_at:%d.%m.%Y %H:%M} angefragt.')
    return fixture


@transaction.atomic
def accept_request(fixture_id, club):
    fixture = FriendlyFixture.objects.select_for_update(of=('self',)).select_related(
        'sender_club', 'target_club').get(pk=fixture_id)
    if fixture.target_club_id != club.pk or fixture.status != FriendlyFixture.STATUS_REQUESTED:
        raise ValidationError('Diese Anfrage kann nicht angenommen werden.')
    list(Club.objects.select_for_update().filter(
        pk__in=[fixture.sender_club_id, fixture.target_club_id],
    ).order_by('pk'))
    _validate_fixture(fixture, [fixture.sender_club, fixture.target_club])
    fixture.status = FriendlyFixture.STATUS_PLANNED
    fixture.save(update_fields=['status'])
    _notify_after_commit([fixture.sender_club], 'Freundschaftsspiel angenommen', 'Deine Anfrage wurde angenommen.')
    return fixture


@transaction.atomic
def decline_request(fixture_id, club):
    fixture = FriendlyFixture.objects.select_for_update().get(pk=fixture_id)
    if fixture.target_club_id != club.pk or fixture.status != FriendlyFixture.STATUS_REQUESTED:
        raise ValidationError('Diese Anfrage kann nicht abgelehnt werden.')
    fixture.status = FriendlyFixture.STATUS_DECLINED
    fixture.resolved_at = timezone.now()
    fixture.save(update_fields=['status', 'resolved_at'])
    _notify_after_commit([fixture.sender_club], 'Freundschaftsspiel abgelehnt', 'Deine Anfrage wurde abgelehnt.')
    return fixture


@transaction.atomic
def withdraw_request(fixture_id, club):
    fixture = FriendlyFixture.objects.select_for_update().get(pk=fixture_id)
    if fixture.sender_club_id != club.pk or fixture.status != FriendlyFixture.STATUS_REQUESTED:
        raise ValidationError('Diese Anfrage kann nicht zurückgezogen werden.')
    fixture.status = FriendlyFixture.STATUS_WITHDRAWN
    fixture.resolved_at = timezone.now()
    fixture.save(update_fields=['status', 'resolved_at'])
    return fixture


@transaction.atomic
def create_marketplace_offer(**kwargs):
    kwargs['target_club'] = None
    fixture = FriendlyFixture(status=FriendlyFixture.STATUS_REQUESTED, season=_season(), **kwargs)
    if fixture.kickoff_at <= timezone.now():
        raise ValidationError('Der Spieltermin muss in der Zukunft liegen.')
    fixture.full_clean()
    fixture.save()
    return fixture


@transaction.atomic
def accept_marketplace_offer(fixture_id, club):
    fixture = FriendlyFixture.objects.select_for_update().select_related('sender_club').get(pk=fixture_id)
    if fixture.status != FriendlyFixture.STATUS_REQUESTED or fixture.target_club_id:
        raise ValidationError('Diese Partie wurde bereits vergeben.')
    if fixture.sender_club_id == club.pk or club.managed_by_id is None:
        raise ValidationError('Nur ein anderer Managerverein kann dieses Inserat annehmen.')
    list(Club.objects.select_for_update().filter(
        pk__in=[fixture.sender_club_id, club.pk],
    ).order_by('pk'))
    fixture.target_club = club
    _validate_fixture(fixture, [fixture.sender_club, club])
    fixture.status = FriendlyFixture.STATUS_PLANNED
    fixture.save(update_fields=['target_club', 'status'])
    _notify_after_commit([fixture.sender_club], 'Inserat angenommen', f'{club.name} spielt die Partie.')
    return fixture


def simulate_fixture(fixture_id):
    claim = uuid.uuid4()
    with transaction.atomic():
        fixture = FriendlyFixture.objects.select_for_update(of=('self',)).select_related(
            'sender_club', 'target_club').get(pk=fixture_id)
        if fixture.status == FriendlyFixture.STATUS_PLAYED:
            return fixture
        if fixture.status != FriendlyFixture.STATUS_PLANNED:
            return fixture
        fixture.status = FriendlyFixture.STATUS_RUNNING
        fixture.simulation_claimed_at = timezone.now()
        fixture.simulation_claim = claim
        fixture.save(update_fields=[
            'status', 'simulation_claimed_at', 'simulation_claim',
        ])
    from game.story_release import friendly_round, refresh_barrier
    story_round = friendly_round(fixture)
    clubs = _clubs_for_fixture(fixture)
    if len(clubs) != 2:
        FriendlyFixture.objects.filter(
            pk=fixture.pk,
            status=FriendlyFixture.STATUS_RUNNING,
            simulation_claim=claim,
        ).update(
            status=FriendlyFixture.STATUS_NOT_PLAYED,
            resolved_at=timezone.now(),
            simulation_claimed_at=None,
            simulation_claim=None,
        )
        refresh_barrier(story_round.pk, fixture.pk)
        return FriendlyFixture.objects.get(pk=fixture.pk)
    if min(get_squad(c, fixture.squad_scope).count() for c in clubs) < 11:
        FriendlyFixture.objects.filter(
            pk=fixture.pk,
            status=FriendlyFixture.STATUS_RUNNING,
            simulation_claim=claim,
        ).update(
            status=FriendlyFixture.STATUS_NOT_PLAYED,
            resolved_at=timezone.now(),
            simulation_claimed_at=None,
            simulation_claim=None,
        )
        refresh_barrier(story_round.pk, fixture.pk)
        return FriendlyFixture.objects.get(pk=fixture.pk)
    home, away = (
        [clubs[1], clubs[0]]
        if fixture.offered_role == FriendlyFixture.VENUE_AWAY
        else clubs
    )
    from game.match_engine import simulate_match
    from game.weather_service import roll_weather
    from game.match_story.django_bridge import tactic_snapshot, simulation_story

    try:
        weather_type, temperature = roll_weather(fixture.kickoff_at.date())
        report = simulate_match(home, away, tactic_context='freundschaft',
                                squad_scope=fixture.squad_scope,
                                extra_time=fixture.extra_time, penalties=fixture.penalties,
                                 penalties_after_90=fixture.penalties_after_90,
                                  neutral_venue=fixture.venue_type == FriendlyFixture.VENUE_NEUTRAL,
                                 weather={'type': weather_type, 'temperature': temperature})
        report['weather'] = {'type': weather_type, 'temperature': temperature}
        report['friendly_sandbox'] = True
        report['neutral_venue'] = fixture.venue_type == FriendlyFixture.VENUE_NEUTRAL
        report['attendance_preview'] = _attendance_preview(fixture, home, away)
        # The report may describe match incidents, but no injury or fatigue
        # mutation is persisted for a friendly.
        referee = Referee.objects.order_by('?').first()
        with transaction.atomic():
            match = SimulatedMatch.create_numbered(
                season=fixture.season, home_club=home, away_club=away,
                home_goals=report.get('home_goals', 0),
                away_goals=report.get('away_goals', 0),
                report_data=report, match_type='freundschaft', referee=referee,
                story_round=story_round, story_source_key=str(fixture.pk),
                story_tactic_snapshot=tactic_snapshot(
                    home, away, context='freundschaft', squad_scope=fixture.squad_scope))
            updated = FriendlyFixture.objects.filter(
                pk=fixture.pk,
                status=FriendlyFixture.STATUS_RUNNING,
                simulation_claim=claim,
                simulated_match__isnull=True,
            ).update(
                status=FriendlyFixture.STATUS_PLAYED,
                simulated_match=match,
                resolved_at=timezone.now(),
                simulation_claimed_at=None,
                simulation_claim=None,
                simulation_attempts=0,
                next_simulation_attempt_at=None,
                simulation_last_error='',
            )
            if not updated:
                match.delete()
            else:
                simulation_story(match)
                # Result-bearing notifications are sent only after round release.
    except Exception as exc:
        attempts = fixture.simulation_attempts + 1
        terminal = attempts >= 3
        FriendlyFixture.objects.filter(
            pk=fixture.pk,
            status=FriendlyFixture.STATUS_RUNNING,
            simulation_claim=claim,
            simulated_match__isnull=True,
        ).update(
            status=(
                FriendlyFixture.STATUS_NOT_PLAYED
                if terminal else FriendlyFixture.STATUS_PLANNED
            ),
            resolved_at=timezone.now() if terminal else None,
            simulation_claimed_at=None,
            simulation_claim=None,
            simulation_attempts=attempts,
            next_simulation_attempt_at=(
                None
                if terminal
                else timezone.now() + timedelta(minutes=5 * (2 ** (attempts - 1)))
            ),
            simulation_last_error=str(exc)[:500],
        )
        if terminal:
            refresh_barrier(story_round.pk, fixture.pk)
        raise
    return FriendlyFixture.objects.get(pk=fixture.pk)


def _attendance_preview(fixture, home, away):
    if fixture.venue_type == FriendlyFixture.VENUE_NEUTRAL:
        return {
            'neutral': True,
            'venue': str(fixture.neutral_stadium),
            'capacity': fixture.neutral_stadium.capacity,
            'zuschauer_gesamt': fixture.neutral_stadium.capacity,
            'auslastung_pct': 100.0,
            'kategorien': {},
        }
    # Spielortwerte sind aus Sicht des Inserenten/Anfragenden gespeichert und
    # bleiben unabhängig von der angebotenen sportlichen Heim-/Gastrolle.
    venue_club = (
        fixture.sender_club
        if fixture.venue_type == FriendlyFixture.VENUE_HOME
        else fixture.target_club
    )
    if venue_club is None:
        return {}
    try:
        stadium = venue_club.stadium
    except Exception:
        return {}
    from game.economy.stadium import compute_demand
    demand = compute_demand(
        venue_club,
        stadium,
        opponent_club=away if venue_club.pk == home.pk else home,
        saison=fixture.season,
    )
    demand['neutral'] = False
    demand['venue'] = stadium.name
    # Preview only: deliberately discard monetary totals to avoid presenting
    # them as a booking.
    demand.pop('einnahmen_gesamt', None)
    for row in demand['kategorien'].values():
        row.pop('einnahmen', None)
    return _jsonable(demand)


def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def run_tick(now=None):
    now = now or timezone.now()
    from game.story_publication import publish_due_results
    publish_due_results(now)
    FriendlyFixture.objects.filter(
        status=FriendlyFixture.STATUS_RUNNING,
        simulation_claimed_at__lt=now - timedelta(minutes=15),
        simulated_match__isnull=True,
    ).update(
        status=FriendlyFixture.STATUS_PLANNED,
        simulation_claimed_at=None,
        simulation_claim=None,
    )
    expired = FriendlyFixture.objects.filter(status=FriendlyFixture.STATUS_REQUESTED, kickoff_at__lte=now).update(
        status=FriendlyFixture.STATUS_EXPIRED, resolved_at=now)
    processed = 0
    due = FriendlyFixture.objects.filter(
        Q(next_simulation_attempt_at__isnull=True)
        | Q(next_simulation_attempt_at__lte=now),
        status=FriendlyFixture.STATUS_PLANNED,
        kickoff_at__lte=now,
    ).order_by('kickoff_at', 'pk').values_list('pk', flat=True)
    for fixture_id in due:
        try:
            simulate_fixture(fixture_id)
            processed += 1
        except Exception:
            logger.exception(
                'Freundschaftsspiel %s konnte nicht simuliert werden; '
                'der Tick fährt mit der nächsten Partie fort.',
                fixture_id,
            )
    # Tournament progression is deliberately a second, idempotent pass: the
    # friendly simulator remains the sole owner of match simulation.
    tournament_processed = 0
    try:
        from game.friendlies.tournaments import (
            advance_due_tournaments, cleanup_orphaned_tournaments,
        )
        tournament_processed = advance_due_tournaments(now)
        cleanup_orphaned_tournaments(now)
    except Exception:
        logger.exception('Turnierfortschreibung im Freundschafts-Tick fehlgeschlagen.')
    return {'expired': expired, 'processed': processed,
            'tournaments': tournament_processed}


@transaction.atomic
def cleanup_season(season):
    """Delete every friendly lifecycle row and report for an old season."""
    from game.friendlies.tournaments import cleanup_season as cleanup_tournaments
    cleanup_tournaments(season)
    fixtures = FriendlyFixture.objects.select_for_update().filter(season=str(season))
    match_ids = list(
        fixtures.exclude(simulated_match_id=None)
        .values_list('simulated_match_id', flat=True)
    )
    fixture_count = fixtures.count()
    fixtures.delete()
    deleted_matches, _ = SimulatedMatch.objects.filter(
        pk__in=match_ids,
        match_type='freundschaft',
    ).delete()
    # Also remove legacy/manual friendly reports that are not linked to a
    # lifecycle row but belong to the old season.
    legacy_matches, _ = SimulatedMatch.objects.filter(
        season=str(season),
        match_type='freundschaft',
    ).delete()
    return {
        'fixtures': fixture_count,
        'matches': deleted_matches + legacy_matches,
    }