"""Durable, idempotent system events for manager timelines.

This module is deliberately separate from the profile presentation code.  A
system event is an ordinary ``ManagerTimelineEntry`` with an explicit source,
so manual moderation keeps working unchanged while replayed season/backfill
jobs remain safe.
"""

import logging

from django.db import IntegrityError, transaction
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

CAREER_END_TITLES = {
    'resign': 'Rücktritt',
    'fired': 'Entlassung',
    'mutual': 'Einvernehmliche Trennung',
    'season_end': 'Amtszeit beendet',
    None: 'Amtszeit beendet',
    '': 'Amtszeit beendet',
}


def _system_entry_defaults(**values):
    values.update(system_entry=True, status='approved')
    return values


def _get_or_create_system_entry(source_type, source_key, defaults):
    """Create one source entry, also tolerating concurrent replay."""
    from .models import ManagerTimelineEntry

    lookup = {'source_type': source_type, 'source_key': source_key}
    try:
        entry, created = ManagerTimelineEntry.objects.get_or_create(
            **lookup,
            defaults=_system_entry_defaults(**defaults),
        )
    except IntegrityError:
        entry = ManagerTimelineEntry.objects.get(**lookup)
        created = False
    return entry, created


def create_career_end_event(career_entry):
    """Materialize the one event belonging to a completed career entry."""
    if not career_entry or not career_entry.ended_at:
        return None
    reason = career_entry.end_reason
    source_key = f'career_end:{career_entry.pk}'
    from .models import ManagerTimelineEntry

    # Older inactivity code created an un-sourced approved dismissal. Adopt
    # that row instead of exposing a duplicate when it is encountered.
    legacy = ManagerTimelineEntry.objects.filter(
        manager_id=career_entry.manager_id,
        club_id=career_entry.club_id,
        event_date=career_entry.ended_at,
        category='status',
        title=CAREER_END_TITLES.get(reason, 'Amtszeit beendet'),
        system_entry=False,
    ).filter(status=ManagerTimelineEntry.STATUS_APPROVED).first()
    if legacy:
        legacy.system_entry = True
        legacy.source_type = 'career_end'
        legacy.source_key = source_key
        legacy.save(update_fields=['system_entry', 'source_type', 'source_key'])
        return legacy

    return _get_or_create_system_entry(
        'career_end',
        source_key,
        {
            'manager_id': career_entry.manager_id,
            'club_id': career_entry.club_id,
            'club_name': career_entry.club.name,
            'event_date': career_entry.ended_at,
            'category': 'status',
            'title': CAREER_END_TITLES.get(reason, 'Amtszeit beendet'),
            'body': f'{career_entry.club.name} · Amtsende',
        },
    )[0]


def finish_manager_career(manager, club=None, ended_at=None, reason=None):
    """Close the active office and create its durable status event."""
    ended_at = ended_at or timezone.localdate()
    from .models import ManagerCareerEntry

    with transaction.atomic():
        qs = ManagerCareerEntry.objects.select_for_update().filter(
            manager=manager, active=True,
        )
        if club is not None:
            qs = qs.filter(club=club)
        entry = qs.order_by('-started_at', '-pk').first()
        if entry is None:
            return None
        entry.active = False
        entry.ended_at = ended_at
        entry.end_reason = reason
        entry.save(update_fields=['active', 'ended_at', 'end_reason'])
        create_career_end_event(entry)
        return entry


def _manager_at_date(club_id, event_date):
    """Resolve one unambiguous manager tenure covering an historical date."""
    from .models import ManagerCareerEntry

    matches = list(
        ManagerCareerEntry.objects.filter(
            club_id=club_id,
            started_at__lte=event_date,
        ).filter(
            models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=event_date)
        ).values_list('manager_id', flat=True).distinct()[:2]
    )
    return matches[0] if len(matches) == 1 else None


def _fixture_managers(fixture, event_date):
    """Return snapshotted or unambiguous match-time managers."""
    from .models import ManagerProfile

    home = getattr(fixture, 'home_manager', None)
    away = getattr(fixture, 'away_manager', None)
    if home is None and fixture.home_club_id:
        manager_id = _manager_at_date(fixture.home_club_id, event_date)
        home = ManagerProfile.objects.filter(pk=manager_id).first()
    if away is None and fixture.away_club_id:
        manager_id = _manager_at_date(fixture.away_club_id, event_date)
        away = ManagerProfile.objects.filter(pk=manager_id).first()
    return home, away


