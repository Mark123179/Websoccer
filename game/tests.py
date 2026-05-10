from decimal import Decimal
from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Club, League, Player, PlayerStrengthProfile


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
            primary_position='Mittelstürmer',
            source_positions='ST',
            potential=90,
            market_value=Decimal('100000000.00'),
            salary_per_match=Decimal('500000.00'),
            club=self.club,
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
        self.assertContains(response, 'Vereinsübersicht')
        self.assertContains(response, 'Ø Stärke')

    def test_club_detail_renders_squad_metrics(self):
        response = self.client.get(
            reverse('club_detail', kwargs={'club_id': self.club.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kadergröße')
        self.assertContains(response, 'Marktwert')

    def test_player_detail_renders_profile_shell(self):
        player = Player.objects.get(transfermarkt_id=132098)
        response = self.client.get(
            reverse('player_detail', kwargs={'player_id': player.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Harry Kane')
        self.assertContains(response, 'Gehalt/Spiel')
