from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game.manager_profile import (
    award_login_reward,
    create_vacation_block,
    level_from_xp,
    level_threshold,
    current_title,
    select_title,
    title_payload,
)
from game.models import (
    Club,
    ClubPublicProfile,
    ClubTrophy,
    League,
    LeagueSeasonState,
    LeagueStandings,
    ManagerProfile,
    ManagerCompetitionTitle,
    ManagerTeamPhoto,
    ManagerTitle,
    SeasonFixture,
    SimulatedMatch,
)
from game.season_service import record_manager_competition_title


class ManagerProfileHandoffTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='profile-handoff',
            password='test-password',
        )
        self.manager = ManagerProfile.objects.get(user=self.user)

    def test_level_curve_starts_at_800_and_adds_100_per_level(self):
        self.assertEqual(level_threshold(2), 800)
        self.assertEqual(level_threshold(3), 1700)
        self.assertEqual(level_threshold(4), 2700)
        self.assertEqual(level_from_xp(799), 1)
        self.assertEqual(level_from_xp(800), 2)

    def test_login_reward_progression_is_daily_and_idempotent(self):
        with patch('game.manager_profile.timezone.localdate', return_value=date(2026, 8, 28)):
            first = award_login_reward(self.manager)
            repeated = award_login_reward(self.manager)
        self.manager.refresh_from_db()
        self.assertEqual(first['points_today'], 5)
        self.assertEqual(repeated['points_today'], 5)
        self.assertEqual(self.manager.login_streak, 1)
        self.assertEqual(self.manager.xp, 5)

        with patch('game.manager_profile.timezone.localdate', return_value=date(2026, 8, 29)):
            second = award_login_reward(self.manager)
        self.manager.refresh_from_db()
        self.assertEqual(second['points_today'], 10)
        self.assertEqual(self.manager.login_streak, 2)
        self.assertEqual(self.manager.xp, 15)

    def test_login_streak_breaks_after_missed_day(self):
        self.manager.login_streak = 6
        self.manager.login_last_date = date(2026, 8, 25)
        self.manager.login_day14_awarded = True
        self.manager.save(update_fields=[
            'login_streak', 'login_last_date', 'login_day14_awarded',
        ])
        with patch('game.manager_profile.timezone.localdate', return_value=date(2026, 8, 28)):
            result = award_login_reward(self.manager)
        self.manager.refresh_from_db()
        self.assertEqual(result['points_today'], 5)
        self.assertEqual(self.manager.login_streak, 1)
        self.assertFalse(self.manager.login_day14_awarded)

    def test_login_milestones_add_bonus_xp(self):
        self.manager.login_streak = 13
        self.manager.login_last_date = date(2026, 8, 27)
        self.manager.save(update_fields=['login_streak', 'login_last_date'])
        with patch('game.manager_profile.timezone.localdate', return_value=date(2026, 8, 28)):
            day14 = award_login_reward(self.manager)
        self.assertEqual(day14['points_today'], 150)

        self.manager.refresh_from_db()
        self.manager.login_streak = 29
        self.manager.login_last_date = date(2026, 8, 27)
        self.manager.login_day14_awarded = True
        self.manager.save(update_fields=[
            'login_streak', 'login_last_date', 'login_day14_awarded',
        ])
        with patch('game.manager_profile.timezone.localdate', return_value=date(2026, 8, 28)):
            day30 = award_login_reward(self.manager)
        self.assertEqual(day30['points_today'], 300)

    def test_free_title_can_be_selected_but_locked_title_cannot(self):
        select_title(self.manager, 'quaelix')
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.active_title, 'quaelix')
        with self.assertRaises(ValueError):
            select_title(self.manager, 'pokaljaeger')

    def test_unlockable_title_is_permanent_after_progress_reaches_target(self):
        self.manager.title_progress = {'pokalsiege': 1}
        self.manager.save(update_fields=['title_progress'])
        payload = title_payload(self.manager)
        self.assertTrue(ManagerTitle.objects.filter(
            manager=self.manager,
            title_key='pokaljaeger',
        ).exists())
        self.manager.title_progress = {'pokalsiege': 0}
        self.manager.save(update_fields=['title_progress'])
        self.assertIn('pokaljaeger', {
            title['key'] for title in title_payload(self.manager)['unlockable']
            if title['unlocked']
        })

    def test_vacation_requires_five_days_and_has_fourteen_day_budget(self):
        start = date.today() + timedelta(days=1)
        with self.assertRaises(ValueError):
            create_vacation_block(self.manager, 1, start, start + timedelta(days=3))
        first = create_vacation_block(self.manager, 1, start, start + timedelta(days=8))
        self.assertEqual(first.day_count, 9)
        second_start = start + timedelta(days=12)
        create_vacation_block(
            self.manager,
            1,
            second_start,
            second_start + timedelta(days=4),
        )
        with self.assertRaises(ValueError):
            create_vacation_block(
                self.manager,
                1,
                second_start + timedelta(days=8),
                second_start + timedelta(days=12),
            )

    def test_profile_does_not_force_name_onboarding_for_existing_account(self):
        self.manager.name_confirmed = False
        self.manager.save(update_fields=['name_confirmed'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('manager_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'mpOnboardingBanner')
        self.assertNotContains(response, 'not name_confirmed')
        self.assertNotContains(response, 'Profil bearbeiten')
        self.assertNotContains(response, 'data-open-edit-profile')
        self.assertContains(response, 'data-title-edit')

    def test_trainer_type_is_visible_title_until_an_explicit_title_is_selected(self):
        self.manager.trainer_type = 'taktikfuchs'
        self.manager.active_title = None
        self.manager.save(update_fields=['trainer_type', 'active_title'])

        self.assertEqual(current_title(self.manager), 'Taktikfuchs')
        self.assertEqual(title_payload(self.manager)['active_key'], 'taktikfuchs')
        self.client.force_login(self.user)
        response = self.client.get(reverse('manager_profile'))
        self.assertContains(
            response,
            '<span id="mpSidebarRole" data-active-manager-title>Taktikfuchs</span>',
            html=True,
        )
        self.assertContains(
            response,
            '<span class="mp-type-badge" data-active-manager-title>Taktikfuchs</span>',
            html=True,
        )
        self.assertNotContains(response, 'Kein Titel gewählt')

    def test_registered_manager_name_cannot_be_changed_from_profile_endpoint(self):
        self.manager.name = 'Fest registriert'
        self.manager.save(update_fields=['name'])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('update_manager_profile'),
            {'display_name': 'Neuer Name'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.name, 'Fest registriert')
        self.assertNotIn('display_name', response.json())

    def test_profile_renders_nine_kpis_and_resolved_trophy_urls(self):
        self.manager.inactivity_season_count = 2
        self.manager.inactivity_streak = 1
        self.manager.save(update_fields=['inactivity_season_count', 'inactivity_streak'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('manager_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'REGISTRIERT AM')
        self.assertContains(response, 'class="mp-kpi-cell', count=9)
        self.assertNotContains(response, '/static/assets/trophies/')
        self.assertNotContains(response, 'TROPHÄENSAMMLUNG')
        self.assertContains(response, 'TROPHÄENVITRINE')
        self.assertContains(response, 'data-trophy-all')
        self.assertContains(response, 'var perPage = 15')
        self.assertContains(response, '2<span>/5</span>')
        self.assertContains(response, '1<span>/3</span>')
        self.assertContains(response, 'Stufen-Regeln')
        self.assertContains(response, 'class="mp-kpi-login"')
        self.assertContains(response, 'class="mp-achievement2"', count=4)
        self.assertEqual(
            [item['key'] for item in response.context['title_progress_cards']],
            ['pokaljaeger', 'serienmeister', 'weltenbummler', 'aufstiegsheld'],
        )
        self.assertContains(response, 'Pokaljäger')
        self.assertContains(response, 'Serienmeister')
        self.assertContains(response, 'Weltenbummler')
        self.assertContains(response, 'Aufstiegsheld')
        self.assertContains(response, 'mp-photo-map-scene')
        self.assertContains(response, 'baseScale * 2.6')
        self.assertNotContains(response, 'markers.length === 1 && Array.isArray(COUNTRY_BBOX)')
        self.assertContains(response, 'class="mp-trainer-title is-locked"', count=9)
        self.assertContains(response, '% der Manager')
        self.assertContains(response, '<rect x="3" y="7" width="10" height="7" rx="1"/>', html=False)

    def test_trophy_action_and_vitrine_exist_on_every_manager_profile_tab(self):
        self.client.force_login(self.user)

        for tab in ('profil', 'mannschaftsfotos', 'einstellungen'):
            with self.subTest(tab=tab):
                response = self.client.get(reverse('manager_profile'), {'tab': tab})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-trophy-all')
                self.assertContains(response, 'id="mpTrophyVitrine"')
                self.assertContains(response, 'id="mpTrophyVitrineShelf"')

    def test_team_photo_rosters_render_18_40_and_60_players_in_handoff_rows(self):
        for season, player_count in enumerate((18, 40, 60), start=1):
            ManagerTeamPhoto.objects.create(
                manager=self.manager,
                season=season,
                roster_names=[
                    f'Spieler {player_number:02d}'
                    for player_number in range(1, player_count + 1)
                ],
            )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('manager_profile'),
            {'tab': 'mannschaftsfotos'},
        )

        self.assertEqual(response.status_code, 200)
        for player_count, row_count in ((18, 2), (40, 4), (60, 5)):
            with self.subTest(player_count=player_count):
                self.assertContains(
                    response,
                    f'class="mp-card2 mp-team-photo-card mp-team-photo-card--{row_count}-rows"',
                )
                self.assertContains(
                    response,
                    f'data-roster-count="{player_count}"',
                )
                self.assertContains(
                    response,
                    f'data-roster-rows="{row_count}"',
                )
                self.assertContains(
                    response,
                    f'aria-label="{player_count} Spieler in {row_count} Reihen"',
                )
        self.assertContains(response, '<li>Spieler 60</li>', html=True)
        self.assertNotContains(response, 'Noch kein Mannschaftsfoto')

    def test_team_photo_empty_state_remains_separately_covered(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('manager_profile'),
            {'tab': 'mannschaftsfotos'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Noch kein Mannschaftsfoto')
        self.assertContains(response, 'mp-team-photo-empty')
        self.assertNotContains(response, 'data-roster-count')

    def test_team_photo_handoff_rows_fit_the_fixed_1440_artboard(self):
        css_path = finders.find('game/css/manager-profile.css')
        with open(css_path, encoding='utf-8') as css_file:
            css = ''.join(css_file.read().split())

        self.assertIn('grid-auto-flow:column', css)
        self.assertIn('grid-auto-columns:minmax(0,1fr)', css)
        for row_count in (2, 4, 5):
            with self.subTest(row_count=row_count):
                self.assertIn(
                    f'.mp-team-photo-card--{row_count}-rows'
                    f'.mp-team-photo-roster{{grid-template-rows:repeat({row_count},minmax(0,auto))',
                    css,
                )

    def test_settings_match_handoff_fields_and_column_order(self):
        self.manager.residence = 'Köln, Deutschland'
        self.manager.birth_date = date(1987, 6, 12)
        self.manager.save(update_fields=['residence', 'birth_date'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('manager_profile'), {'tab': 'einstellungen'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['privacy_fields']), 10)
        self.assertNotIn('title', {
            field['key'] for field in response.context['privacy_fields']
        })
        self.assertContains(response, 'Geburtsdatum')
        self.assertContains(response, 'id="mpBirthDate"')
        self.assertContains(response, 'value="1987-06-12"')
        self.assertContains(response, 'id="mpResidence"')
        self.assertContains(response, 'value="Köln, Deutschland"')
        left_column = response.content.decode().split(
            '<div class="mp-settings-col">', 2
        )[1]
        self.assertIn('mp-card-vacation', left_column)

    def test_account_settings_save_residence(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('update_manager_profile'),
            {'residence': 'Köln, Deutschland'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.residence, 'Köln, Deutschland')

    def test_account_settings_save_change_and_clear_birth_date(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('update_manager_profile'),
            {'birth_date': '1990-04-23'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.birth_date, date(1990, 4, 23))

        response = self.client.post(
            reverse('update_manager_profile'),
            {'birth_date': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.manager.refresh_from_db()
        self.assertIsNone(self.manager.birth_date)

    def test_account_settings_reject_invalid_or_future_birth_date(self):
        self.manager.birth_date = date(1990, 4, 23)
        self.manager.save(update_fields=['birth_date'])
        self.client.force_login(self.user)

        for birth_date in ('kein-datum', '2026-02-30', '2999-01-01'):
            with self.subTest(birth_date=birth_date):
                response = self.client.post(
                    reverse('update_manager_profile'),
                    {'birth_date': birth_date},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )

                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()['ok'])
                self.manager.refresh_from_db()
                self.assertEqual(self.manager.birth_date, date(1990, 4, 23))

    def test_birthday_visibility_controls_public_profile(self):
        self.manager.birth_date = date(1987, 6, 12)
        self.manager.visibility_settings = {'birthday': 'private'}
        self.manager.save(update_fields=['birth_date', 'visibility_settings'])

        response = self.client.get(
            reverse('public_manager_profile', args=[self.user.username])
        )
        self.assertNotContains(response, '12.06.1987')

        self.manager.visibility_settings = {'birthday': 'all'}
        self.manager.save(update_fields=['visibility_settings'])
        response = self.client.get(
            reverse('public_manager_profile', args=[self.user.username])
        )
        self.assertContains(response, '12.06.1987')

    def test_profile_uses_current_club_stadium_and_one_persisted_active_title(self):
        league = League.objects.create(name='Profil-Liga', country='Deutschland')
        club = Club.objects.create(
            name='Aktueller Profilverein',
            short_name='APV',
            founded_year=1900,
            budget=Decimal('1000000.00'),
            league=league,
            managed_by=self.manager,
        )
        ClubPublicProfile.objects.create(
            club=club,
            stadium_image_static_path='game/images/stadiums/germany/b-dortmund.jpg',
        )
        ClubTrophy.objects.create(
            club=club,
            competition_name='Bundesliga',
            trophy_asset_id='22',
        )
        select_title(self.manager, 'quaelix')
        self.client.force_login(self.user)

        response = self.client.get(reverse('manager_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_title'], 'Quälix')
        self.assertEqual(
            response.context['manager']['active_type'],
            response.context['active_title'],
        )
        self.assertEqual(
            response.context['current_manager']['title'],
            response.context['active_title'],
        )
        self.assertEqual(
            response.context['current_manager']['role'],
            response.context['active_title'],
        )
        self.assertContains(response, '>Quälix</span>')
        self.assertContains(
            response,
            "--mp-current-stadium-image:url('/static/game/images/stadiums/germany/b-dortmund.jpg')",
        )
        self.assertNotContains(response, 'fc-bayern-stadium.jpg')
        self.assertEqual(response.context['manager']['trophies_list_mini'], [])
        self.assertEqual(response.context['manager']['trophies'], 0)
        self.assertEqual(response.context['trophies_list'], [])
        self.assertContains(response, 'Noch keine Trophäen in der Vitrine.')

    def test_kpis_ignore_club_history_and_use_simulated_matches_and_last_seen(self):
        league = League.objects.create(name='KPI-Liga', country='Deutschland')
        club = Club.objects.create(
            name='KPI-Verein',
            short_name='KPI',
            founded_year=1900,
            budget=Decimal('1000000.00'),
            league=league,
            managed_by=self.manager,
        )
        opponent = Club.objects.create(
            name='KPI-Gegner',
            short_name='KPG',
            founded_year=1901,
            budget=Decimal('1000000.00'),
            league=league,
        )
        ClubTrophy.objects.create(
            club=club,
            competition_name='Bundesliga',
            count=8,
            trophy_asset_id='22',
        )
        ClubTrophy.objects.create(
            club=club,
            competition_name='DFB-Pokal',
            count=5,
            trophy_asset_id='1301397',
        )
        ClubTrophy.objects.create(
            club=club,
            competition_name='DFL-Supercup',
            count=4,
            trophy_asset_id='1301395',
        )
        SimulatedMatch.objects.create(
            home_club=club,
            away_club=opponent,
            home_goals=2,
            away_goals=1,
        )
        self.manager.last_seen = timezone.now()
        self.manager.save(update_fields=['last_seen'])
        self.client.force_login(self.user)

        response = self.client.get(reverse('manager_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['manager']['trophies'], 0)
        self.assertEqual(response.context['manager']['games_total'], 1)
        self.assertEqual(response.context['manager']['win_rate'], '100%')
        self.assertEqual(
            response.context['manager']['last_login_date'],
            timezone.localdate().strftime('%d.%m.%Y'),
        )
        self.assertEqual(response.context['manager']['trophies_list_mini'], [])
        self.assertEqual(response.context['trophies_list'], [])
        self.assertContains(response, '0 TITEL')
        self.assertNotContains(response, '8×')
        self.assertNotContains(response, '5×')
        self.assertContains(response, '1 S · 0 U · 0 N')

    def test_profile_uses_only_personal_titles_and_keeps_winning_club(self):
        league = League.objects.create(name='Titel-Liga', country='Deutschland')
        old_club = Club.objects.create(
            name='Titelverein', short_name='TV', founded_year=1900,
            budget=Decimal('1000000.00'), league=league,
        )
        new_club = Club.objects.create(
            name='Neuer Verein', short_name='NV', founded_year=1901,
            budget=Decimal('1000000.00'), league=league, managed_by=self.manager,
        )
        ManagerCompetitionTitle.objects.create(
            manager=self.manager,
            club=old_club,
            competition=league,
            competition_name=league.name,
            season='2026',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('manager_profile'))

        self.assertEqual(response.context['manager']['trophies'], 1)
        self.assertEqual(response.context['trophies_list'][0]['count'], 1)
        self.assertContains(response, 'Titelverein')
        self.assertContains(response, 'Saison 2026')
        self.assertNotContains(response, '<b>Neuer Verein</b>')

    def test_recording_competition_title_is_idempotent_and_snapshots_manager(self):
        league = League.objects.create(name='Meister-Liga', country='Deutschland')
        club = Club.objects.create(
            name='Meisterverein', short_name='MV', founded_year=1900,
            budget=Decimal('1000000.00'), league=league, managed_by=self.manager,
        )

        first = record_manager_competition_title(league, '2026', club)
        second = record_manager_competition_title(league, '2026', club)
        club.managed_by = None
        club.save(update_fields=['managed_by'])

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ManagerCompetitionTitle.objects.count(), 1)
        title = ManagerCompetitionTitle.objects.get()
        self.assertEqual(title.manager, self.manager)
        self.assertEqual(title.club, club)
        self.assertEqual(title.competition_name, 'Meister-Liga')
        self.assertEqual(title.season, '2026')

    def test_league_completion_records_each_season_once(self):
        from game.season_service import close_matchday

        league = League.objects.create(name='Mehrjahresliga', country='Deutschland')
        champion = Club.objects.create(
            name='Serienmeister', short_name='SM', founded_year=1900,
            budget=Decimal('1000000.00'), league=league, managed_by=self.manager,
        )
        opponent = Club.objects.create(
            name='Verfolger', short_name='VF', founded_year=1901,
            budget=Decimal('1000000.00'), league=league,
        )
        for season in ('1', '2'):
            SeasonFixture.objects.create(
                league=league, season=season, matchday=1,
                home_club=champion, away_club=opponent, is_played=True,
            )
            LeagueStandings.objects.create(
                league=league, club=champion, season=season,
                position=1, points=3,
            )
            LeagueStandings.objects.create(
                league=league, club=opponent, season=season,
                position=2, points=0,
            )
            LeagueSeasonState.objects.create(
                league=league, season=season,
                current_matchday=1, is_simulated=True,
            )
            close_matchday(league, season)
            close_matchday(league, season)

        self.assertEqual(
            set(self.manager.competition_titles.values_list('season', flat=True)),
            {'1', '2'},
        )
        self.assertEqual(self.manager.competition_titles.count(), 2)

    def test_unmanaged_league_is_not_retroactively_awarded_on_retry(self):
        from game.season_service import close_matchday

        league = League.objects.create(name='Managerlose Liga', country='Deutschland')
        champion = Club.objects.create(
            name='Managerloser Meister', short_name='MM', founded_year=1900,
            budget=Decimal('1000000.00'), league=league,
        )
        opponent = Club.objects.create(
            name='Zweiter', short_name='ZW', founded_year=1901,
            budget=Decimal('1000000.00'), league=league,
        )
        SeasonFixture.objects.create(
            league=league, season='1', matchday=1,
            home_club=champion, away_club=opponent, is_played=True,
        )
        LeagueStandings.objects.create(
            league=league, club=champion, season='1', position=1, points=3,
        )
        LeagueSeasonState.objects.create(
            league=league, season='1',
            current_matchday=1, is_simulated=True,
        )

        close_matchday(league, '1')
        champion.managed_by = self.manager
        champion.save(update_fields=['managed_by'])
        close_matchday(league, '1')

        self.assertFalse(self.manager.competition_titles.exists())

    def test_historical_club_trophies_are_never_backfilled(self):
        league = League.objects.create(name='Historische Liga', country='Deutschland')
        club = Club.objects.create(
            name='Traditionsverein', short_name='TV', founded_year=1900,
            budget=Decimal('1000000.00'), league=league, managed_by=self.manager,
        )
        ClubTrophy.objects.create(
            club=club, competition_name='Historische Liga', count=12,
        )

        self.assertFalse(
            ManagerCompetitionTitle.objects.filter(manager=self.manager).exists()
        )

        self.client.force_login(self.user)
        self.client.post(
            reverse('set_trainer_type'),
            {'trainer_type_key': 'serienmeister'},
        )
        self.manager.refresh_from_db()
        self.assertNotEqual(self.manager.trainer_type, 'serienmeister')
