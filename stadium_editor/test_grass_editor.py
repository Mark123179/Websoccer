import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from game.models import Club, League, Stadium
from .grass import GRASS_VARIANTS
from .image_validation import normalize_design_payload
from .models import StadiumDesign, StadiumGeometry
from .tests import _block, _geometry


class GrassEditorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('grass-editor-owner', password='test-only')
        league = League.objects.create(name='Grass editor test league', country='DE')
        self.club = Club.objects.create(
            name='Grass editor test club', short_name='GET', founded_year=1900,
            budget=0, league=league, managed_by=self.user.manager_profile,
        )
        self.stadium = Stadium.objects.create(
            club=self.club, name='Grass test stadium', city='Test', nord_seating=11,
        )
        StadiumGeometry.objects.create(
            stadium=self.stadium,
            geometry=_geometry([_block(0, rows=1, seats=5), _block(1, rows=1, seats=3)]),
        )
        self.payload = {'version': 1, 'palette': ['#ffffff'], 'blocks': [],
                        'grass_variant': 'A3'}
        self.client.force_login(self.user)

    def post(self, payload):
        return self.client.post(reverse('stadium_editor_save_design'),
                                json.dumps(payload), content_type='application/json')

    def test_every_approved_variant_is_valid_and_unknown_values_are_rejected(self):
        for value in GRASS_VARIANTS:
            result = normalize_design_payload({**self.payload, 'grass_variant': value})
            self.assertEqual(result['grass_variant'], value)
        for value in (None, True, 0, [], {}, 'a1', 'A5', '../private'):
            with self.assertRaises(ValueError):
                normalize_design_payload({**self.payload, 'grass_variant': value})

    def test_editor_has_controls_outside_disabled_3d_tools_and_reads_do_not_save(self):
        page = self.client.get(reverse('stadium_editor'))
        self.assertEqual(page.status_code, 200)
        text = page.content.decode()
        self.assertLess(text.index('id="grassVariant"'), text.index('id="toolsPanel"'))
        self.assertIn('id="editor-grass-assets"', text)
        for value in GRASS_VARIANTS:
            self.assertIn(f'value="{value}"', text)
        before = list(StadiumDesign.objects.values())
        for name in ('stadium_editor_design', 'stadium_editor_geometry'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(list(StadiumDesign.objects.values()), before)

    def test_only_save_persists_choice_and_legacy_tabs_preserve_it(self):
        stadium_before = Stadium.objects.filter(pk=self.stadium.pk).values().get()
        self.assertFalse(StadiumDesign.objects.filter(stadium=self.stadium).exists())
        self.assertEqual(self.post(self.payload).status_code, 200)
        saved = StadiumDesign.objects.get(stadium=self.stadium)
        self.assertEqual(saved.design['grass_variant'], 'A3')
        self.assertEqual(self.client.get(reverse('stadium_editor_design')).json()['grass_variant'], 'A3')
        legacy = {key: value for key, value in self.payload.items() if key != 'grass_variant'}
        self.assertEqual(self.post(legacy).status_code, 200)
        saved.refresh_from_db()
        self.assertEqual(saved.design['grass_variant'], 'A3')
        self.assertEqual(self.post({**self.payload, 'grass_variant': 'bestand'}).status_code, 200)
        saved.refresh_from_db()
        self.assertEqual(saved.design['grass_variant'], 'bestand')
        self.stadium.refresh_from_db()
        self.club.refresh_from_db()
        self.assertEqual(Stadium.objects.filter(pk=self.stadium.pk).values().get(), stadium_before)
        self.assertEqual(self.club.budget, 0)

    def test_failed_save_keeps_existing_choice(self):
        self.assertEqual(self.post(self.payload).status_code, 200)
        before = StadiumDesign.objects.get(stadium=self.stadium).design
        self.assertEqual(self.post({**self.payload, 'grass_variant': 'invalid'}).status_code, 400)
        self.assertEqual(StadiumDesign.objects.get(stadium=self.stadium).design, before)

    def test_asset_whitelist_for_regular_owner_without_admin_privilege(self):
        storage = Mock()
        storage.download_as_bytes.return_value = b'image-fixture'
        with patch('game.object_storage_backend.get_client', return_value=storage):
            response = self.client.get(reverse('stadium_editor_grass_asset', args=['basis']))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/webp')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            storage.download_as_bytes.assert_called_once_with(
                'studies/grass-pilot/v1/rasen_basis.webp')
            self.assertEqual(self.client.get(reverse(
                'stadium_editor_grass_asset', args=['other'])).status_code, 404)
            storage.download_as_bytes.side_effect = RuntimeError('private failure details')
            response = self.client.get(reverse('stadium_editor_grass_asset', args=['abnutzung']))
            self.assertEqual(response.status_code, 503)
            self.assertNotContains(response, 'private failure details', status_code=503)

    def test_guests_and_clubless_managers_cannot_save_or_read_assets(self):
        self.client.logout()
        self.assertEqual(self.post(self.payload).status_code, 302)
        self.assertEqual(self.client.get(reverse(
            'stadium_editor_grass_asset', args=['basis'])).status_code, 302)
        clubless = User.objects.create_user('grass-editor-clubless')
        self.client.force_login(clubless)
        with patch('game.object_storage_backend.get_client') as storage:
            self.assertEqual(self.post(self.payload).status_code, 404)
            self.assertEqual(self.client.get(reverse(
                'stadium_editor_grass_asset', args=['basis'])).status_code, 403)
            storage.assert_not_called()
