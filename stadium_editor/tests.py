import base64
import io
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from game.economy.stadium import resolve_due_expansions
from game.models import Club, League, Stadium, StadiumExpansion
from stadium_editor.capacity import distribute_capacities
from stadium_editor.image_validation import InvalidImageData, validate_and_quantize_data_url
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.seed import seed_existing_stadiums


def _geometry(blocks):
    return {
        'meta': {'name': 'Test-Arena', 'club': 'FC Test', 'maxR': 100},
        'outline': [[-100, -100], [100, -100], [100, 100], [-100, 100]],
        'blocks': blocks,
        'bg': {},
    }


def _block(block_id, *, stand='NORD', seat_type='SITZ', rows=10, seats=10):
    return {
        'id': block_id, 'stand': stand, 'type': seat_type,
        'tier': 'UNTER', 'rows': rows, 'seats': seats,
        'quad': [[0, 0], [1, 0], [1, 1], [0, 1]], 'z0': 0, 'z1': 1,
    }


class StadiumEditorTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='Editorliga', country='DE')
        self.user = User.objects.create_user('editor', password='pass')
        self.club = Club.objects.create(
            name='FC Test', short_name='FCT', founded_year=1900, budget=0,
            league=self.league, managed_by=self.user.manager_profile,
        )
        self.stadium = Stadium.objects.create(
            club=self.club, name='Test-Arena', city='Teststadt', nord_seating=11,
        )
        self.geometry = StadiumGeometry.objects.create(
            stadium=self.stadium,
            geometry=_geometry([
                _block(0, rows=1, seats=5),
                _block(1, rows=1, seats=3),
            ]),
        )

    def test_capacity_distribution_is_exact_and_remainder_uses_largest_block(self):
        distributed = distribute_capacities(self.stadium, self.geometry.geometry)
        assigned = [block['capacity'] for block in distributed['blocks']]
        self.assertEqual(sum(assigned), 11)
        self.assertEqual(assigned, [7, 4])
        self.assertEqual(distributed['capacity_total'], self.stadium.capacity_total)

    def test_manager_receives_no_simulator_markup(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('stadium_editor'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Ausbau · Simulator')
        self.assertNotContains(response, 'id="btnExpand"')
        self.assertContains(response, 'Blaupause: OpenStreetMap-Daten (ODbL)')
        editor_js = (
            Path(__file__).resolve().parent / 'static' / 'stadium_editor' / 'editor.js'
        ).read_text(encoding='utf-8')
        self.assertIn("const expandButton = document.getElementById('btnExpand');", editor_js)
        self.assertIn('if(expandButton){', editor_js)
        self.assertIn('new ResizeObserver', editor_js)
        self.assertIn('if(!nextW || !nextH || !D) return;', editor_js)
        self.assertIn('if(!D) return;', editor_js)

    def test_editor_is_embedded_in_the_global_management_shell(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('stadium_editor'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<nav class="navbar"', html=False)
        self.assertContains(response, 'class="ws-game-header"', html=False)
        self.assertContains(response, 'class="ws-calendar-strip"', html=False)
        self.assertContains(response, 'href="/management/" aria-current="page"', html=False)
        self.assertContains(response, '← ZUR STADIONVERWALTUNG')
        self.assertContains(response, 'id="btnSave"', html=False)
        self.assertNotContains(response, 'BLUEPRINT')
        self.assertNotContains(response, 'STADION-EDITOR · ZURÜCK')
        self.assertNotContains(response, '<body>\n', html=False)

    def test_stadium_management_remains_editor_entry_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('stadium_detail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stadion-Editor')
        self.assertContains(response, reverse('stadium_editor'))

    def test_staff_manager_receives_simulator_markup(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        response = self.client.get(reverse('stadium_editor'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ausbau · Simulator')
        self.assertContains(response, 'class="main has-admin"', html=False)
        self.assertContains(response, 'class="admin-tools"', html=False)

    def test_manager_editor_uses_the_full_middle_area_without_admin_column(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('stadium_editor'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="main"', html=False)
        self.assertNotContains(response, 'class="main has-admin"', html=False)
        self.assertNotContains(response, 'class="admin-tools"', html=False)

    def test_editor_layout_has_staff_rail_and_narrow_screen_fallback(self):
        template = (
            Path(__file__).resolve().parent / 'templates' / 'stadium_editor' / 'editor.html'
        ).read_text(encoding='utf-8')

        self.assertIn('grid-template-columns:282px minmax(0,1fr) 300px', template)
        self.assertIn('@media (max-width:980px)', template)
        self.assertIn('display:flex;flex-direction:column;min-height:0', template)

    def test_bundled_seed_makes_a_supported_stadium_editor_ready(self):
        self.geometry.delete()
        self.club.name = 'FC Bayern München'
        self.club.save(update_fields=['name'])
        seeded, skipped = seed_existing_stadiums(
            Stadium.objects.select_related('club').filter(pk=self.stadium.pk),
            StadiumGeometry,
        )
        self.assertEqual((seeded, skipped), (1, 0))
        self.client.force_login(self.user)
        editor = self.client.get(reverse('stadium_editor'))
        self.assertEqual(editor.status_code, 200)
        geometry = self.client.get(reverse('stadium_editor_geometry')).json()
        self.assertEqual(
            sum(block['capacity'] for block in geometry['blocks']),
            self.stadium.capacity_total,
        )

    def test_missing_blueprint_has_a_clear_non_404_page(self):
        self.geometry.delete()
        self.client.force_login(self.user)
        response = self.client.get(reverse('stadium_editor'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fehlt noch eine Blaupause')

    def test_save_design_never_persists_browser_capacity(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('stadium_editor_save_design'),
            data='{"palette":["#112233"],"blocks":[{"id":0,"rle":[[1,0]],"capacity":999999}],"capacity_total":999999}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        design = StadiumDesign.objects.get(stadium=self.stadium).design
        self.assertEqual(design, {'version': 1, 'palette': ['#112233'], 'blocks': [{'id': 0, 'rle': [[1, 0]]}]})
        self.stadium.refresh_from_db()
        self.assertEqual(self.stadium.capacity_total, 11)

    def test_oversized_data_url_is_rejected(self):
        image = Image.new('RGB', (481, 1), '#336699')
        raw = io.BytesIO()
        image.save(raw, format='PNG')
        value = 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii')
        with self.assertRaises(InvalidImageData):
            validate_and_quantize_data_url(value)

    def test_valid_image_is_stored_as_quantized_png_data_url(self):
        image = Image.new('RGB', (32, 32), '#336699')
        raw = io.BytesIO()
        image.save(raw, format='PNG')
        value = 'data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode('ascii')
        self.assertTrue(validate_and_quantize_data_url(value).startswith('data:image/png;base64,'))

    def test_completed_expansion_keeps_geometry_when_42_rows_would_be_exceeded(self):
        self.stadium.nord_seating = 42
        self.stadium.save(update_fields=['nord_seating'])
        self.geometry.geometry = _geometry([_block(0, rows=42, seats=1)])
        self.geometry.save(update_fields=['geometry'])
        StadiumExpansion.objects.create(
            stadium=self.stadium,
            stand='NORD',
            seat_type='SITZ',
            seats_added=1,
            cost=Decimal('1'),
            completes_at=timezone.now() - timedelta(seconds=1),
            applied=False,
        )
        self.assertEqual(resolve_due_expansions(self.stadium), 1)
        self.geometry.refresh_from_db()
        self.assertEqual(self.geometry.geometry['blocks'][0]['rows'], 42)
        self.assertIn('42 Reihen', self.geometry.last_warning)