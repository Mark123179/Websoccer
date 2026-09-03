from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from game.manager_profile import (
    award_login_reward,
    create_vacation_block,
    level_from_xp,
    level_threshold,
    select_title,
    title_payload,
)
from game.models import Club, ClubPublicProfile, League, ManagerProfile, ManagerTitle


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
        self.assertContains(response, 'data-open-edit-profile')

    def test_profile_renders_nine_kpis_and_resolved_trophy_urls(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('manager_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'REGISTRIERT AM')
        self.assertContains(response, 'class="mp-kpi-cell"', count=9)
        self.assertNotContains(response, '/static/assets/trophies/')
        self.assertNotContains(response, 'TROPHÄENSAMMLUNG')
        self.assertContains(response, 'TROPHÄENVITRINE')
        self.assertContains(response, 'data-trophy-all')
        self.assertContains(response, 'var perPage = 15')

    def test_trophy_action_and_vitrine_exist_on_every_manager_profile_tab(self):
        self.client.force_login(self.user)

        for tab in ('profil', 'mannschaftsfotos', 'einstellungen'):
            with self.subTest(tab=tab):
                response = self.client.get(reverse('manager_profile'), {'tab': tab})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-trophy-all')
                self.assertContains(response, 'id="mpTrophyVitrine"')
                self.assertContains(response, 'id="mpTrophyVitrineShelf"')

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