def create_final_events(fixture):
    """Create winner and loser cards after an authoritative final completion."""
    if not fixture or fixture.status != fixture.STATUS_PLAYED:
        return []
    cup_round = fixture.cup_round
    if cup_round.round_code != 'final' or not fixture.winner_club_id:
        return []
    cup_season = cup_round.cup_season
    if (
        cup_round.status != cup_round.STATUS_COMPLETED
        or cup_season.status != cup_season.STATUS_COMPLETED
        or cup_season.winner_club_id != fixture.winner_club_id
    ):
        logger.warning('Finale %s übersprungen: Wettbewerb nicht abgeschlossen.', fixture.pk)
        return []
    if not fixture.home_club_id or not fixture.away_club_id:
        return []

    event_date = cup_round.scheduled_date
    if event_date is None and fixture.simulated_match_id:
        event_date = fixture.simulated_match.simulated_at.date()
    if event_date is None:
        logger.warning('Finale %s übersprungen: Spieldatum fehlt.', fixture.pk)
        return []
    home_manager, away_manager = _fixture_managers(fixture, event_date)
    if not home_manager or not away_manager:
        logger.warning(
            'Finale %s übersprungen: eindeutige Managerzuordnung fehlt.',
            fixture.pk,
        )
        return []

    winner_id = fixture.winner_club_id
    competition = cup_season.competition
    competition_name = competition.name
    score = fixture.score_display
    home_name = fixture.home_club.name
    away_name = fixture.away_club.name
    title = f'Finale {competition_name}'[:120]
    result = []
    for club, opponent, manager in (
        (fixture.home_club, fixture.away_club, home_manager),
        (fixture.away_club, fixture.home_club, away_manager),
    ):
        won = club.pk == winner_id
        body = f'{home_name} {score} {away_name}'
        entry, _ = _get_or_create_system_entry(
            'cup_final',
            f'cup_final:{fixture.pk}:manager:{manager.pk}',
            {
                'manager_id': manager.pk,
                'club_id': club.pk,
                'club_name': club.name,
                'event_date': event_date,
                'category': 'finale',
                'title': title,
                'body': body,
                'result_text': score,
                'opponent_name': opponent.name,
                'competition_name': competition_name,
                'show_trophy': won,
                'tone_override': 'gold' if won else 'red',
                'cup_fixture_id': fixture.pk,
            },
        )
        result.append(entry)
    return result


def create_first_youth_promotion_event(
    manager, player, club, promotion_date=None, age=None,
):
    """Record an explicitly confirmed youth-to-pro promotion.

    There is currently no persisted promotion transition in the game.  This
    function is therefore an opt-in hook for the authoritative transition
    path, rather than inferring one from a player's age or current club.
    """
    with transaction.atomic():
        promotion_date = promotion_date or timezone.localdate()
        if age is None:
            age = player.age
        source_key = f'youth_promotion:{manager.pk}:first'
        entry, created = _get_or_create_system_entry(
            'youth_promotion',
            source_key,
            {
                'manager_id': manager.pk,
                'club_id': club.pk if club else None,
                'club_name': club.name if club else '',
                'event_date': promotion_date,
                'category': 'jugend',
                'title': 'Talentschmied',
                'body': (
                    f'{player.full_name} · {age} Jahre · '
                    f'{club.name if club else "Verein"}'
                ),
                'player_id': player.pk,
                'tone_override': 'green',
            },
        )
        if created:
            from .manager_profile import evaluate_titles
            from .models import ManagerProfile

            locked_manager = ManagerProfile.objects.select_for_update().get(
                pk=manager.pk
            )
            progress = dict(locked_manager.title_progress or {})
            progress['jugendspieler_hochgezogen'] = max(
                1, int(progress.get('jugendspieler_hochgezogen') or 0)
            )
            locked_manager.title_progress = progress
            locked_manager.save(update_fields=['title_progress'])
            evaluate_titles(locked_manager)
        return entry
