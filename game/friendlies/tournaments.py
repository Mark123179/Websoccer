"""Community tournament domain service.

Tournament matches deliberately remain ordinary :class:`FriendlyFixture`
rows.  This module only owns the tournament state machine and never writes
friendly statistics or player state.
"""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import logging

from game.models import (
    Club, CommunityTournament, CommunityTournamentApplication,
    CommunityTournamentEntry, CommunityTournamentMatch,
    CommunityTournamentPhase, CommunityTournamentRound,
    CommunityTournamentStanding, FriendlyFixture, FinanceTransaction,
)
from game.notifications import notify_club

logger = logging.getLogger(__name__)


def _is_standings_match(match):
    tournament = match.round.phase.tournament
    if tournament.format == CommunityTournament.FORMAT_LEAGUE:
        return True
    if tournament.format != CommunityTournament.FORMAT_GROUP_KO:
        return False
    if match.round.number > 3:
        return False
    groups = [entry.group for entry in (match.home_entry, match.away_entry)
              if entry and entry.group]
    return bool(groups and len(set(groups)) == 1)


def _safe_notify(club, title, body):
    try:
        notify_club(club, title, body)
    except Exception:
        logger.exception('Turnierbenachrichtigung fehlgeschlagen für Verein %s', getattr(club, 'pk', None))


def candidate_schedule_conflicts(club, tournament, *, exclude_entry=False):
    """Return the first collision against every published tournament slot."""
    from game.friendlies.services import _collision
    for value in tournament.schedule or []:
        value = value.get('kickoff_at') if isinstance(value, dict) else value
        parsed = _schedule_value(type('Schedule', (), {'schedule': [value]})(), 0)
        if _collision(club, parsed, tournament.squad_scope):
            return True
        for other in CommunityTournament.objects.filter(
                status__in=[CommunityTournament.STATUS_OPEN, CommunityTournament.STATUS_RUNNING],
                squad_scope=tournament.squad_scope).exclude(pk=tournament.pk):
            if other.entries.filter(club=club).exists():
                for other_value in other.schedule or []:
                    other_value = (other_value.get('kickoff_at')
                                   if isinstance(other_value, dict) else other_value)
                    other_time = _schedule_value(
                        type('Schedule', (), {'schedule': [other_value]})(), 0)
                    if abs(other_time - parsed) < timedelta(hours=3):
                        return True
    return False


FIELD_SIZES = {
    CommunityTournament.FORMAT_LEAGUE: (4, 6, 8, 10, 16),
    CommunityTournament.FORMAT_CUP: (4, 8, 16),
    CommunityTournament.FORMAT_GROUP_KO: (8, 16),
}


def _notify(clubs, title, body):
    for club in clubs:
        transaction.on_commit(lambda club=club: _safe_notify(club, title, body))


def _notify_completion(tournament):
    for entry in tournament.entries.select_related('club'):
        _notify([entry.club], 'Turnier abgeschlossen',
                f'{tournament.name}: Platz {entry.final_rank or "—"}')


def _notify_pairing(tournament, match):
    if not match.home_entry or not match.away_entry:
        return
    _notify([match.home_entry.club, match.away_entry.club],
            'Neue Turnierpaarung',
            f'{tournament.name}: {match.home_entry.club.name} – '
            f'{match.away_entry.club.name} ({match.scheduled_at:%d.%m.%Y %H:%M})')


def _round_count(tournament):
    n = tournament.field_size
    if tournament.format == CommunityTournament.FORMAT_LEAGUE:
        return (n - 1) * (2 if tournament.home_and_away else 1)
    if tournament.format == CommunityTournament.FORMAT_GROUP_KO:
        return 3 + (2 if n == 8 else 3)
    return (n.bit_length() - 1) * (2 if tournament.home_and_away else 1)


