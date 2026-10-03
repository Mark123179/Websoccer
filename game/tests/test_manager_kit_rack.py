import hashlib
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from game.manager_kit_reference import reference_kits


class ManagerKitSourceTests(SimpleTestCase):
    def test_javascript_only_changes_the_approved_hook_height(self):
        path = Path(__file__).resolve().parents[1] / 'static/game/js/manager-trikots.js'
        modified = path.read_bytes()
        self.assertEqual(modified.count(b'const hookInset = KIT_H * -0.002 + 6;'), 1)
        original = modified.replace(
            b'const hookInset = KIT_H * -0.002 + 6;',
            b'const hookInset = KIT_H * -0.002;',
        )
        self.assertEqual(
            hashlib.sha256(original).hexdigest(),
            'e4a05311ed0a93760cd32843dca30ec83cfbf588974bc83a9a572b72b43ce8e9',
        )

    def test_css_only_changes_the_permitted_static_image_path(self):
        path = Path(__file__).resolve().parents[1] / 'static/game/css/manager-trikots.css'
        original = path.read_bytes().replace(
            b'/static/game/images/kits/rack-room.png', b'assets/kits/rack-room.png',
        )
        self.assertEqual(
            hashlib.sha256(original).hexdigest(),
            '3055ff7fbf88cc1a7cf6dffb6cde0b8ae85ffc1bf2f83bbe59125c40f154565d',
        )

    def test_reference_kits_keep_the_original_order_and_dimensions(self):
        kits = reference_kits()
        self.assertEqual([(k['W'], k['H']) for k in kits], [(483, 688), (591, 822), (520, 734)])
        root = Path(__file__).resolve().parents[1] / 'static/game'
        for code, kit in zip(['1026', '1050', '1052'], kits):
            self.assertTrue(kit['glb'].endswith(f'{code}_away.glb'))
            self.assertEqual((root / f'models/kits/{code}_away.glb').read_bytes()[:4], b'glTF')
            self.assertTrue((root / f'images/kits/hanger-{code}.png').is_file())


class ManagerKitPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('kit-reference-manager')
        self.client.force_login(self.user)

    def test_trikots_tab_renders_reference_models_and_preserves_tab_order(self):
        response = self.client.get(reverse('manager_profile') + '?tab=trikots')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['kits_json'], reference_kits())
        self.assertContains(response, 'id="kit-stage"')
        self.assertContains(response, 'id="kit-data" type="application/json"')
        self.assertContains(response, 'three@0.184.0')
        self.assertContains(response, '"integrity"')
        self.assertNotContains(response, 'id="mpAvatarBadgeImg"')
        content = response.content.decode()
        positions = [content.index(f'href="?tab={tab}"') for tab in (
            'profil', 'mannschaftsfotos', 'trikots', 'einstellungen',
        )]
        self.assertEqual(positions, sorted(positions))

    def test_other_profile_tabs_do_not_load_the_renderer_or_import_map(self):
        response = self.client.get(reverse('manager_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="kit-stage"')
        self.assertNotContains(response, 'three@0.184.0')
        self.assertNotContains(response, 'id="mpAvatarBadgeImg"')
        self.assertContains(response, 'id="mpAvatarHeaderImg"')