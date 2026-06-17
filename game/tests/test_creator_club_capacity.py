"""game/tests/test_creator_club_capacity.py

Creator-Mode: Stadionkapazität (12 Tribünen-Einzelfelder) im Infrastruktur-Tab.

Abgedeckt:
  - Infrastruktur-Tab rendert die 12 editierbaren Tribünenfelder
  - creator_save_infrastruktur speichert alle 12 Felder; capacity_total = Summe
  - negative / ungültige Eingaben werden abgefangen (PositiveIntegerField)
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from game.models import Club, League, Stadium


class CreatorClubCapacityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='staff', password='pw', is_staff=True)
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='FC Kapazität', short_name='FCK', founded_year=2000,
            budget=Decimal('0'), league=self.league)
        self.stadium = Stadium.objects.create(
            club=self.club, name='Arena', city='Stadt')
        self.client.force_login(self.staff)

    def _post(self, **over):
        data = {
            'stadium_name': 'Arena', 'stadium_city': 'Stadt',
            'nord_standing': '1000', 'nord_seating': '2000', 'nord_vip': '50',
            'ost_standing': '1000', 'ost_seating': '2000', 'ost_vip': '50',
            'sued_standing': '1000', 'sued_seating': '2000', 'sued_vip': '50',
            'west_standing': '1000', 'west_seating': '2000', 'west_vip': '50',
        }
        data.update(over)
        return self.client.post(
            reverse('creator_save_infrastruktur', args=[self.club.id]), data)

    def test_infrastruktur_tab_renders_capacity_inputs(self):
        url = reverse('creator_club_edit', args=[self.club.id])
        resp = self.client.get(url + '?tab=infrastruktur')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Tribünenkapazität')
        for field in ('nord_standing', 'ost_seating', 'sued_vip', 'west_standing'):
            self.assertContains(resp, 'name="%s"' % field)

    def test_save_persists_all_twelve_fields(self):
        self._post()
        self.stadium.refresh_from_db()
        self.assertEqual(self.stadium.nord_standing, 1000)
        self.assertEqual(self.stadium.sued_vip, 50)
        self.assertEqual(self.stadium.west_seating, 2000)
        self.assertEqual(self.stadium.capacity_total, 4 * (1000 + 2000 + 50))

    def test_invalid_values_are_ignored(self):
        self.stadium.nord_standing = 500
        self.stadium.save()
        self._post(nord_standing='abc', ost_standing='-99')
        self.stadium.refresh_from_db()
        self.assertEqual(self.stadium.nord_standing, 500)
        self.assertEqual(self.stadium.ost_standing, 0)

    def test_excessive_value_is_clamped(self):
        self._post(nord_standing='999999999999')
        self.stadium.refresh_from_db()
        self.assertEqual(self.stadium.nord_standing, 500_000)