@transaction.atomic
def create_tournament(*, organizer, name, format, field_size, schedule,
                      description='', season=None, squad_scope='pro',
                      home_and_away=False, neutral_venue=None, access='offen',
                      invitation_code='', rules=None, reward_plan=None,
                      is_admin=False):
    if format not in FIELD_SIZES or field_size not in FIELD_SIZES[format]:
        raise ValidationError('Ungültige Feldgröße für dieses Turnierformat.')
    if not name.strip():
        raise ValidationError('Ein Turniername ist erforderlich.')
    if access == CommunityTournament.ACCESS_CODE and not invitation_code:
        raise ValidationError('Für den Zugang per Code ist ein Code erforderlich.')
    if format == CommunityTournament.FORMAT_GROUP_KO and home_and_away:
        raise ValidationError('Die Gruppenphase wird als einfache Runde gespielt.')
    if format == CommunityTournament.FORMAT_CUP and home_and_away:
        # Cup legs are supported explicitly: every leg receives its own
        # pre-announced round/date (there is no away-goals rule).
        pass
    if format in (CommunityTournament.FORMAT_CUP, CommunityTournament.FORMAT_GROUP_KO):
        if not (rules or {}).get('penalties'):
            raise ValidationError('K.o.-Regeln benötigen Elfmeterschießen.')
    schedule = list(schedule or [])
    if len(schedule) != _round_count(
        CommunityTournament(format=format, field_size=field_size,
                            home_and_away=home_and_away)
    ):
        raise ValidationError('Der vollständige Spielplan muss vor der Anmeldung feststehen.')
    parsed_schedule = []
    for value in schedule:
        if isinstance(value, dict):
            value = value.get('kickoff_at') or value.get('scheduled_at')
        from django.utils.dateparse import parse_datetime
        parsed = parse_datetime(value) if isinstance(value, str) else value
        if parsed is None:
            raise ValidationError('Spielplan enthält einen ungültigen Termin.')
        parsed = parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
        if parsed <= timezone.now():
            raise ValidationError('Alle Turniertermine müssen in der Zukunft liegen.')
        parsed_schedule.append(parsed.isoformat())
    if parsed_schedule != sorted(parsed_schedule):
        raise ValidationError('Turniertermine müssen chronologisch sortiert sein.')
    for previous, current_time in zip(parsed_schedule, parsed_schedule[1:]):
        from django.utils.dateparse import parse_datetime
        if parse_datetime(current_time) - parse_datetime(previous) < timedelta(hours=3):
            raise ValidationError('Turnierrunden müssen mindestens drei Stunden auseinanderliegen.')
    if reward_plan and not is_admin:
        raise ValidationError('Nur Administratoren dürfen Prämien festlegen.')
    current = season
    if current is None:
        from game.friendlies.services import _season
        current = _season()
    tournament = CommunityTournament.objects.create(
        organizer=organizer, name=name.strip(), description=description,
        format=format, field_size=field_size, season=str(current),
        squad_scope=squad_scope, home_and_away=home_and_away,
        neutral_venue=neutral_venue, access=access,
        invitation_code=invitation_code, rules=rules or {},
        schedule=parsed_schedule, reward_plan=reward_plan or {},
        status=CommunityTournament.STATUS_OPEN, opened_at=timezone.now(),
    )
    return tournament


@transaction.atomic
def join_tournament(tournament_id, club, *, code=''):
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament_id)
    if tournament.status != CommunityTournament.STATUS_OPEN:
        raise ValidationError('Diesem Turnier kann nicht mehr beigetreten werden.')
    if tournament.access == CommunityTournament.ACCESS_APPLICATION:
        raise ValidationError('Für dieses Turnier ist eine angenommene Bewerbung erforderlich.')
    club = Club.objects.select_for_update().get(pk=club.pk)
    if candidate_schedule_conflicts(club, tournament):
        raise ValidationError('Der Verein hat eine Terminkollision im Turnierplan.')
    if tournament.access == CommunityTournament.ACCESS_CODE and code != tournament.invitation_code:
        raise ValidationError('Der Einladungscode ist ungültig.')
    if CommunityTournamentEntry.objects.filter(tournament=tournament, club=club).exists():
        return CommunityTournamentEntry.objects.get(tournament=tournament, club=club)
    if CommunityTournamentEntry.objects.filter(tournament=tournament).count() >= tournament.field_size:
        raise ValidationError('Das Teilnehmerfeld ist bereits voll.')
    entry = CommunityTournamentEntry.objects.create(
        tournament=tournament, club=club, is_ai=club.managed_by_id is None,
    )
    _notify([club], 'Turnierbeitritt bestätigt', f'Du nimmst an „{tournament.name}“ teil.')
    return entry


@transaction.atomic
def apply_tournament(tournament_id, club):
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament_id)
    if tournament.status != CommunityTournament.STATUS_OPEN or tournament.access != 'bewerbung':
        raise ValidationError('Dieses Turnier nimmt keine Bewerbungen an.')
    if CommunityTournamentEntry.objects.filter(tournament=tournament, club=club).exists():
        raise ValidationError('Der Verein nimmt bereits teil.')
    application, _ = CommunityTournamentApplication.objects.get_or_create(
        tournament=tournament, club=club, defaults={'status': 'offen'},
    )
    if application.status != 'offen':
        raise ValidationError('Diese Bewerbung ist nicht mehr offen.')
    _notify([tournament.organizer], 'Neue Turnierbewerbung',
            f'{club.name} bewirbt sich für „{tournament.name}“.')
    return application


@transaction.atomic
def set_reward_plan(tournament_id, reward_plan, *, is_admin=False):
    """Change rewards before the first played tournament match only."""
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament_id)
    if not is_admin:
        raise ValidationError('Nur Administratoren dürfen Prämien festlegen.')
    if CommunityTournamentMatch.objects.filter(
            round__phase__tournament=tournament,
            friendly_fixture__status=FriendlyFixture.STATUS_PLAYED).exists():
        raise ValidationError('Der Prämienplan ist nach dem ersten Spiel unveränderlich.')
    payouts = (reward_plan or {}).get('payouts', {})
    if any(Decimal(str(value)) < 0 for value in payouts.values()):
        raise ValidationError('Prämien dürfen nicht negativ sein.')
    tournament.reward_plan = reward_plan or {}
    tournament.save(update_fields=['reward_plan'])
    return tournament


