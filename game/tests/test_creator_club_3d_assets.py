import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from game.creator_club_assets import (
    MAX_UPLOAD_BYTES, ThreeDKitFinder, creator_asset_context, texture_file,
)
from game.models import Club, League, Stadium, StadiumExpansion
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.services import refresh_geometry_after_capacity_change
from stadium_editor.tests import _block, _geometry


def png_file(colour='red'):
    stream = io.BytesIO()
    Image.new('RGBA', (16, 24), colour).save(stream, format='PNG')
    return SimpleUploadedFile('texture.png', stream.getvalue(), content_type='image/png')


class CreatorClub3DAssetsTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user('asset-creator', is_staff=True)
        self.manager = get_user_model().objects.create_user('asset-manager')
        self.client.force_login(self.staff)
        league = League.objects.create(name='Assetliga', country='Deutschland')
        self.club = Club.objects.create(
            name='Assetclub', short_name='Asset', league=league,
            founded_year=1900, budget=0, fm_inside_id=907, cmtracker_id=22,
        )
        self.stadium = Stadium.objects.create(club=self.club, name='Assetstadion')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = patch('game.creator_club_assets.assets_root', return_value=self.tmp.name)
        root.start()
        self.addCleanup(root.stop)

    def upload_url(self, kind='home'):
        return reverse('creator_upload_3d_kit', args=[self.club.pk, kind])

    def source_url(self):
        return reverse('creator_save_source_ids', args=[self.club.pk])

    def identities(self, **overrides):
        return {
            'fm_inside_id': '907', 'transfermarkt_id': '',
            'api_football_id': '', 'cmtracker_id': '66', **overrides,
        }

    def records(self):
        self.stadium.nord_seating = 4
        self.stadium.save(update_fields=['nord_seating'])
        raw = _geometry([{
            **_block(0, rows=2, seats=2),
            'quad': [[-2, 4], [2, 4], [1, 2], [-1, 2]],
        }])
        raw['meta']['axisTheta'] = 0
        geometry = StadiumGeometry.objects.create(stadium=self.stadium, geometry=raw)
        design = StadiumDesign.objects.create(stadium=self.stadium, design={
            'version': 2, 'stadium': self.stadium.name, 'blickrichtung': 'NORD',
            'palette': ['#000000', '#ffffff'],
            'blocks': [{'id': 0, 'stand': 'NORD', 'tier': 'UNTER', 'order': 0,
                        'rows': 2, 'seats': 2, 'rle': [[4, 0]]}],
        })
        return geometry, design

    def test_all_three_uploads_use_fmi_not_database_id(self):
        for kind in ('home', 'away', 'third'):
            response = self.client.post(self.upload_url(kind), {'image': png_file()})
            self.assertRedirects(response, reverse('creator_club_edit', args=[self.club.pk]) + '?tab=bilder')
            file = texture_file(907, kind)
            self.assertTrue(file.is_file())
            with Image.open(file) as image:
                self.assertEqual(image.size, (16, 24))
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))
            self.assertEqual(file.name, f'907_{kind}.png')
        self.assertEqual(len(list(Path(self.tmp.name).glob('3dkits/*'))), 3)

    def test_preview_urls_are_exact_and_replacements_bust_cache(self):
        self.client.post(self.upload_url(), {'image': png_file()})
        first = creator_asset_context(self.club, self.stadium)['kits_3d'][0]
        self.assertEqual(first['path'], '/static/game/images/3dkits/907_home.png')
        self.assertTrue(first['uploaded'])
        self.client.post(self.upload_url(), {'image': png_file('blue')})
        second = creator_asset_context(self.club, self.stadium)['kits_3d'][0]
        self.assertNotEqual(first['url'], second['url'])
        with Image.open(texture_file(907, 'home')) as image:
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 255, 255))

    def test_invalid_upload_never_replaces_existing(self):
        self.client.post(self.upload_url(), {'image': png_file()})
        before = texture_file(907, 'home').read_bytes()
        for data in (b'not a png', before[:-12]):
            response = self.client.post(self.upload_url(), {
                'image': SimpleUploadedFile('fake.png', data, content_type='image/png'),
            })
            self.assertTrue(any(message.level_tag == 'error' for message in get_messages(response.wsgi_request)))
            self.assertEqual(texture_file(907, 'home').read_bytes(), before)

    def test_jpeg_disguised_as_png_is_rejected(self):
        stream = io.BytesIO()
        Image.new('RGB', (16, 24)).save(stream, format='JPEG')
        self.client.post(self.upload_url(), {
            'image': SimpleUploadedFile('texture.png', stream.getvalue(), content_type='image/png'),
        })
        self.assertFalse(texture_file(907, 'home').exists())

    def test_size_and_pixel_limits_prevent_writes(self):
        self.client.post(self.upload_url(), {
            'image': SimpleUploadedFile('big.png', b'x' * (MAX_UPLOAD_BYTES + 1)),
        })
        oversized = png_file()
        with patch('game.creator_club_assets.MAX_TEXTURE_PIXELS', 1):
            self.client.post(self.upload_url(), {'image': oversized})
        self.assertFalse(Path(self.tmp.name, '3dkits').exists())

    def test_missing_file_invalid_slot_and_no_fmi_do_not_write(self):
        self.client.post(self.upload_url(), {})
        self.client.post(self.upload_url('invalid'), {'image': png_file()})
        self.club.fm_inside_id = None
        self.club.save(update_fields=['fm_inside_id'])
        self.client.post(self.upload_url(), {'image': png_file()})
        self.assertFalse(Path(self.tmp.name, '3dkits').exists())
        ctx = creator_asset_context(self.club, self.stadium)
        self.assertTrue(all(not kit['path'] and not kit['uploaded'] for kit in ctx['kits_3d']))

    def test_io_failure_does_not_damage_existing(self):
        self.client.post(self.upload_url(), {'image': png_file()})
        before = texture_file(907, 'home').read_bytes()
        with patch('game.creator_club_assets.os.replace', side_effect=OSError):
            response = self.client.post(self.upload_url(), {'image': png_file('blue')})
        self.assertEqual(texture_file(907, 'home').read_bytes(), before)
        self.assertEqual(len(list(Path(self.tmp.name, '3dkits').iterdir())), 1)
        self.assertTrue(any(message.level_tag == 'error' for message in get_messages(response.wsgi_request)))

    def test_upload_is_staff_only_post_only_and_csrf_protected(self):
        for user in (None, self.manager):
            self.client.logout()
            if user:
                self.client.force_login(user)
            self.assertEqual(self.client.post(self.upload_url(), {'image': png_file()}).status_code, 302)
        self.assertFalse(texture_file(907, 'home').exists())
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.upload_url()).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(self.upload_url(), {'image': png_file()}).status_code, 403)

    def test_finder_serves_upload_at_requested_url_without_collecting_it(self):
        self.client.post(self.upload_url(), {'image': png_file()})
        expected = str(texture_file(907, 'home'))
        finder = ThreeDKitFinder()
        self.assertEqual(finder.find('game/images/3dkits/907_home.png'), expected)
        self.assertEqual(finders.find('game/images/3dkits/907_home.png'), expected)
        self.assertEqual(finder.find('game/images/3dkits/907_home.png', find_all=True), [expected])
        self.assertEqual(list(finder.list([])), [])
        for path in ('game/images/3dkits/../secret.png', 'game/images/3dkits/907_unknown.png'):
            self.assertEqual(finder.find(path), [])

    def test_creator_renders_real_textures_both_model_states_and_cmt(self):
        self.records()
        self.client.post(self.upload_url('third'), {'image': png_file()})
        response = self.client.get(reverse('creator_club_edit', args=[self.club.pk]))
        self.assertContains(response, '/static/game/images/3dkits/907_third.png?v=')
        self.assertContains(response, 'name="cmtracker_id"')
        self.assertContains(response, 'value="22"')
        for mode in ('original', 'current'):
            self.assertContains(response, reverse('creator_stadium_model', args=[self.club.pk, mode]))
        self.assertContains(response, self.upload_url('home'))

    def test_cmtracker_save_clear_and_legacy_partial_post(self):
        self.client.post(self.source_url(), self.identities())
        self.club.refresh_from_db()
        self.assertEqual(self.club.cmtracker_id, 66)
        self.client.post(self.source_url(), {
            'fm_inside_id': '907', 'transfermarkt_id': '', 'api_football_id': '',
        })
        self.club.refresh_from_db()
        self.assertEqual(self.club.cmtracker_id, 66)
        self.client.post(self.source_url(), self.identities(cmtracker_id=''))
        self.club.refresh_from_db()
        self.assertIsNone(self.club.cmtracker_id)

    def test_invalid_identity_is_atomic_and_does_not_clear_other_ids(self):
        for invalid in ('-1', '0', 'wrong', '1_2', '+2', str(2**63)):
            self.client.post(self.source_url(), self.identities(
                fm_inside_id='999', cmtracker_id=invalid))
            self.club.refresh_from_db()
            self.assertEqual(self.club.cmtracker_id, 22)
            self.assertEqual(self.club.fm_inside_id, 907)
        self.client.post(self.source_url(), self.identities(api_football_id=str(2**31)))
        self.club.refresh_from_db()
        self.assertEqual(self.club.cmtracker_id, 22)

    def test_duplicate_fmi_is_reported_and_no_partial_identity_save(self):
        Club.objects.create(name='Other assetclub', short_name='Other',
                            founded_year=1900, budget=0, league=self.club.league, fm_inside_id=999)
        self.client.post(self.source_url(), self.identities(fm_inside_id='999'))
        self.club.refresh_from_db()
        self.assertEqual(self.club.fm_inside_id, 907)
        self.assertEqual(self.club.cmtracker_id, 22)

    def test_source_ids_are_staff_only_and_csrf_protected(self):
        self.client.force_login(self.manager)
        self.client.post(self.source_url(), self.identities())
        self.club.refresh_from_db()
        self.assertEqual(self.club.cmtracker_id, 22)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(self.source_url(), self.identities()).status_code, 403)

    def test_model_availability_never_falls_back_to_another_club(self):
        self.club.fm_inside_id = 915
        self.club.save(update_fields=['fm_inside_id'])
        ctx = creator_asset_context(self.club, self.stadium)
        self.assertTrue(all(not model['available'] for model in ctx['stadium_models']))
        self.assertEqual(self.client.get(
            reverse('creator_stadium_model', args=[self.club.pk, 'original'])).status_code, 404)
        self.assertEqual(self.client.get(
            reverse('creator_stadium_model', args=[self.club.pk, 'current'])).status_code, 404)
        self.records()
        ctx = creator_asset_context(self.club, self.stadium)
        self.assertFalse(ctx['stadium_models'][0]['available'])
        self.assertTrue(ctx['stadium_models'][1]['available'])

    def test_viewer_is_staff_only_read_only_and_uses_real_live_scene(self):
        geometry, design = self.records()
        before = (geometry.geometry, design.design, self.stadium.nord_seating)
        original = self.client.get(reverse('creator_stadium_model', args=[self.club.pk, 'original']))
        self.assertContains(original, 'data-mode="original"')
        current = self.client.get(reverse('creator_stadium_model', args=[self.club.pk, 'current']))
        self.assertContains(current, reverse('stadium_live_scene', args=[self.club.pk]))
        self.assertContains(current, 'data-view-kind="current"')
        geometry.refresh_from_db()
        design.refresh_from_db()
        self.stadium.refresh_from_db()
        self.assertEqual(before, (geometry.geometry, design.design, self.stadium.nord_seating))
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse(
            'creator_stadium_model', args=[self.club.pk, 'current'])).status_code, 302)

    def test_current_scene_tracks_applied_expansion_but_never_applies_pending(self):
        self.records()
        url = reverse('stadium_live_scene', args=[self.club.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        before = response.json()
        pending = StadiumExpansion.objects.create(
            stadium=self.stadium, stand='NORD', seat_type='SITZ', seats_added=4, cost=0, applied=False)
        self.client.get(reverse('creator_stadium_model', args=[self.club.pk, 'current']))
        pending.refresh_from_db()
        self.stadium.refresh_from_db()
        self.assertFalse(pending.applied)
        self.assertEqual(self.stadium.nord_seating, 4)
        self.assertEqual(self.client.get(url).json(), before)
        self.stadium.nord_seating = 8
        self.stadium.save(update_fields=['nord_seating'])
        pending.applied = True
        pending.save(update_fields=['applied'])
        refresh_geometry_after_capacity_change(self.stadium)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        after = response.json()
        self.assertNotEqual(before['blocks'], after['blocks'])

    def test_geometry_warning_is_visible_and_missing_stadium_is_supported(self):
        geometry, _design = self.records()
        geometry.last_warning = 'Ausbau wird nur im Kapazitätsmodell geführt.'
        geometry.save(update_fields=['last_warning'])
        response = self.client.get(reverse('creator_club_edit', args=[self.club.pk]))
        self.assertContains(response, geometry.last_warning)
        self.stadium.delete()
        response = self.client.get(reverse('creator_club_edit', args=[self.club.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['stadium_models'][1]['available'])
