from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from game.manager_profile import (
    create_vacation_block,
    level_from_xp,
    level_threshold,
    select_title,
    title_payload,
)
from game.models import ManagerProfile, ManagerTitle


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

    def test_free_title_can_be_selected_but_locked_title_cannot(self):
        select_title(self.manager, 'quaelix')
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.active_title_key, 'quaelix')
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