@transaction.atomic
def decide_application(application_id, organizer, accept):
    application = CommunityTournamentApplication.objects.select_for_update().select_related(
        'tournament', 'club').get(pk=application_id)
    tournament = CommunityTournament.objects.select_for_update().get(pk=application.tournament_id)
    if tournament.organizer_id != organizer.pk or tournament.status != tournament.STATUS_OPEN:
        raise ValidationError('Nur der Veranstalter darf Bewerbungen verwalten.')
    if application.status != application.OPEN:
        return application
    if accept:
        if CommunityTournamentEntry.objects.filter(tournament=tournament).count() >= tournament.field_size:
            raise ValidationError('Das Teilnehmerfeld ist voll.')
        application.club = Club.objects.select_for_update().get(pk=application.club_id)
        if candidate_schedule_conflicts(application.club, tournament):
            raise ValidationError('Der Verein hat eine Terminkollision im Turnierplan.')
        CommunityTournamentEntry.objects.create(
            tournament=tournament, club=application.club,
            is_ai=application.club.managed_by_id is None,
        )
        application.status = application.ACCEPTED
    else:
        application.status = application.REJECTED
    application.save(update_fields=['status'])
    _notify([application.club], 'Turnierbewerbung ' + ('angenommen' if accept else 'abgelehnt'),
            tournament.name)
    return application


@transaction.atomic
def withdraw_application(application_id, club):
    application = CommunityTournamentApplication.objects.select_for_update().select_related(
        'tournament', 'club').get(pk=application_id)
    if application.club_id != club.pk or application.status != application.OPEN:
        raise ValidationError('Diese Bewerbung kann nicht zurückgezogen werden.')
    if application.tournament.status != CommunityTournament.STATUS_OPEN:
        raise ValidationError('Das Turnier nimmt keine Änderungen mehr an.')
    application.status = application.WITHDRAWN
    application.save(update_fields=['status'])
    return application


@transaction.atomic
def remove_participant(tournament_id, entry_id, organizer):
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament_id)
    if tournament.organizer_id != organizer.pk or tournament.status != tournament.STATUS_OPEN:
        raise ValidationError('Teilnehmer können jetzt nicht entfernt werden.')
    entry = CommunityTournamentEntry.objects.select_for_update().select_related(
        'club').get(pk=entry_id, tournament=tournament)
    entry.delete()
    _notify([entry.club], 'Aus Turnier entfernt', tournament.name)
    return entry


@transaction.atomic
def reschedule_round(round_id, kickoff_at, organizer):
    round_obj = CommunityTournamentRound.objects.select_for_update().select_related(
        'phase__tournament').get(pk=round_id)
    tournament = round_obj.phase.tournament
    if tournament.organizer_id != organizer.pk or tournament.status != tournament.STATUS_RUNNING:
        raise ValidationError('Dieser Spieltag kann nicht verschoben werden.')
    from django.utils.dateparse import parse_datetime
    value = parse_datetime(kickoff_at) if isinstance(kickoff_at, str) else kickoff_at
    if value is None:
        raise ValidationError('Ungültiger Spieltermin.')
    value = value if timezone.is_aware(value) else timezone.make_aware(value)
    if value <= timezone.now() or (round_obj.scheduled_at and timezone.now() >= round_obj.scheduled_at):
        raise ValidationError('Der Spieltag ist nicht mehr verschiebbar.')
    matches = list(CommunityTournamentMatch.objects.select_for_update(of=('self',)).filter(
        round=round_obj).select_related('home_entry__club', 'away_entry__club',
                                         'friendly_fixture'))
    from game.friendlies.services import _collision
    for match in matches:
        for entry in (match.home_entry, match.away_entry):
            if entry and _collision(entry.club, value, tournament.squad_scope,
                                    match.friendly_fixture):
                raise ValidationError('Der neue Spieltermin kollidiert mit einer Partie.')
    round_obj.scheduled_at = value
    round_obj.save(update_fields=['scheduled_at'])
    clubs = []
    for match in matches:
        if match.friendly_fixture_id and match.friendly_fixture.status not in (
                FriendlyFixture.STATUS_PLAYED, FriendlyFixture.STATUS_NOT_PLAYED):
            match.friendly_fixture.kickoff_at = value
            match.friendly_fixture.save(update_fields=['kickoff_at'])
        match.scheduled_at = value
        match.save(update_fields=['scheduled_at'])
        clubs.extend([e.club for e in (match.home_entry, match.away_entry) if e])
    _notify([c for c in clubs if c.managed_by_id], 'Turniertermin verschoben',
            f'{tournament.name}: {value:%d.%m.%Y %H:%M}')
    return round_obj


@transaction.atomic
def rotate_invitation_code(tournament_id, organizer, code):
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament_id)
    if tournament.organizer_id != organizer.pk or tournament.status != tournament.STATUS_OPEN:
        raise ValidationError('Der Einladungscode kann jetzt nicht geändert werden.')
    if tournament.access != tournament.ACCESS_CODE or not code:
        raise ValidationError('Für dieses Turnier ist kein Einladungscode vorgesehen.')
    tournament.invitation_code = code
    tournament.save(update_fields=['invitation_code'])
    return tournament


def _schedule_value(tournament, index):
    value = tournament.schedule[index]
    if isinstance(value, dict):
        value = value.get('kickoff_at') or value.get('scheduled_at')
    if not value:
        raise ValidationError('Spielplan enthält keinen gültigen Termin.')
    from django.utils.dateparse import parse_datetime
    if isinstance(value, str):
        value = parse_datetime(value)
    if value is None:
        raise ValidationError('Spielplan enthält keinen gültigen Termin.')
    return value if timezone.is_aware(value) else timezone.make_aware(value)


