from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.models import Club, ClubRecord, League, Player


class HallOfFameViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('hall-view-user', password='test-password')
        self.league = League.objects.create(name='Ansichts-Liga', country='DE')
        self.club = Club.objects.create(
            name='Ansichtsverein',
            short_name='ANS',
            founded_year=1900,
            budget=Decimal('0'),
            league=self.league,
            managed_by=self.user.manager_profile,
        )
        self.opponent = Club.objects.create(
            name='Gegnerverein',
            short_name='GEG',
            founded_year=1901,
            budget=Decimal('0'),
            league=self.league,
        )
        self.player = Player.objects.create(
            club=self.club,
            first_name='Sichtbar',
            last_name='Rekord',
            position='ST',
            age=25,
        )
        self.client.force_login(self.user)

    def _record(self, *, source, value, holder_name, **extra):
        data = {
            'club': self.club,
            'record_key': 'top_scorer',
            'source': source,
            'value_numeric': Decimal(str(value)),
            'value_display': str(value),
            'holder_name': holder_name,
            'holder_player': self.player,
        }
        data.update(extra)
        return ClubRecord.objects.create(**data)

    def test_entrance_renders_all_navigation_destinations(self):
        response = self.client.get(reverse('management_halloffame'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['hall_room'], 'entrance')
        self.assertContains(response, 'Eingang')
        self.assertContains(response, 'Spieler')
        self.assertContains(response, 'Trainer')
        self.assertContains(response, 'Verein')

    def test_real_history_keeps_seed_until_sim_record_is_better(self):
        self._record(
            source=ClubRecord.SOURCE_SEED,
            value=100,
            holder_name='Historische Legende',
        )
        self._record(
            source=ClubRecord.SOURCE_SIM,
            value=99,
            holder_name='Simulationsrekord',
        )

        response = self.client.get(reverse('management_halloffame'), {'raum': 'player'})

        self.assertContains(response, 'Historische Legende')
        self.assertNotContains(response, 'Simulationsrekord')

        ClubRecord.objects.filter(
            club=self.club,
            record_key='top_scorer',
            source=ClubRecord.SOURCE_SIM,
        ).update(value_numeric=Decimal('101'), value_display='101')

        response = self.client.get(reverse('management_halloffame'), {'raum': 'player'})
        self.assertContains(response, 'Simulationsrekord')
        self.assertNotContains(response, 'Historische Legende')

    def test_new_history_contains_only_sim_records_and_player_link(self):
        self._record(
            source=ClubRecord.SOURCE_SEED,
            value=150,
            holder_name='Nur Archiv',
        )
        self._record(
            source=ClubRecord.SOURCE_SIM,
            value=151,
            holder_name='Spielbare Legende',
        )

        response = self.client.get(
            reverse('management_halloffame'),
            {'raum': 'player', 'modus': 'neu'},
        )

        self.assertEqual(response.context['hall_mode'], 'neu')
        self.assertContains(response, 'Spielbare Legende')
        self.assertNotContains(response, 'Nur Archiv')
        self.assertContains(response, reverse('player_detail', kwargs={'player_id': self.player.pk}))
        self.assertContains(response, 'Dieser Rekord wartet noch auf seine Geschichte.')

    def test_club_wall_has_sixteen_slots_and_uses_season_without_year(self):
        ClubRecord.objects.create(
            club=self.club,
            record_key='biggest_win',
            source=ClubRecord.SOURCE_SIM,
            value_numeric=Decimal('5'),
            value_display='5:0',
            holder_name=self.club.name,
            opponent_name=self.opponent.name,
            opponent_club=self.opponent,
            season='4',
        )

        response = self.client.get(
            reverse('management_halloffame'),
            {'raum': 'club', 'modus': 'neu'},
        )

        self.assertEqual(len(response.context['club_slots']), 16)
        self.assertContains(response, 'Saison #4')
        self.assertNotContains(response, '2026')
        self.assertContains(response, reverse('club_detail', kwargs={'club_id': self.opponent.pk}))