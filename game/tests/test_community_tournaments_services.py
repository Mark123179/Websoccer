from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from game.friendlies.tournaments import (
    advance_tournament, apply_tournament, cleanup_orphaned_tournaments,
    create_tournament, decide_application, join_tournament, pay_rewards,
    set_reward_plan, start_tournament, cleanup_season, remove_participant,
    reschedule_round, withdraw_application, rank_standings,
)
from game.models import (
    Club, CommunityTournament, CommunityTournamentApplication,
    CommunityTournamentMatch, CommunityTournamentStanding, FinanceTransaction,
    FriendlyFixture, League, SimulatedMatch,
)


class CommunityTournamentServiceTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Community-Testliga')
        self.clubs = [
            Club.objects.create(name=f'Turnierverein {i}', short_name=f'CTV{i}',
                                league=self.league, founded_year=2000 + i, budget=0)
            for i in range(1, 17)
        ]
        self.organizer = self.clubs[0]
        self.kickoff = timezone.now() + timedelta(days=2)

    def schedule(self, count):
        return [(self.kickoff + timedelta(days=i)).isoformat() for i in range(count)]

    def create(self, fmt='liga', size=4, **kwargs):
        rounds = ((size - 1) if fmt == 'liga' else (size.bit_length() - 1))
        if kwargs.get('home_and_away'):
            rounds *= 2
        if fmt == 'gruppen_ko':
            rounds = 3 + (2 if size == 8 else 3)
        schedule = kwargs.pop('schedule', self.schedule(rounds))
        return create_tournament(
            organizer=self.organizer, name=f'Test {fmt} {size}',
            format=fmt, field_size=size, schedule=schedule,
            rules=kwargs.pop('rules', {'penalties': True} if fmt != 'liga' else {}),
            **kwargs,
        )

    def test_all_formats_and_field_sizes_require_complete_schedule(self):
        for fmt, sizes in (
            ('liga', (4, 6, 8, 10, 16)),
            ('pokal', (4, 8, 16)),
            ('gruppen_ko', (8, 16)),
        ):
            for size in sizes:
                tournament = self.create(fmt, size)
                self.assertEqual(tournament.status, tournament.STATUS_OPEN)
                expected = (size - 1 if fmt == 'liga' else
                            3 + (2 if size == 8 else 3) if fmt == 'gruppen_ko' else
                            size.bit_length() - 1)
                self.assertEqual(len(tournament.schedule), expected)
        with self.assertRaises(ValidationError):
            self.create('pokal', 4, schedule=['bad'])

    def test_cup_leg_schedule_maps_each_round_and_leg(self):
        tournament = self.create('pokal', 4, home_and_away=True)
        self.assertEqual(tournament.phases.count(), 0)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        rounds = list(tournament.phases.first().rounds.order_by('number'))
        self.assertEqual(len(rounds), 4)
        self.assertEqual(rounds[0].name, '1. Runde – Hinspiel')
        self.assertEqual(rounds[1].name, '1. Runde – Rückspiel')
        self.assertEqual(rounds[-1].name, '2. Runde – Rückspiel')

    def test_two_leg_cup_uses_aggregate_without_away_goals(self):
        tournament = self.create('pokal', 4, home_and_away=True)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        for _ in range(6):
            self._finish_open_matches(tournament)
            advance_tournament(tournament.pk)
        tournament.refresh_from_db()
        self.assertEqual(tournament.status, tournament.STATUS_COMPLETED)
        self.assertIsNotNone(tournament.winner_entry_id)

    def test_start_collision_rolls_back_all_tournament_fixtures(self):
        tournament = self.create('liga', 4)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        FriendlyFixture.objects.create(
            sender_club=self.clubs[1], target_club=self.clubs[2],
            kickoff_at=self.kickoff, status=FriendlyFixture.STATUS_PLANNED)
        with self.assertRaises(ValidationError):
            start_tournament(tournament.pk, organizer=self.organizer)
        self.assertEqual(tournament.phases.count(), 0)
        self.assertEqual(tournament.entries.count(), 4)

    def test_access_modes_and_organizer_is_not_implicitly_participant(self):
        open_tournament = self.create(access='offen')
        self.assertEqual(open_tournament.entries.count(), 0)
        self.assertEqual(join_tournament(open_tournament.pk, self.clubs[1]).club_id,
                         self.clubs[1].pk)
        code_tournament = self.create(access='code', invitation_code='secret')
        with self.assertRaises(ValidationError):
            join_tournament(code_tournament.pk, self.clubs[1], code='wrong')
        join_tournament(code_tournament.pk, self.clubs[3], code='secret')
        application_tournament = self.create(access='bewerbung')
        application = apply_tournament(application_tournament.pk, self.clubs[2])
        self.assertEqual(application.status, 'offen')
        decide_application(application.pk, self.organizer, True)
        self.assertTrue(application_tournament.entries.filter(club=self.clubs[2]).exists())

    def test_lifecycle_mutation_authorization_and_reschedule(self):
        tournament = self.create(access='bewerbung')
        application = apply_tournament(tournament.pk, self.clubs[1])
        withdrawn = withdraw_application(application.pk, self.clubs[1])
        self.assertEqual(withdrawn.status, 'zurueckgezogen')
        entry = join_tournament(self.create().pk, self.clubs[1])
        with self.assertRaises(ValidationError):
            remove_participant(entry.tournament_id, entry.pk, self.clubs[1])
        removable = remove_participant(entry.tournament_id, entry.pk, self.organizer)
        self.assertIsNotNone(removable)
        running = self.create()
        for club in self.clubs[1:5]:
            join_tournament(running.pk, club)
        start_tournament(running.pk, organizer=self.organizer)
        rnd = running.phases.first().rounds.first()
        moved = self.kickoff + timedelta(days=20)
        updated = reschedule_round(rnd.pk, moved.isoformat(), self.organizer)
        self.assertEqual(updated.scheduled_at.date(), moved.date())
        with self.assertRaises(ValidationError):
            reschedule_round(rnd.pk, timezone.now() - timedelta(hours=1), self.organizer)

    def test_ai_fill_and_shrink_and_pokal_bye_option(self):
        tournament = self.create('liga', 4)
        join_tournament(tournament.pk, self.clubs[1])
        started = start_tournament(tournament.pk, organizer=self.organizer,
                                   ai_clubs=[self.clubs[2], self.clubs[3], self.clubs[4]])
        self.assertEqual(started.entries.count(), 4)

    def test_shrink_and_pokal_byes(self):
        tournament = self.create('pokal', 8)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        started = start_tournament(tournament.pk, organizer=self.organizer,
                                   allow_byes=True)
        self.assertEqual(started.status, started.STATUS_RUNNING)
        self.assertEqual(started.entries.count(), 4)

    def test_sandbox_linkage_and_idempotent_standings(self):
        tournament = self.create('liga', 4)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        match = tournament.phases.first().rounds.first().matches.first()
        self.assertIsNotNone(match.friendly_fixture_id)
        fixture = match.friendly_fixture
        fixture.status = FriendlyFixture.STATUS_NOT_PLAYED
        fixture.save(update_fields=['status'])
        self.assertEqual(advance_tournament(tournament.pk), 1)
        self.assertEqual(advance_tournament(tournament.pk), 0)
        standing = CommunityTournamentStanding.objects.get(entry=match.home_entry)
        self.assertEqual(standing.played, 1)

    def test_league_updates_standings_on_every_matchday(self):
        tournament = self.create('liga', 6)
        for club in self.clubs[1:7]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        self.assertEqual(tournament.phases.first().rounds.count(), 5)
        self._finish_open_matches(tournament)
        advance_tournament(tournament.pk)
        self.assertTrue(tournament.standings.filter(played__gt=3).exists())

    def test_group_h2h_uses_persisted_group_match(self):
        tournament = self.create('gruppen_ko', 8)
        for club in self.clubs[1:9]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        match = tournament.phases.first().rounds.first().matches.first()
        match.home_goals, match.away_goals = 1, 0
        match.counted = True
        match.status = FriendlyFixture.STATUS_PLAYED
        match.save(update_fields=['home_goals', 'away_goals', 'counted', 'status'])
        home = CommunityTournamentStanding.objects.get(entry=match.home_entry)
        away = CommunityTournamentStanding.objects.get(entry=match.away_entry)
        for standing in (home, away):
            standing.points = 7
            standing.goals_for = standing.goals_against = 4
            standing.random_order = 99
            standing.save()
        self.assertEqual(rank_standings(tournament, group=home.group)[0].entry_id,
                         home.entry_id)

    def _finish_open_matches(self, tournament):
        for match in CommunityTournamentMatch.objects.filter(
                round__phase__tournament=tournament, counted=False):
            match.friendly_fixture.status = FriendlyFixture.STATUS_PLAYED
            report = {'home_goals': 1, 'away_goals': 0,
                      'winner_club_id': match.home_entry.club_id}
            simulated = SimulatedMatch.create_numbered(
                season=tournament.season, home_club=match.home_entry.club,
                away_club=match.away_entry.club, home_goals=1, away_goals=0,
                report_data=report, match_type='freundschaft')
            match.friendly_fixture.simulated_match = simulated
            match.friendly_fixture.save(update_fields=['status', 'simulated_match'])

    def test_pokal_reaches_winner_and_repeated_advance_is_idempotent(self):
        tournament = self.create('pokal', 4)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        for _ in range(3):
            self._finish_open_matches(tournament)
            advance_tournament(tournament.pk)
        tournament.refresh_from_db()
        self.assertEqual(tournament.status, tournament.STATUS_COMPLETED)
        self.assertIsNotNone(tournament.winner_entry_id)
        self.assertEqual(advance_tournament(tournament.pk), 0)

    def _set_result(self, match, home_goals, away_goals):
        fixture = match.friendly_fixture
        simulated = SimulatedMatch.create_numbered(
            season=match.round.phase.tournament.season,
            home_club=match.home_entry.club, away_club=match.away_entry.club,
            home_goals=home_goals, away_goals=away_goals,
            report_data={'home_goals': home_goals, 'away_goals': away_goals,
                         'winner_club_id': (
                             match.home_entry.club_id if home_goals > away_goals
                             else match.away_entry.club_id if away_goals > home_goals
                             else None)},
            match_type='freundschaft')
        fixture.status = FriendlyFixture.STATUS_PLAYED
        fixture.simulated_match = simulated
        fixture.save(update_fields=['status', 'simulated_match'])

    def test_two_leg_deciding_return_draws_are_aggregate_resolved(self):
        for case, return_score in enumerate(((1, 1), (1, 0))):
            tournament = self.create('pokal', 4, home_and_away=True)
            start = 1 + case * 4
            for club in self.clubs[start:start + 4]:
                join_tournament(tournament.pk, club)
            start_tournament(tournament.pk, organizer=self.organizer)
            first = tournament.phases.first().rounds.first()
            for match in first.matches.all():
                self._set_result(match, 1, 0)
            advance_tournament(tournament.pk)
            returns = tournament.phases.first().rounds.get(number=2)
            target = returns.matches.first()
            self._set_result(target, *return_score)
            for match in returns.matches.exclude(pk=target.pk):
                self._set_result(match, 1, 0)
            advance_tournament(tournament.pk)
            self.assertTrue(tournament.phases.first().rounds.get(
                number=3).matches.exists())
            resolved = CommunityTournamentMatch.objects.get(pk=target.pk)
            self.assertTrue(resolved.winner_entry_id or resolved.forfeiture == 'shootout')

    def test_two_leg_all_dead_first_legs_complete_without_stuck_round(self):
        tournament = self.create('pokal', 4, home_and_away=True)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        for match in tournament.phases.first().rounds.first().matches.all():
            match.friendly_fixture.status = FriendlyFixture.STATUS_NOT_PLAYED
            match.friendly_fixture.save(update_fields=['status'])
        advance_tournament(tournament.pk)
        tournament.refresh_from_db()
        self.assertEqual(tournament.status, tournament.STATUS_COMPLETED)

    def test_seven_entrant_cup_uses_one_bye_and_reaches_champion(self):
        tournament = self.create('pokal', 8)
        for club in self.clubs[1:8]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer, allow_byes=True)
        for _ in range(5):
            self._finish_open_matches(tournament)
            advance_tournament(tournament.pk)
        tournament.refresh_from_db()
        self.assertEqual(tournament.status, tournament.STATUS_COMPLETED)
        self.assertIsNotNone(tournament.winner_entry_id)

    def test_groups_qualify_two_each_then_complete_knockout(self):
        tournament = self.create('gruppen_ko', 8)
        for club in self.clubs[1:9]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        self.assertEqual(tournament.entries.exclude(group='').count(), 8)
        self.assertEqual(tournament.phases.first().rounds.filter(
            number__lte=3).count(), 3)
        for _ in range(4):
            self._finish_open_matches(tournament)
            advance_tournament(tournament.pk)
        self.assertGreaterEqual(
            CommunityTournamentMatch.objects.filter(
                round__number=4, round__phase__tournament=tournament).count(), 1)
        for _ in range(3):
            self._finish_open_matches(tournament)
            advance_tournament(tournament.pk)
        tournament.refresh_from_db()
        self.assertEqual(tournament.status, tournament.STATUS_COMPLETED)
        self.assertIsNotNone(tournament.winner_entry_id)

    def test_double_no_show_is_counted_once_without_points(self):
        tournament = self.create('liga', 4)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        match = tournament.phases.first().rounds.first().matches.first()
        match.friendly_fixture.status = FriendlyFixture.STATUS_NOT_PLAYED
        match.friendly_fixture.save(update_fields=['status'])
        advance_tournament(tournament.pk)
        home = CommunityTournamentStanding.objects.get(entry=match.home_entry)
        away = CommunityTournamentStanding.objects.get(entry=match.away_entry)
        self.assertEqual((home.played, away.played), (1, 1))

    def test_collision_with_tournament_fixture_is_rejected_by_friendly_planner(self):
        tournament = self.create('liga', 4)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        from game.friendlies.services import create_directed_request
        with self.assertRaises(ValidationError):
            create_directed_request(sender_club=self.clubs[1], target_club=self.clubs[2],
                                    kickoff_at=self.kickoff)

    def test_rewards_permission_lock_and_idempotency(self):
        tournament = self.create('liga', 4)
        with self.assertRaises(ValidationError):
            set_reward_plan(tournament.pk, {'payouts': {'1': 100}}, is_admin=False)
        set_reward_plan(tournament.pk, {'payouts': {'1': 100}}, is_admin=True)
        for club in self.clubs[1:5]:
            join_tournament(tournament.pk, club)
        start_tournament(tournament.pk, organizer=self.organizer)
        self._finish_open_matches(tournament)
        advance_tournament(tournament.pk)
        with self.assertRaises(ValidationError):
            set_reward_plan(tournament.pk, {'payouts': {'1': 200}}, is_admin=True)
        tournament.status = tournament.STATUS_COMPLETED
        tournament.save(update_fields=['status'])
        standing = tournament.standings.first()
        tx1 = pay_rewards(tournament)
        tx2 = pay_rewards(tournament)
        self.assertEqual(len(tx1), 0)  # completion pass already paid it
        self.assertEqual(tx2, [])
        self.assertEqual(FinanceTransaction.objects.filter(
            referenz_typ='community_tournament_reward',
            referenz_id=tournament.pk).count(), 1)

    def test_orphan_cleanup(self):
        tournament = self.create()
        CommunityTournament.objects.filter(pk=tournament.pk).update(
            created_at=timezone.now() - timedelta(days=15))
        self.assertEqual(cleanup_orphaned_tournaments(), 1)

    def test_season_cleanup_removes_tournament_domain(self):
        tournament = self.create(season='old-season')
        self.assertEqual(cleanup_season('old-season'), 1)
        self.assertFalse(CommunityTournament.objects.filter(pk=tournament.pk).exists())