from decimal import Decimal

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
            age=31,
            position='ST',
            source_positions='ST',
            potential=90,
            market_value=Decimal('100000000.00'),
            market_value_note='€80M - €120M',
            weekly_wage=Decimal('381200.00'),
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
