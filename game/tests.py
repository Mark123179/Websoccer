from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin import PlayerNationalityForm
from .models import (
    Club,
    League,
    Player,
    PlayerSourceRating,
    PlayerStrengthProfile,
)


@override_settings(ALLOWED_HOSTS=['testserver'])
class PageSmokeTests(TestCase):
    def setUp(self):
        league = League.objects.create(
            name='1. Bundesliga',
            country='Deutschland',
        )
        self.club = Club.objects.create(
            name='Borussia Dortmund',
            short_name='BVB',
            fm_inside_id=907,
            founded_year=1909,
            budget=Decimal('5000000.00'),
            league=league,
        )
        player = Player.objects.create(
            first_name='Harry',
            last_name='Kane',
            fm_inside_id=28049320,
            transfermarkt_id=132098,
            transfermarkt_profile_url='https://www.transfermarkt.de/harry-kane/profil/spieler/132098',
            transfermarkt_market_value_url='https://www.transfermarkt.de/harry-kane/marktwertverlauf/spieler/132098',
            date_of_birth=date(1993, 7, 28),
            nationalities='England, Irland',
            age=31,
            position='ST',
            primary_position='OM',
            source_positions='OM',
            main_position_1='ST',
            main_position_2='OM',
            secondary_position_1='ZM',
            potential=90,
            market_value=Decimal('100000000.00'),
            salary_per_match=Decimal('500000.00'),
            club=self.club,
            real_life_club=self.club,
        )
        PlayerSourceRating.objects.create(
            player=player,
            source=PlayerSourceRating.SOURCE_EA,
            rating=90,
            potential=90,
            source_version='FC 26 Testdaten',
        )
        PlayerSourceRating.objects.create(
            player=player,
            source=PlayerSourceRating.SOURCE_FM,
            rating=94,
            potential=95,
            source_version='FMInside Testdaten',
        )
        PlayerStrengthProfile.objects.create(
            player=player,
            base_strength=88,
            form_modifier=2,
        )

    def test_home_page_renders_dashboard(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Saisonvorbereitung')
        self.assertContains(response, 'Borussia Dortmund')

    def test_club_list_renders_club_metrics(self):
        response = self.client.get(reverse('club_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Borussia Dortmund')
        self.assertContains(response, '1. Bundesliga')

    def test_club_detail_renders_squad_metrics(self):
        response = self.client.get(
            reverse('club_detail', kwargs={'club_id': self.club.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1. Mannschaft')
        self.assertContains(response, 'Marktwert')
        self.assertContains(response, 'game/images/players/28049320.svg')
        self.assertContains(response, 'game/images/kits/907_home.svg')
        self.assertContains(response, 'game/images/flags/765.svg')
        self.assertContains(response, 'game/images/flags/789.svg')
        self.assertContains(response, 'https://www.transfermarkt.de/harry-kane/profil/spieler/132098')
        self.assertNotContains(response, 'https://www.transfermarkt.de/harry-kane/marktwertverlauf/spieler/132098')

    def test_player_detail_renders_profile_shell(self):
        player = Player.objects.get(transfermarkt_id=132098)
        response = self.client.get(
            reverse('player_detail', kwargs={'player_id': player.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Harry Kane')
        self.assertContains(response, 'Spielerprofil')
        self.assertContains(response, 'Gehalt pro Spiel')
        self.assertContains(response, 'WS-Verein')
        self.assertContains(
            response,
            'Die Reiter liegen jetzt in der Django-Verwaltung.',
        )

    def test_player_source_ratings_calculate_base_and_potential(self):
        player = Player.objects.get(transfermarkt_id=132098)

        self.assertEqual(player.calculated_base_strength, 184)
        self.assertEqual(player.calculated_potential_strength, 185)
        self.assertIn(
            'Base = EA + FM = 184',
            player.source_strength_explanation,
        )

    def test_player_admin_nationality_form_stores_two_dropdown_values(self):
        player = Player.objects.get(transfermarkt_id=132098)
        form = PlayerNationalityForm(
            data={
                'first_name': player.first_name,
                'last_name': player.last_name,
                'fm_inside_id': player.fm_inside_id,
                'transfermarkt_id': player.transfermarkt_id,
                'transfermarkt_profile_url': player.transfermarkt_profile_url,
                'transfermarkt_market_value_url': player.transfermarkt_market_value_url,
                'date_of_birth': player.date_of_birth,
                'nationality_1': 'England',
                'nationality_2': 'Irland',
                'age': player.age,
                'position': player.position,
                'primary_position': player.primary_position,
                'source_positions': player.source_positions,
                'main_position_1': 'ST',
                'main_position_2': 'OM',
                'main_position_3': '',
                'secondary_position_1': 'ZM',
                'secondary_position_2': '',
                'secondary_position_3': '',
                'potential': player.potential,
                'market_value': player.market_value,
                'salary_per_match': player.salary_per_match,
                'contract_until': player.contract_until,
                'club': player.club_id,
                'real_life_club': player.real_life_club_id,
                'ws_injury_type': '',
                'ws_injury_days_remaining': 0,
                'ws_suspension_reason': '',
                'ws_suspension_matches_remaining': 0,
            },
            instance=player,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved_player = form.save()
        self.assertEqual(saved_player.nationalities, 'England, Irland')
        self.assertEqual(saved_player.position, 'ST')
        self.assertEqual(saved_player.primary_position, 'ZM')
        self.assertEqual(saved_player.main_positions, ['ST', 'OM'])
        self.assertEqual(saved_player.secondary_positions, ['ZM'])

    def test_player_admin_club_dropdown_orders_career_end_first(self):
        Club.objects.create(
            name='Karrierende',
            short_name='KARR',
            founded_year=0,
            budget=Decimal('0.00'),
            league=self.club.league,
        )
        player = Player.objects.get(transfermarkt_id=132098)
        form = PlayerNationalityForm(instance=player)

        club_names = [
            club.name
            for club in form.fields['club'].queryset
        ]
        real_life_club_names = [
            club.name
            for club in form.fields['real_life_club'].queryset
        ]

        self.assertEqual(club_names[0], 'Karrierende')
        self.assertEqual(real_life_club_names[0], 'Karrierende')

    def test_player_admin_position_form_rejects_duplicate_positions(self):
        player = Player.objects.get(transfermarkt_id=132098)
        form = PlayerNationalityForm(
            data={
                'first_name': player.first_name,
                'last_name': player.last_name,
                'fm_inside_id': player.fm_inside_id,
                'transfermarkt_id': player.transfermarkt_id,
                'transfermarkt_profile_url': player.transfermarkt_profile_url,
                'transfermarkt_market_value_url': player.transfermarkt_market_value_url,
                'date_of_birth': player.date_of_birth,
                'nationality_1': 'England',
                'nationality_2': 'Irland',
                'age': player.age,
                'position': player.position,
                'primary_position': player.primary_position,
                'source_positions': player.source_positions,
                'main_position_1': 'ST',
                'main_position_2': '',
                'main_position_3': '',
                'secondary_position_1': 'ST',
                'secondary_position_2': '',
                'secondary_position_3': '',
                'potential': player.potential,
                'market_value': player.market_value,
                'salary_per_match': player.salary_per_match,
                'contract_until': player.contract_until,
                'club': player.club_id,
                'real_life_club': player.real_life_club_id,
                'ws_injury_type': '',
                'ws_injury_days_remaining': 0,
                'ws_suspension_reason': '',
                'ws_suspension_matches_remaining': 0,
            },
            instance=player,
        )

        self.assertFalse(form.is_valid())

    def test_player_admin_change_form_contains_management_tabs(self):
        player = Player.objects.get(transfermarkt_id=132098)
        admin_user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test-pass',
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse('admin:game_player_change', args=[player.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ws-admin-tabs')
        self.assertContains(response, 'SPIELERPROFIL')
        self.assertContains(response, 'STAERKE')
        self.assertContains(response, 'SOURCE')
        self.assertContains(response, 'SAISON')
        self.assertContains(response, 'KARRIERE')
        self.assertContains(response, 'TRANSFERHISTORIE WS')
        self.assertContains(response, 'GESCHICHTE')

