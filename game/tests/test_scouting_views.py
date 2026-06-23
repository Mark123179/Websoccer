"""View-Tests für das Scouting-System.

Deckt ab: Fund-Kachel (öffentliche Sicht, real_life_club ohne Stärke-Leak),
Ausbau-View (POST), Ablehnen-View (POST) — jeweils mit Vereins-Eigentümerschaft
über current_manager_club(user=...).
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from game.club_import.season import get_current_tm_season_id
from game.models import (
    League, Club, Player, PlayerStrengthProfile, ManagerProfile,
    ScoutingAssignment, ScoutingFind, ScoutingDepartment,
)
from game.scouting import department
from game.views_scouting import _find_card


def _pool_player(nat='Türkei', last='Spieler', real_life_club=None):
    player = Player.objects.create(
        first_name='Pool', last_name=last, age=22,
        position='Sturm', main_position_1='ST', nationalities=nat,
        market_value=Decimal('4000000'), potential=80,
        pool_status=Player.POOL_STATUS_SCOUTABLE, real_life_club=real_life_club,
    )
    PlayerStrengthProfile.objects.create(player=player, base_strength=Decimal('72'))
    return player


class FindCardTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Süper Lig', country='Türkei')
        self.rl_club = Club.objects.create(
            name='Galatasaray', short_name='GS', founded_year=1905,
            budget=Decimal('50000000.00'), league=self.league)

    def test_card_uses_real_life_club_and_league(self):
        player = _pool_player(real_life_club=self.rl_club)
        a = ScoutingAssignment.objects.create(
            club=self.rl_club, manager=None, scope_type='country', scope_key='TR',
            position='ST', profile='ergaenzung', department_level=0,
            cost=Decimal('250000'), duration_days=18,
            completes_on=date(2026, 6, 23),
            season_id=get_current_tm_season_id(), status=ScoutingAssignment.STATUS_ACTIVE,
        )
        find = ScoutingFind.objects.create(
            assignment=a, player=player, order=0, min_bid=Decimal('5000000'),
            status=ScoutingFind.STATUS_OFFERED)
        card = _find_card(find, set())
        self.assertEqual(card['rl_club'], 'Galatasaray')
        self.assertEqual(card['rl_liga'], 'Süper Lig')
        # Keine geheimen Felder nach außen.
        self.assertNotIn('base_strength', card)
        self.assertNotIn('potential', card)

    def test_card_without_real_life_club_uses_dash(self):
        player = _pool_player(real_life_club=None)
        a = ScoutingAssignment.objects.create(
            club=self.rl_club, manager=None, scope_type='country', scope_key='TR',
            position='ST', profile='ergaenzung', department_level=0,
            cost=Decimal('250000'), duration_days=18,
            completes_on=date(2026, 6, 23),
            season_id=get_current_tm_season_id(), status=ScoutingAssignment.STATUS_ACTIVE,
        )
        find = ScoutingFind.objects.create(
            assignment=a, player=player, order=0, min_bid=Decimal('5000000'),
            status=ScoutingFind.STATUS_OFFERED)
        card = _find_card(find, set())
        self.assertEqual(card['rl_club'], '—')
        self.assertEqual(card['rl_liga'], '—')


class ScoutingActionViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='boss', password='pw12345')
        # Eine ManagerProfile wird per post_save-Signal automatisch angelegt.
        self.manager = self.user.manager_profile
        self.league = League.objects.create(name='Bundesliga', country='Deutschland')
        self.club = Club.objects.create(
            name='Bayern', short_name='FCB', founded_year=1900,
            budget=Decimal('200000000.00'), league=self.league,
            managed_by=self.manager,
        )
        self.client.force_login(self.user)

    def test_upgrade_view_levels_up_department(self):
        resp = self.client.post(reverse('scouting_upgrade'))
        self.assertEqual(resp.status_code, 302)
        dept = ScoutingDepartment.objects.get(club=self.club)
        self.assertEqual(dept.level, 1)
        self.club.refresh_from_db()
        self.assertEqual(self.club.budget,
                         Decimal('200000000.00') - Decimal(department.upgrade_cost(0)))

    def test_reject_view_completes_active_assignment(self):
        a = ScoutingAssignment.objects.create(
            club=self.club, manager=self.manager, scope_type='country', scope_key='TR',
            position='ST', profile='ergaenzung', department_level=0,
            cost=Decimal('250000'), duration_days=18,
            completes_on=date(2026, 6, 23),
            season_id=get_current_tm_season_id(), status=ScoutingAssignment.STATUS_ACTIVE,
            finds_generated=True,
        )
        player = _pool_player()
        find = ScoutingFind.objects.create(
            assignment=a, player=player, order=0, min_bid=Decimal('5000000'),
            status=ScoutingFind.STATUS_OFFERED)
        resp = self.client.post(reverse('scouting_reject'))
        self.assertEqual(resp.status_code, 302)
        a.refresh_from_db(); find.refresh_from_db()
        self.assertEqual(a.status, ScoutingAssignment.STATUS_COMPLETED)
        self.assertEqual(find.status, ScoutingFind.STATUS_REJECTED)

    def test_reject_view_without_assignment_is_safe(self):
        resp = self.client.post(reverse('scouting_reject'))
        self.assertEqual(resp.status_code, 302)