@transaction.atomic
def start_tournament(tournament_id, *, organizer, ai_clubs=(), shrink_to=None,
                     allow_byes=False):
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament_id)
    if tournament.organizer_id != organizer.pk or tournament.status != tournament.STATUS_OPEN:
        raise ValidationError('Turnier kann nicht gestartet werden.')
    entries = list(CommunityTournamentEntry.objects.select_for_update().filter(
        tournament=tournament).select_related('club'))
    ai_club_ids = sorted(c.pk for c in ai_clubs)
    locked_ai = {
        c.pk: c for c in Club.objects.select_for_update().filter(
            pk__in=ai_club_ids).order_by('pk')
    }
    if ai_clubs:
        for club in ai_clubs:
            club = locked_ai.get(club.pk, club)
            if len(entries) >= tournament.field_size:
                break
            if not any(e.club_id == club.pk for e in entries):
                if candidate_schedule_conflicts(club, tournament):
                    raise ValidationError('Ein KI-Verein hat eine Terminkollision im Turnierplan.')
                entries.append(CommunityTournamentEntry.objects.create(
                    tournament=tournament, club=club, is_ai=True))
    target = shrink_to or tournament.field_size
    if target not in FIELD_SIZES[tournament.format]:
        raise ValidationError('Ungültige Zielfeldgröße.')
    if len(entries) > target:
        raise ValidationError('Die Zielfeldgröße darf nicht kleiner als das aktuelle Teilnehmerfeld sein.')
    if target != tournament.field_size:
        tournament.field_size = target
        tournament.save(update_fields=['field_size'])
    if len(entries) != target:
        if tournament.format != tournament.FORMAT_CUP or not allow_byes:
            raise ValidationError('Teilnehmerzahl entspricht nicht der Feldgröße.')
        if target != tournament.field_size or len(entries) > target:
            raise ValidationError('Ungültige verkleinerte Feldgröße.')
    if len(entries) < 2:
        raise ValidationError('Mindestens zwei Teilnehmer sind erforderlich.')
    rng = random.Random(tournament.pk)
    rng.shuffle(entries)
    for pos, entry in enumerate(entries, 1):
        entry.draw_position = pos
        entry.save(update_fields=['draw_position'])
        CommunityTournamentStanding.objects.get_or_create(
            tournament=tournament, entry=entry, defaults={'random_order': pos})
    phase = CommunityTournamentPhase.objects.create(
        tournament=tournament, name='Liga' if tournament.format == 'liga' else 'Hauptphase',
        phase_type=('gruppe' if tournament.format == tournament.FORMAT_GROUP_KO
                    else tournament.format), number=1,
    )
    rounds = _round_count(tournament)
    for number in range(1, rounds + 1):
        if tournament.format == tournament.FORMAT_CUP:
            label = f'{number}. Runde' if not tournament.home_and_away else (
                f'{(number + 1) // 2}. Runde – '
                f'{"Hinspiel" if number % 2 else "Rückspiel"}')
        elif tournament.format == tournament.FORMAT_GROUP_KO and number <= 3:
            label = f'Gruppenspieltag {number}'
        else:
            label = f'Spieltag {number}'
        CommunityTournamentRound.objects.create(
            phase=phase, number=number, name=label,
            scheduled_at=_schedule_value(tournament, number - 1),
        )
    # League and groups are materialised up front; knockout rounds are drawn
    # as results become available.
    if tournament.format == tournament.FORMAT_LEAGUE:
        for rnd in phase.rounds.all():
            pairings = _league_pairings(entries, rnd.number, tournament.home_and_away)
            for home, away in pairings:
                _create_fixture(rnd, home, away, tournament)
    elif tournament.format == tournament.FORMAT_CUP:
        _create_cup_round(phase.rounds.first(), entries, tournament)
    else:
        group_count = 2 if len(entries) == 8 else 4
        for index, entry in enumerate(entries):
            entry.group = chr(ord('A') + index // 4)
            entry.save(update_fields=['group'])
            CommunityTournamentStanding.objects.filter(entry=entry).update(group=entry.group)
        for number in range(1, 4):
            rnd = phase.rounds.get(number=number)
            for group in range(group_count):
                members = [e for e in entries if e.group == chr(ord('A') + group)]
                for home, away in _league_pairings(members, number, False):
                    _create_fixture(rnd, home, away, tournament)
    tournament.status = tournament.STATUS_RUNNING
    tournament.started_at = timezone.now()
    tournament.save(update_fields=['status', 'started_at'])
    _notify([e.club for e in entries], 'Turnier gestartet', tournament.name)
    return tournament


def _create_cup_round(round_obj, entries, tournament):
    ordered = sorted(entries, key=lambda e: (e.draw_position or 0, e.pk))
    size = 1 << (len(ordered) - 1).bit_length()
    match_count = len(ordered) - size // 2
    bye_count = size - len(ordered)
    for entry in ordered[:bye_count]:
        CommunityTournamentMatch.objects.create(
            round=round_obj, home_entry=entry, winner_entry=entry,
            status='bye', counted=True)
    for index in range(bye_count, bye_count + match_count * 2, 2):
        match = _create_fixture(
            round_obj, ordered[index], ordered[index + 1], tournament)
        _notify_pairing(tournament, match)


def _league_pairings(entries, round_number, double):
    teams = list(entries)
    if len(teams) % 2:
        teams.append(None)
    n = len(teams)
    shift = (round_number - 1) % (n - 1)
    order = [teams[0]] + teams[1:][shift:] + teams[1:][:shift]
    pairs = [(order[i], order[-i - 1]) for i in range(n // 2)]
    if double and round_number > n - 1:
        pairs = [(a, b) for b, a in pairs]
    return [(a, b) for a, b in pairs if a and b]


def _create_fixture(round_obj, home, away, tournament):
    kickoff = round_obj.scheduled_at
    from game.friendlies.services import _collision
    if _collision(home.club, kickoff, tournament.squad_scope) or _collision(
            away.club, kickoff, tournament.squad_scope):
        raise ValidationError('Turniertermin kollidiert mit einer vorhandenen Partie.')
    is_group = round_obj.phase.phase_type == 'gruppe' and round_obj.number <= 3
    is_two_leg = tournament.format == tournament.FORMAT_CUP and tournament.home_and_away
    ko_rules = tournament.format in (tournament.FORMAT_CUP, tournament.FORMAT_GROUP_KO)
    use_decisive_rules = ko_rules and not is_group and not is_two_leg
    fixture = FriendlyFixture.objects.create(
        sender_club=home.club, target_club=away.club, kickoff_at=kickoff,
        squad_scope=tournament.squad_scope,
        venue_type=FriendlyFixture.VENUE_NEUTRAL if tournament.neutral_venue_id else 'heim',
        neutral_stadium=tournament.neutral_venue,
        extra_time=bool(tournament.rules.get('extra_time')) if use_decisive_rules else False,
        penalties=bool(tournament.rules.get('penalties')) if use_decisive_rules else False,
        season=tournament.season, status=FriendlyFixture.STATUS_PLANNED,
    )
    return CommunityTournamentMatch.objects.create(
        round=round_obj, home_entry=home, away_entry=away,
        friendly_fixture=fixture, scheduled_at=kickoff,
    )


@transaction.atomic
def advance_tournament(tournament_id):
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament_id)
    if tournament.status == CommunityTournament.STATUS_COMPLETED:
        return 0
    matches = CommunityTournamentMatch.objects.filter(round__phase__tournament=tournament)
    changed = 0
    for match in matches.select_related('friendly_fixture', 'home_entry', 'away_entry'):
        fixture = match.friendly_fixture
        if match.counted:
            continue
        if not match.home_entry_id or not match.away_entry_id:
            match.status = FriendlyFixture.STATUS_NOT_PLAYED
            match.forfeiture = 'single_no_show' if (
                match.home_entry_id or match.away_entry_id) else 'double_no_show'
            match.winner_entry = match.home_entry or match.away_entry
            match.counted = True
            match.save(update_fields=['status', 'forfeiture', 'winner_entry', 'counted'])
            if (match.home_entry_id or match.away_entry_id) and _is_standings_match(match):
                survivor = match.home_entry or match.away_entry
                standing = CommunityTournamentStanding.objects.select_for_update().get(
                    entry=survivor)
                standing.played += 1
                standing.wins += 1
                standing.goals_for += 3
                standing.points += 3
                standing.save()
            changed += 1
            continue
        if not fixture or fixture.status not in (
                FriendlyFixture.STATUS_PLAYED, FriendlyFixture.STATUS_NOT_PLAYED):
            continue
        if fixture.simulated_match_id:
            match.home_goals = fixture.simulated_match.home_goals
            match.away_goals = fixture.simulated_match.away_goals
        else:
            from game.friendlies.services import get_squad
            home_ready = get_squad(match.home_entry.club, tournament.squad_scope).count()
            away_ready = get_squad(match.away_entry.club, tournament.squad_scope).count()
            if home_ready < 11 and away_ready >= 11:
                match.home_goals, match.away_goals = 0, 3
                match.forfeiture, match.winner_entry = 'home_no_show', match.away_entry
            elif away_ready < 11 and home_ready >= 11:
                match.home_goals, match.away_goals = 3, 0
                match.forfeiture, match.winner_entry = 'away_no_show', match.home_entry
            else:
                match.home_goals = match.away_goals = 0
                match.forfeiture, match.winner_entry = 'double_no_show', None
        match.status = fixture.status
        if match.status == FriendlyFixture.STATUS_NOT_PLAYED:
            if not match.forfeiture:
                match.forfeiture = 'double_no_show'
                match.winner_entry = None
        elif match.home_goals > match.away_goals:
            match.winner_entry = match.home_entry
        elif match.away_goals > match.home_goals:
            match.winner_entry = match.away_entry
        else:
            report = fixture.simulated_match.report_data if fixture.simulated_match_id else {}
            winner_id = report.get('winner_club_id')
            match.winner_entry = (
                match.home_entry if winner_id == match.home_entry.club_id else
                match.away_entry if winner_id == match.away_entry.club_id else None)
            # A drawn first leg is intentionally unresolved; the return leg
            # resolves the aggregate.  Only single-leg KO (and return legs)
            # must be decisive here.
            first_leg_draw = (
                tournament.format == tournament.FORMAT_CUP and
                tournament.home_and_away and match.round.number % 2 == 1)
            deciding_return = (
                tournament.format == tournament.FORMAT_CUP and
                tournament.home_and_away and match.round.number % 2 == 0)
            if (match.winner_entry is None and not _is_standings_match(match)
                    and not first_leg_draw and not deciding_return):
                raise ValidationError('K.o.-Ergebnis ist nicht entscheidungsfähig.')
        match.counted = True
        match.save(update_fields=['home_goals', 'away_goals', 'status',
                                  'counted', 'winner_entry', 'forfeiture'])
        if _is_standings_match(match):
            _update_standings(match)
        changed += 1
    if tournament.format == tournament.FORMAT_LEAGUE and matches.exists() and not matches.filter(counted=False).exists():
        for rank, standing in enumerate(rank_standings(tournament), 1):
            standing.entry.final_rank = rank
            standing.entry.save(update_fields=['final_rank'])
        tournament.status = tournament.STATUS_COMPLETED
        tournament.completed_at = timezone.now()
        tournament.save(update_fields=['status', 'completed_at'])
        _notify_completion(tournament)
        pay_rewards(tournament)
    elif tournament.format == tournament.FORMAT_CUP:
        _advance_cup(tournament)
    elif tournament.format == tournament.FORMAT_GROUP_KO:
        _advance_groups(tournament)
    return changed


def _advance_cup(tournament):
    phase = tournament.phases.first()
    rounds = list(phase.rounds.order_by('number'))
    current = next((r for r in rounds if r.matches.exists() and
                    not r.matches.filter(counted=False).exists() and
                    r.number == max(x.number for x in rounds if x.matches.exists())), None)
    if current is None:
        return
    completed_matches = list(current.matches.select_related(
        'home_entry', 'away_entry', 'home_leg').all())
    # In a two-leg tie the second pre-announced round is the return leg.
    # Aggregate score decides; away goals are intentionally ignored.
    if tournament.home_and_away and current.number % 2 == 0:
        winners = []
        for return_match in completed_matches:
            first = return_match.home_leg
            if first is None:
                continue
            home_total = (first.home_goals or 0) + (return_match.away_goals or 0)
            away_total = (first.away_goals or 0) + (return_match.home_goals or 0)
            winner = (first.home_entry if home_total > away_total else
                       first.away_entry if away_total > home_total else None)
            if winner is not None:
                return_match.winner_entry = winner
                return_match.save(update_fields=['winner_entry'])
            if winner is None:
                data = (return_match.friendly_fixture.simulated_match.report_data
                        if return_match.friendly_fixture_id and
                        return_match.friendly_fixture.simulated_match_id else {})
                shootout = data.get('tournament_aggregate_shootout')
                if not shootout:
                    rng = random.Random(
                        f'aggregate-shootout:{tournament.pk}:{current.number}:{first.pk}')
                    home_pen = sum(rng.randrange(100) < 75 for _ in range(5))
                    away_pen = sum(rng.randrange(100) < 75 for _ in range(5))
                    while home_pen == away_pen:
                        away_pen = (away_pen + 1) % 6
                    shootout = {
                        'home_penalties': home_pen,
                        'away_penalties': away_pen,
                        'winner_club_id': (
                            return_match.home_entry.club_id if home_pen > away_pen
                            else return_match.away_entry.club_id),
                    }
                    if return_match.friendly_fixture_id and return_match.friendly_fixture.simulated_match_id:
                        sm = return_match.friendly_fixture.simulated_match
                        sm.report_data = {**(sm.report_data or {}),
                                          'tournament_aggregate_shootout': shootout}
                        sm.save(update_fields=['report_data'])
                return_match.home_penalties = shootout['home_penalties']
                return_match.away_penalties = shootout['away_penalties']
                # Totals on the deciding return match are authoritative;
                # report winner_club_id is only an annotation and is repaired.
                winner = (return_match.home_entry
                          if return_match.home_penalties > return_match.away_penalties
                          else return_match.away_entry)
                shootout['winner_club_id'] = winner.club_id
                if return_match.friendly_fixture_id and return_match.friendly_fixture.simulated_match_id:
                    sm = return_match.friendly_fixture.simulated_match
                    sm.report_data = {**(sm.report_data or {}),
                                      'tournament_aggregate_shootout': shootout}
                    sm.save(update_fields=['report_data'])
                return_match.forfeiture = 'shootout'
                return_match.winner_entry = winner
                return_match.save(update_fields=['forfeiture', 'winner_entry',
                                                 'home_penalties', 'away_penalties'])
            winners.append(winner)
    else:
        winners = [m.winner_entry for m in completed_matches if m.winner_entry]
    nxt = phase.rounds.filter(number=current.number + 1).first()
    if (tournament.home_and_away and current.number % 2 == 1 and
            nxt is not None and not nxt.matches.exists()):
        # First legs with a live tie always get their return leg before any
        # singleton/bye completion logic. Dead ties intentionally stay empty.
        return_created = False
        for match in completed_matches:
            if (match.home_entry and match.away_entry and
                    match.forfeiture != 'double_no_show'):
                fixture = _create_fixture(nxt, match.away_entry, match.home_entry, tournament)
                fixture.home_leg = match
                fixture.save(update_fields=['home_leg'])
                _notify_pairing(tournament, fixture)
                return_created = True
        if return_created:
            return
    if len(winners) <= 1 and nxt is not None and not nxt.matches.exists():
        survivor = winners[0] if winners else None
        for future in rounds:
            if future.number <= current.number:
                continue
            if survivor:
                CommunityTournamentMatch.objects.create(
                    round=future, home_entry=survivor, winner_entry=survivor,
                    status='bye', counted=True)
        tournament.status = tournament.STATUS_COMPLETED
        tournament.completed_at = timezone.now()
        tournament.winner_entry = survivor
        if survivor:
            _persist_ko_ranks(tournament, survivor, [])
        tournament.save(update_fields=['status', 'completed_at', 'winner_entry'])
        _notify_completion(tournament)
        pay_rewards(tournament)
        return
    if nxt is None or nxt.matches.exists():
        if len(winners) <= 1 and (
                nxt is None or current.number == max(r.number for r in rounds)):
            tournament.status = tournament.STATUS_COMPLETED
            tournament.completed_at = timezone.now()
            if winners:
                tournament.winner_entry = winners[0]
            _persist_ko_ranks(tournament, winners[0] if winners else None,
                              completed_matches)
            tournament.save(update_fields=['status', 'completed_at', 'winner_entry'])
            _notify_completion(tournament)
            pay_rewards(tournament)
        return
    if len(winners) % 2:
        bye = winners.pop()
        CommunityTournamentMatch.objects.create(
            round=nxt, home_entry=bye, winner_entry=bye,
            status='bye', counted=True)
    for home, away in zip(winners[::2], winners[1::2]):
        _notify_pairing(tournament, _create_fixture(nxt, home, away, tournament))


def _persist_ko_ranks(tournament, champion, final_matches):
    """Materialize unique final placements from knockout elimination depth."""
    entries = list(tournament.entries.all())
    ordered = []
    if champion:
        ordered.append(champion)
    # Every knockout round's losers are ranked by elimination depth: the
    # latest round first, with persisted draw order as the stable tie-break.
    phase = tournament.phases.first()
    knockout_qs = CommunityTournamentMatch.objects.filter(
        round__phase=phase, counted=True,
    ).select_related('home_entry', 'away_entry', 'round')
    if tournament.format == CommunityTournament.FORMAT_GROUP_KO:
        knockout_qs = knockout_qs.filter(round__number__gt=3)
    knockout_matches = list(knockout_qs)
    if tournament.home_and_away:
        knockout_matches = [m for m in knockout_matches if m.round.number % 2 == 0]
    loser_groups = {}
    ko_entry_ids = set()
    for match in knockout_matches:
        if match.home_entry_id:
            ko_entry_ids.add(match.home_entry_id)
        if match.away_entry_id:
            ko_entry_ids.add(match.away_entry_id)
        if not match.home_entry or not match.away_entry:
            continue
        loser = match.away_entry if match.winner_entry == match.home_entry else match.home_entry
        if loser.pk != getattr(champion, 'pk', None):
            loser_groups.setdefault(match.round.number, []).append(loser)
    for round_number in sorted(loser_groups, reverse=True):
        ordered.extend(sorted(loser_groups[round_number],
                              key=lambda entry: (entry.draw_position or 0, entry.pk)))
    used = {entry.pk for entry in ordered}
    if tournament.format == CommunityTournament.FORMAT_GROUP_KO:
        for group in sorted(set(tournament.entries.values_list('group', flat=True))):
            for standing in rank_standings(tournament, group=group):
                if standing.entry_id not in used:
                    ordered.append(standing.entry)
                    used.add(standing.entry_id)
    for entry in entries:
        if entry.pk not in used:
            ordered.append(entry)
    for rank, entry in enumerate(ordered, 1):
        entry.final_rank = rank
        entry.save(update_fields=['final_rank'])


def _advance_groups(tournament):
    phase = tournament.phases.first()
    group_rounds = list(phase.rounds.filter(number__lte=3))
    if any(r.matches.filter(counted=False).exists() for r in group_rounds):
        return
    knockout = phase.rounds.filter(number=4).first()
    if knockout is None:
        return
    if knockout.matches.exists():
        if not knockout.matches.filter(counted=False).exists():
            _advance_cup(tournament)
        return
    qualifiers = []
    for group in sorted(set(tournament.entries.values_list('group', flat=True))):
        qualifiers.extend(rank_standings(tournament, group=group)[:2])
    entries = [s.entry for s in qualifiers]
    random.Random(f'ko-draw:{tournament.pk}').shuffle(entries)
    for position, entry in enumerate(entries, 1):
        entry.draw_position = position
        entry.save(update_fields=['draw_position'])
    for home, away in zip(entries[::2], entries[1::2]):
        match = _create_fixture(knockout, home, away, tournament)
        _notify_pairing(tournament, match)


def _update_standings(match):
    if not match.home_entry_id or not match.away_entry_id:
        return
    home = CommunityTournamentStanding.objects.select_for_update().get(
        tournament=match.home_entry.tournament, entry=match.home_entry)
    away = CommunityTournamentStanding.objects.select_for_update().get(
        tournament=match.away_entry.tournament, entry=match.away_entry)
    hg, ag = match.home_goals or 0, match.away_goals or 0
    home.played += 1; away.played += 1
    home.goals_for += hg; home.goals_against += ag
    away.goals_for += ag; away.goals_against += hg
    if match.status == FriendlyFixture.STATUS_NOT_PLAYED:
        if match.forfeiture == 'home_no_show':
            home.losses += 1; away.wins += 1; away.points += 3
        elif match.forfeiture == 'away_no_show':
            away.losses += 1; home.wins += 1; home.points += 3
        # A double no-show is recorded in the table but yields no points.
        home.save(); away.save()
        return
    if hg > ag:
        home.wins += 1; home.points += 3; away.losses += 1
    elif ag > hg:
        away.wins += 1; away.points += 3; home.losses += 1
    else:
        home.draws += 1; away.draws += 1; home.points += 1; away.points += 1
    home.save(); away.save()


def rank_standings(tournament, *, group=''):
    """Authoritative table order: points, goal difference, goals, H2H, draw."""
    rows = list(tournament.standings.filter(group=group).select_related('entry'))
    phase_filter = {}
    if tournament.format == CommunityTournament.FORMAT_LEAGUE:
        phase_filter['round__phase__phase_type'] = CommunityTournament.FORMAT_LEAGUE
    elif tournament.format == CommunityTournament.FORMAT_GROUP_KO:
        phase_filter['round__number__lte'] = 3
        if group:
            phase_filter['home_entry__group'] = group
            phase_filter['away_entry__group'] = group
    def key(row):
        gd = row.goals_for - row.goals_against
        return (-row.points, -gd, -row.goals_for)
    rows.sort(key=key)
    result = []
    i = 0
    while i < len(rows):
        j = i + 1
        base = key(rows[i])
        while j < len(rows) and key(rows[j]) == base:
            j += 1
        tied = rows[i:j]
        ids = {r.entry_id for r in tied}
        mini = {r.entry_id: [0, 0, 0] for r in tied}
        for match in CommunityTournamentMatch.objects.filter(
                round__phase__tournament=tournament, counted=True,
                **phase_filter,
                home_entry_id__in=ids, away_entry_id__in=ids):
            if match.home_goals is None:
                continue
            mini[match.home_entry_id][0] += match.home_goals
            mini[match.home_entry_id][1] += match.away_goals or 0
            mini[match.away_entry_id][0] += match.away_goals or 0
            mini[match.away_entry_id][1] += match.home_goals
        # Recompute mutual points from every leg before mutual GD/GF.
        for match in CommunityTournamentMatch.objects.filter(
                round__phase__tournament=tournament, counted=True,
                **phase_filter,
                home_entry_id__in=ids, away_entry_id__in=ids):
            if match.home_goals is None:
                continue
            if match.home_goals > match.away_goals:
                mini[match.home_entry_id][2] += 3
            elif match.away_goals > match.home_goals:
                mini[match.away_entry_id][2] += 3
            else:
                mini[match.home_entry_id][2] += 1
                mini[match.away_entry_id][2] += 1
        tied.sort(key=lambda r: (-mini[r.entry_id][2],
                                 -(mini[r.entry_id][0] - mini[r.entry_id][1]),
                                 -mini[r.entry_id][0], r.random_order, r.pk))
        result.extend(tied)
        i = j
    return result


@transaction.atomic
def pay_rewards(tournament):
    """Pay the immutable reward plan once, through the canonical ledger."""
    tournament = CommunityTournament.objects.select_for_update().get(pk=tournament.pk)
    if tournament.rewards_paid_at or not tournament.reward_plan:
        return []
    from game.economy.booking import book
    if tournament.format in (CommunityTournament.FORMAT_CUP,
                             CommunityTournament.FORMAT_GROUP_KO):
        entries = list(tournament.entries.select_related('club').filter(
            final_rank__isnull=False, club__isnull=False).order_by('final_rank'))
        standings = [type('Placement', (), {'entry': entry}) for entry in entries]
    else:
        standings = rank_standings(tournament)
        for rank, standing in enumerate(standings, 1):
            if standing.entry.final_rank is None:
                standing.entry.final_rank = rank
                standing.entry.save(update_fields=['final_rank'])
        standings = sorted(
            [s for s in standings if s.entry.club_id],
            key=lambda s: s.entry.final_rank or 999999,
        )
    payouts = tournament.reward_plan.get('payouts', {})
    txs = []
    for standing in standings:
        rank = standing.entry.final_rank
        amount = Decimal(str(payouts.get(str(rank), payouts.get(rank, 0))))
        if amount <= 0:
            continue
        if FinanceTransaction.objects.filter(
                referenz_typ='community_tournament_reward', referenz_id=tournament.pk,
                club=standing.entry.club, beschreibung__startswith=f'Platz {rank}').exists():
            continue
        txs.append(book(standing.entry.club, 'KORREKTUR_ADMIN',
                        amount, saison=tournament.season,
                        referenz_typ='community_tournament_reward',
                        referenz_id=tournament.pk,
                        beschreibung=f'Platz {rank}: {tournament.name}'))
        _notify([standing.entry.club], 'Turnierprämie ausgezahlt',
                f'{tournament.name}: Platz {rank}')
    CommunityTournament.objects.filter(pk=tournament.pk, rewards_paid_at__isnull=True).update(
        rewards_paid_at=timezone.now())
    return txs


def advance_due_tournaments(now=None):
    now = now or timezone.now()
    ids = CommunityTournamentMatch.objects.filter(
        counted=False, friendly_fixture__kickoff_at__lte=now,
    ).values_list('round__phase__tournament_id', flat=True).distinct()
    ids = set(ids)
    ids.update(CommunityTournamentMatch.objects.filter(
        counted=False, friendly_fixture__isnull=True,
    ).values_list('round__phase__tournament_id', flat=True))
    return sum(advance_tournament(pk) for pk in ids)


def cleanup_season(season):
    return CommunityTournament.objects.filter(season=str(season)).delete()[0]


def cleanup_orphaned_tournaments(now=None):
    now = now or timezone.now()
    cutoff = now - timedelta(days=14)
    return CommunityTournament.objects.filter(
        status=CommunityTournament.STATUS_OPEN, created_at__lt=cutoff,
    ).delete()[0]