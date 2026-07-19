"""Tests für die Manager-Notizen-API (/api/notizen/), Task #717."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from game.models import ManagerNotes, ManagerProfile

User = get_user_model()


def _note(note_id='n1', title='Test', content='Inhalt', todos=None, updated=1000):
    return {
        'id': note_id,
        'title': title,
        'content': content,
        'todos': todos or [],
        'updatedAt': updated,
    }


class NotizenApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Ein post_save-Signal legt für jeden neuen User automatisch ein
        # ManagerProfile an — daher die Profile aus dem Signal übernehmen.
        cls.user_a = User.objects.create_user(username='mgr_a', password='pw')
        cls.user_b = User.objects.create_user(username='mgr_b', password='pw')
        cls.user_c = User.objects.create_user(username='kein_manager', password='pw')
        cls.manager_a = ManagerProfile.objects.get(user=cls.user_a)
        cls.manager_b = ManagerProfile.objects.get(user=cls.user_b)
        # Sonderfall ohne Profil (403-Pfad) explizit herstellen:
        ManagerProfile.objects.filter(user=cls.user_c).delete()
        cls.url = reverse('notizen_api')

    def _put(self, payload):
        return self.client.put(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_user_without_manager_profile_gets_403(self):
        self.client.force_login(self.user_c)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_empty_initially(self):
        self.client.force_login(self.user_a)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'notes': []})

    def test_put_persists_and_get_returns_notes(self):
        self.client.force_login(self.user_a)
        todos = [{'id': 't1', 'text': 'Punkt 1', 'done': True}]
        response = self._put({'notes': [_note(todos=todos)]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

        data = self.client.get(self.url).json()['notes']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['title'], 'Test')
        self.assertEqual(data[0]['todos'][0]['done'], True)

    def test_notes_isolated_between_managers(self):
        self.client.force_login(self.user_a)
        self._put({'notes': [_note(title='Geheim A')]})

        self.client.force_login(self.user_b)
        response = self.client.get(self.url)
        self.assertEqual(response.json(), {'notes': []})

        self._put({'notes': [_note(title='Notiz B')]})
        self.assertEqual(
            ManagerNotes.objects.get(manager=self.manager_a).data[0]['title'],
            'Geheim A',
        )
        self.assertEqual(
            ManagerNotes.objects.get(manager=self.manager_b).data[0]['title'],
            'Notiz B',
        )

    def test_notes_survive_club_independence(self):
        # Notizen hängen am ManagerProfile, nicht am Club — ein Vereinswechsel
        # (kein Club-Feld beteiligt) ändert nichts an den gespeicherten Daten.
        self.client.force_login(self.user_a)
        self._put({'notes': [_note(title='Bleibt')]})
        obj = ManagerNotes.objects.get(manager=self.manager_a)
        self.assertIsNone(obj.manager.club if hasattr(obj.manager, 'club') else None)
        self.assertEqual(obj.data[0]['title'], 'Bleibt')

    def test_put_invalid_json_returns_400(self):
        self.client.force_login(self.user_a)
        response = self.client.put(self.url, data='kein json', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_put_notes_not_a_list_returns_400(self):
        self.client.force_login(self.user_a)
        response = self._put({'notes': 'nope'})
        self.assertEqual(response.status_code, 400)

    def test_put_sanitizes_unknown_fields_and_clamps(self):
        self.client.force_login(self.user_a)
        raw = _note()
        raw['evil'] = '<script>'
        raw['title'] = 'x' * 1000
        response = self._put({'notes': [raw, 'kein-dict']})
        self.assertEqual(response.status_code, 200)
        data = self.client.get(self.url).json()['notes']
        self.assertEqual(len(data), 1)
        self.assertNotIn('evil', data[0])
        self.assertEqual(len(data[0]['title']), 300)

    def test_put_empty_list_deletes_all_notes(self):
        self.client.force_login(self.user_a)
        self._put({'notes': [_note()]})
        response = self._put({'notes': []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(self.url).json(), {'notes': []})

    def test_post_not_allowed(self):
        self.client.force_login(self.user_a)
        response = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 405)

    def test_oversized_payload_rejected(self):
        self.client.force_login(self.user_a)
        big = _note(content='x' * (300 * 1024))
        response = self._put({'notes': [big]})
        self.assertEqual(response.status_code, 413)
