"""Focused tests for automatic manager timeline system events."""

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from game.manager_timeline_service import (
    CAREER_END_TITLES,
    create_career_end_event,
    create_final_events,
    create_first_youth_promotion_event,
    finish_manager_career,
)
from game.models import (
    Club,
    CupFixture,
    CupRound,
    CupSeason,
    League,
    ManagerCareerEntry,
    ManagerCompetitionTitle,
    ManagerProfile,
    ManagerTimelineEntry,
    Player,
)


class ManagerTimelineServiceTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(
            name='Timeline Testliga',
            country='Deutschland',
            competition_type='league',
            max_teams=32,
        )
        self.cup = League.objects.create(
            name='Timeline Pokal',
            country='Deutschland',
            competition_type='cup',
            max_teams=32,
        )

    def _club(self, name):
        return Club.objects.create(
            name=name,
            short_name=name[:8],
            founded_year=1900,
            budget=1_000_000,
            fan_popularity=50,
            league=self.league,
        )

    def _manager(self, name):
        return ManagerProfile.objects.create(name=name)

    def _final_fixture(
        self,
        *,
        season,
        home,
        away,
        winner,
        home_manager=None,
        away_manager=None,
        scheduled_date=date(2026, 5, 10),
    ):
        cup_season = CupSeason.objects.create(
            competition=self.cup,
            season=season,
            status=CupSeason.STATUS_COMPLETED,
            winner_club=winner,
        )
        cup_round = CupRound.objects.create(
            cup_season=cup_season,
            round_number=5,
            round_code='final',
            status=CupRound.STATUS_COMPLETED,
            scheduled_date=scheduled_date,
        )
        return CupFixture.objects.create(
            cup_round=cup_round,
            bracket_position=1,
            home_club=home,
            away_club=away,
            home_manager=home_manager,
            away_manager=away_manager,
            winner_club=winner,
            status=CupFixture.STATUS_PLAYED,
            home_goals_90=2,
            away_goals_90=1,
            decided_by=CupFixture.DECIDED_BY_REGULAR,
        )

    def test_career_end_reasons_have_titles_and_are_idempotent(self):
        for index, reason in enumerate((*CAREER_END_TITLES.keys(),)):
            manager = self._manager(f'End Manager {index}')
            club = self._club(f'End Club {index}')
            career = ManagerCareerEntry.objects.create(
                manager=manager,
                club=club,
                started_at=date(2025, 8, 1),
                active=True,
            )
            ended_at = date(2026, 5, 10 + index)

            result = finish_manager_career(
                manager, club, ended_at=ended_at, reason=reason
            )

            self.assertIsNotNone(result)
            result.refresh_from_db()
            self.assertFalse(result.active)
            self.assertEqual(result.ended_at, ended_at)
            self.assertEqual(result.end_reason, reason)
            event = ManagerTimelineEntry.objects.get(
                source_type='career_end',
                source_key=f'career_end:{career.pk}',
            )
            self.assertEqual(event.title, CAREER_END_TITLES[reason])
            self.assertEqual(event.category, 'status')
            self.assertTrue(event.system_entry)
            self.assertEqual(event.status, ManagerTimelineEntry.STATUS_APPROVED)

            # Replaying either the career close or its materialization must not
            # create a second visible status card.
            self.assertIsNone(
                finish_manager_career(
                    manager, club, ended_at=ended_at, reason=reason
                )
            )
            self.assertEqual(create_career_end_event(result).pk, event.pk)
            self.assertEqual(
                ManagerTimelineEntry.objects.filter(manager=manager).count(), 1
            )

    def test_first_youth_promotion_is_once_per_manager(self):
        manager = self._manager('Youth Manager')
        club = self._club('Youth Club')
        first_player = Player.objects.create(
            first_name='First',
            last_name='Talent',
            age=17,
            position='ST',
            club=club,
        )
        second_player = Player.objects.create(
            first_name='Second',
            last_name='Talent',
            age=18,
            position='ST',
            club=club,
        )

        first = create_first_youth_promotion_event(
            manager, first_player, club, date(2026, 4, 1)
        )
        replay = create_first_youth_promotion_event(
            manager, second_player, club, date(2026, 5, 1)
        )

        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(first.source_key, f'youth_promotion:{manager.pk}:first')
        self.assertEqual(first.player_id, first_player.pk)
        self.assertEqual(first.event_date, date(2026, 4, 1))
        self.assertEqual(first.category, 'jugend')
        self.assertEqual(first.tone, 'green')
        self.assertTrue(first.system_entry)
        self.assertEqual(
            ManagerTimelineEntry.objects.filter(
                manager=manager, source_type='youth_promotion'
            ).count(),
            1,
        )

    def test_final_events_use_gold_for_winner_red_for_loser_and_are_idempotent(self):
        home = self._club('Final Home')
        away = self._club('Final Away')
        home_manager = self._manager('Final Home Manager')
        away_manager = self._manager('Final Away Manager')
        fixture = self._final_fixture(
            season='2025/26',
            home=home,
            away=away,
            winner=home,
            home_manager=home_manager,
            away_manager=away_manager,
        )

        first = create_final_events(fixture)
        replay = create_final_events(fixture)

        self.assertEqual(len(first), 2)
        self.assertEqual([event.pk for event in replay], [event.pk for event in first])
        self.assertEqual(
            ManagerTimelineEntry.objects.filter(source_type='cup_final').count(), 2
        )
        winner = ManagerTimelineEntry.objects.get(manager=home_manager)
        loser = ManagerTimelineEntry.objects.get(manager=away_manager)
        self.assertTrue(winner.show_trophy)
        self.assertEqual(winner.tone, 'gold')
        self.assertFalse(loser.show_trophy)
        self.assertEqual(loser.tone, 'red')
        self.assertEqual(winner.result_text, '2:1')
        self.assertEqual(loser.opponent_name, home.name)
        self.assertEqual(winner.event_date, date(2026, 5, 10))

    def test_final_uses_kickoff_manager_snapshot_after_club_changes_manager(self):
        home = self._club('Snapshot Home')
        away = self._club('Snapshot Away')
        kickoff_home_manager = self._manager('Kickoff Home Manager')
        current_home_manager = self._manager('Current Home Manager')
        away_manager = self._manager('Kickoff Away Manager')
        fixture = self._final_fixture(
            season='2026/27',
            home=home,
            away=away,
            winner=home,
            home_manager=kickoff_home_manager,
            away_manager=away_manager,
        )
        home.managed_by = current_home_manager
        home.save(update_fields=['managed_by'])

        create_final_events(fixture)

        self.assertTrue(
            ManagerTimelineEntry.objects.filter(
                manager=kickoff_home_manager,
                source_key=f'cup_final:{fixture.pk}:manager:{kickoff_home_manager.pk}',
            ).exists()
        )
        self.assertFalse(
            ManagerTimelineEntry.objects.filter(manager=current_home_manager).exists()
        )

    def test_away_winner_ticket_keeps_canonical_home_away_orientation(self):
        from game.views import _timeline_entry_js

        home = self._club('Canonical Home')
        away = self._club('Canonical Away')
        home_manager = self._manager('Canonical Home Manager')
        away_manager = self._manager('Canonical Away Manager')
        fixture = self._final_fixture(
            season='2028/29',
            home=home,
            away=away,
            winner=away,
            home_manager=home_manager,
            away_manager=away_manager,
        )
        fixture.home_goals_90 = 1
        fixture.away_goals_90 = 2
        fixture.save(update_fields=['home_goals_90', 'away_goals_90'])

        create_final_events(fixture)
        away_event = ManagerTimelineEntry.objects.select_related(
            'cup_fixture__home_club',
            'cup_fixture__away_club',
            'cup_fixture__cup_round__cup_season__competition',
        ).get(manager=away_manager)
        ticket = _timeline_entry_js(away_event)['ticket']

        self.assertEqual(ticket['home']['name'], home.name)
        self.assertEqual(ticket['away']['name'], away.name)
        self.assertEqual(ticket['score'], '1:2')
        self.assertEqual(away_event.tone, 'gold')

    def test_final_event_requires_authoritative_competition_completion(self):
        home = self._club('Incomplete Home')
        away = self._club('Incomplete Away')
        home_manager = self._manager('Incomplete Home Manager')
        away_manager = self._manager('Incomplete Away Manager')
        fixture = self._final_fixture(
            season='2029/30',
            home=home,
            away=away,
            winner=home,
            home_manager=home_manager,
            away_manager=away_manager,
        )
        fixture.cup_round.status = CupRound.STATUS_SCHEDULED
        fixture.cup_round.save(update_fields=['status'])

        self.assertEqual(create_final_events(fixture), [])
        self.assertFalse(ManagerTimelineEntry.objects.exists())

    def test_final_resolves_unset_snapshots_from_manager_career_history(self):
        home = self._club('History Home')
        away = self._club('History Away')
        home_manager = self._manager('Historical Home Manager')
        away_manager = self._manager('Historical Away Manager')
        ManagerCareerEntry.objects.create(
            manager=home_manager,
            club=home,
            started_at=date(2025, 8, 1),
            ended_at=date(2026, 5, 10),
            active=False,
        )
        ManagerCareerEntry.objects.create(
            manager=away_manager,
            club=away,
            started_at=date(2025, 8, 1),
            active=True,
        )
        fixture = self._final_fixture(
            season='2027/28',
            home=home,
            away=away,
            winner=home,
        )

        create_final_events(fixture)

        self.assertTrue(
            ManagerTimelineEntry.objects.filter(manager=home_manager).exists()
        )
        self.assertTrue(
            ManagerTimelineEntry.objects.filter(manager=away_manager).exists()
        )

    def test_final_winner_title_card_is_not_rendered_twice(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='timeline-profile-user',
            password='x',
        )
        manager = ManagerProfile.objects.get(user=user)
        manager.name = 'Timeline Profile Manager'
        manager.save(update_fields=['name'])
        club = self._club('Visible Winner Club')
        opponent = self._club('Visible Loser Club')
        club.managed_by = manager
        club.save(update_fields=['managed_by'])
        title = ManagerCompetitionTitle.objects.create(
            manager=manager,
            club=club,
            competition=self.cup,
            competition_name=self.cup.name,
            season='2025/26',
            won_at=timezone.make_aware(datetime(2026, 5, 10, 20)),
        )
        ManagerTimelineEntry.objects.create(
            manager=manager,
            club=club,
            club_name=club.name,
            event_date=title.won_at.date(),
            category='finale',
            title=self.cup.name,
            body=f'{club.name} 2:1 {opponent.name}',
            result_text='2:1',
            opponent_name=opponent.name,
            competition_name=self.cup.name,
            show_trophy=True,
            system_entry=True,
            source_type='cup_final',
            source_key='cup_final:visible:manager:1',
            tone_override='gold',
            status=ManagerTimelineEntry.STATUS_APPROVED,
        )

        client = Client()
        client.force_login(user)
        response = client.get('/manager/profil/')

        self.assertEqual(response.status_code, 200)
        matching_events = [
            event for event in response.context['timeline_events_json']
            if event.get('title') == self.cup.name
        ]
        self.assertEqual(len(matching_events), 1)
        self.assertEqual(matching_events[0]['type'], 'finale')