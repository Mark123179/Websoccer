import base64
import io
import json
import math
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from game.economy.stadium import resolve_due_expansions
from game.models import Club, League, Stadium, StadiumExpansion
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks, project_rle, spatial_project_design
from stadium_editor.image_validation import InvalidImageData, normalize_design_payload, validate_and_quantize_data_url
from stadium_editor.live_scene import LiveSceneError, build_live_scene
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.seed import (
    BVB_NORD_STANDING_BLOCK_IDS,
    load_blueprints,
    normalise_block_types,
    seed_existing_stadiums,
)
from stadium_editor.services import refresh_geometry_after_capacity_change


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
        self.assertIn('requestAnimationFrame(() => requestAnimationFrame(resize))', editor_js)

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
        self.assertIn('height:904px;flex:0 0 904px', template)
        self.assertIn('grid-template-rows:minmax(0,1fr)', template)
        self.assertIn('.main.has-admin .stage{grid-column:2;grid-row:1}', template)
        self.assertIn('.main.has-admin .admin-tools{grid-column:3;grid-row:1}', template)
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
        self.assertEqual(
            StadiumGeometry.objects.get(stadium=self.stadium).schema_version, 2)
        self.client.force_login(self.user)
        editor = self.client.get(reverse('stadium_editor'))
        self.assertEqual(editor.status_code, 200)
        geometry = self.client.get(reverse('stadium_editor_geometry')).json()
        self.assertEqual(
            sum(block['capacity'] for block in geometry['blocks']),
            self.stadium.capacity_total,
        )

    def test_bvb_override_is_exact_52_block_prototype(self):
        blueprint = load_blueprints()['borussiadortmund']
        blocks = blueprint['blocks']
        self.assertEqual(len(blocks), 52)
        self.assertEqual(len({block['id'] for block in blocks}), 52)
        self.assertEqual(len({str(block['quad']) for block in blocks}), 52)
        self.assertEqual(
            {key: blocks[0][key] for key in ('id', 'stand', 'tier', 'rows', 'seats')},
            {'id': 0, 'stand': 'SUED', 'tier': 'OBER', 'rows': 31, 'seats': 51},
        )
        self.assertEqual(
            blocks[0]['quad'],
            [[21.69, -122.48], [49.39, -118.53], [39.02, -93.64], [17.14, -96.76]],
        )
        self.assertGreater(len(blueprint['roofs']), 20)
        self.assertEqual(blueprint['roofs'][0]['id'], 'roof-0')
        self.assertEqual(len({roof['id'] for roof in blueprint['roofs']}),
                         len(blueprint['roofs']))

    def test_bvb_nord_standing_capacity_uses_all_lower_tier_blocks(self):
        self.club.name = 'Borussia Dortmund'
        self.club.save(update_fields=['name'])
        self.stadium.nord_standing = 14_239
        self.stadium.nord_seating = 8_829
        self.stadium.save(update_fields=['nord_standing', 'nord_seating'])

        raw = normalise_block_types(
            self.stadium,
            load_blueprints()['borussiadortmund'],
        )
        original_ids = [block['id'] for block in raw['blocks']]
        distributed = distribute_capacities(self.stadium, raw)
        north = [block for block in distributed['blocks']
                 if block['stand'] == 'NORD']
        standing = [block for block in north if block['type'] == 'STEH']
        seating = [block for block in north if block['type'] == 'SITZ']

        self.assertEqual(
            {block['id'] for block in standing},
            BVB_NORD_STANDING_BLOCK_IDS,
        )
        self.assertTrue(all(block['tier'] == 'UNTER' for block in standing))
        self.assertTrue(all(block['tier'] == 'OBER' for block in seating))
        self.assertEqual(sum(block['capacity'] for block in standing), 14_239)
        self.assertEqual(sum(block['capacity'] for block in seating), 8_829)
        self.assertLessEqual(max(block['rows'] for block in standing), 56)
        self.assertEqual([block['id'] for block in distributed['blocks']], original_ids)
        self.assertEqual(distributed['capacity_total'], self.stadium.capacity_total)

    def test_bvb_nord_grid_projects_existing_design_into_matching_live_scene(self):
        self.club.name = 'Borussia Dortmund'
        self.club.save(update_fields=['name'])
        self.stadium.nord_standing = 14_239
        self.stadium.nord_seating = 8_829
        self.stadium.save(update_fields=['nord_standing', 'nord_seating'])

        new_raw = normalise_block_types(
            self.stadium,
            load_blueprints()['borussiadortmund'],
        )
        old_raw = json.loads(json.dumps(new_raw))
        for block in old_raw['blocks']:
            if block['id'] == 10:
                block['type'] = 'STEH'
            elif block['id'] in BVB_NORD_STANDING_BLOCK_IDS:
                block['type'] = 'SITZ'
        old_effective = distribute_capacities(self.stadium, old_raw)
        new_effective = distribute_capacities(self.stadium, new_raw)
        old_design = {
            'version': 2,
            'stadium': self.stadium.name,
            'blickrichtung': 'NORD',
            'palette': ['#111111', '#f4d20b'],
            'blocks': [{
                **{key: block[key] for key in
                   ('id', 'stand', 'tier', 'order', 'rows', 'seats')},
                'rle': [[block['rows'] * block['seats'], block['id'] % 2]],
            } for block in geometry_blocks(old_effective)],
        }

        projected = spatial_project_design(
            old_design,
            old_effective,
            new_effective,
            self.stadium.name,
        )
        scene = build_live_scene(self.stadium, new_raw, projected)
        editor_shapes = {
            block['id']: (block['rows'], block['seats'])
            for block in geometry_blocks(new_effective)
        }
        live_shapes = {
            block['id']: (block['rows'], block['seats'])
            for block in scene['blocks']
        }

        self.assertEqual(live_shapes, editor_shapes)
        self.assertEqual(set(live_shapes), set(range(52)))
        for block in projected['blocks']:
            self.assertEqual(
                sum(run[0] for run in block['rle']),
                block['rows'] * block['seats'],
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
        self.assertEqual(design['version'], 2)
        self.assertEqual(design['blocks'][0]['rows'] * design['blocks'][0]['seats'], 10)
        self.stadium.refresh_from_db()
        self.assertEqual(self.stadium.capacity_total, 11)

    def test_geometry_endpoint_metadata_round_trips_through_v2_save(self):
        self.client.force_login(self.user)
        geometry = self.client.get(reverse('stadium_editor_geometry')).json()
        payload = {
            'version': 2,
            'stadium': self.stadium.name,
            'blickrichtung': 'NORD',
            'palette': ['#112233'],
            'blocks': [
                {
                    **{key: block[key] for key in ('id', 'stand', 'tier', 'order', 'rows', 'seats')},
                    'rle': [[block['rows'] * block['seats'], 0]],
                }
                for block in geometry['blocks']
            ],
        }
        response = self.client.post(
            reverse('stadium_editor_save_design'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_v2_rejects_browser_owned_metadata_and_duplicate_or_unknown_ids(self):
        geometry = distribute_capacities(self.stadium, self.geometry.geometry)
        block = geometry['blocks'][0]
        payload = {
            'version': 2, 'palette': ['#112233'], 'blickrichtung': 'NORD',
            'blocks': [{
                'id': 0, 'stand': block['stand'], 'tier': 'UNTER', 'order': 0,
                'rows': block['rows'], 'seats': block['seats'],
                'rle': [[block['rows'] * block['seats'], 0]],
            }],
        }
        payload['blocks'][0]['rows'] += 1
        with self.assertRaises(InvalidImageData):
            normalize_design_payload(payload, geometry=geometry, stadium_name=self.stadium.name)
        canonical = dict(payload['blocks'][0], rows=block['rows'])
        payload['blocks'] = [dict(canonical, id=999)]
        with self.assertRaisesRegex(InvalidImageData, 'Unbekannte Block-ID'):
            normalize_design_payload(payload, geometry=geometry, stadium_name=self.stadium.name)
        payload['blocks'] = [dict(canonical, rle=[[1, 0]])]
        with self.assertRaisesRegex(InvalidImageData, 'Sitzfolge muss exakt'):
            normalize_design_payload(payload, geometry=geometry, stadium_name=self.stadium.name)
        payload['blocks'].append(dict(payload['blocks'][0]))
        with self.assertRaises(InvalidImageData):
            normalize_design_payload(payload, geometry=geometry, stadium_name=self.stadium.name)

    def test_empty_palette_is_rejected_before_default_runs_are_generated(self):
        geometry = distribute_capacities(self.stadium, self.geometry.geometry)
        with self.assertRaisesRegex(InvalidImageData, 'mindestens eine Farbe'):
            normalize_design_payload(
                {'version': 2, 'palette': [], 'blocks': []},
                geometry=geometry,
                stadium_name=self.stadium.name,
            )

    def test_large_legacy_rle_is_bounded_by_the_trusted_grid(self):
        result = project_rle([[65_535, 1]] * 10_000, (2, 2), (2, 2))
        self.assertEqual(result, [[4, 1]])

    def test_large_v1_payload_is_bounded_during_normalization(self):
        geometry = distribute_capacities(self.stadium, self.geometry.geometry)
        result = normalize_design_payload(
            {
                'palette': ['#000000', '#ffffff'],
                'blocks': [{'id': 0, 'rle': [[65_535, 1]] * 10_000}],
            },
            geometry=geometry,
            stadium_name=self.stadium.name,
        )
        block = result['blocks'][0]
        self.assertEqual(sum(run[0] for run in block['rle']), block['rows'] * block['seats'])

    def test_v1_upgrade_uses_complete_effective_grid(self):
        geometry = distribute_capacities(self.stadium, self.geometry.geometry)
        result = normalize_design_payload(
            {'palette': ['#112233'], 'blocks': [{'id': 0, 'rle': [[1, 0]]}]},
            geometry=geometry, stadium_name=self.stadium.name)
        self.assertEqual(result['version'], 2)
        for block in result['blocks']:
            self.assertEqual(sum(run[0] for run in block['rle']), block['rows'] * block['seats'])

    def test_block_order_is_left_to_right_from_the_pitch(self):
        geometry = _geometry([
            {**_block(10, stand='NORD'), 'quad': [[2, 2], [3, 2], [3, 1], [2, 1]]},
            {**_block(11, stand='NORD'), 'quad': [[-3, 2], [-2, 2], [-2, 1], [-3, 1]]},
            {**_block(12, stand='SUED'), 'quad': [[2, -2], [3, -2], [3, -1], [2, -1]]},
            {**_block(13, stand='SUED'), 'quad': [[-3, -2], [-2, -2], [-2, -1], [-3, -1]]},
        ])
        by_id = {block['id']: block for block in geometry_blocks(geometry)}
        self.assertEqual((by_id[11]['order'], by_id[10]['order']), (0, 1))
        self.assertEqual((by_id[12]['order'], by_id[13]['order']), (0, 1))

    def test_two_dimensional_resize_keeps_asymmetric_pattern_orientation(self):
        result = project_rle(
            [[1, 1], [1, 2], [1, 3], [1, 4]],
            (2, 2),
            (4, 4),
        )
        decoded = [colour for count, colour in result for _ in range(count)]
        self.assertEqual(decoded[:4], [1, 1, 2, 2])
        self.assertEqual(decoded[-4:], [3, 3, 4, 4])

    def test_spatial_projection_transfers_across_changed_block_id(self):
        old = _geometry([_block(7, rows=2, seats=2)])
        new_block = _block(99, rows=2, seats=2)
        new = _geometry([new_block])
        design = {'palette': ['#000000', '#ffffff'],
                  'blocks': [{'id': 7, 'rows': 2, 'seats': 2,
                              'rle': [[1, 1], [3, 0]]}]}
        result = spatial_project_design(design, old, new, 'Arena')
        self.assertEqual(result['blocks'][0]['id'], 99)
        self.assertEqual(result['blocks'][0]['rle'], [[1, 1], [3, 0]])

    def test_spatial_projection_ignores_oversized_historical_dimensions(self):
        old = _geometry([_block(7, rows=2, seats=2)])
        new = _geometry([_block(99, rows=2, seats=2)])
        design = {
            'palette': ['#000000', '#ffffff'],
            'blocks': [{
                'id': 7, 'rows': 1_000_000, 'seats': 1_000_000,
                'rle': [[65_535, 1]] * 10_000,
            }],
        }
        result = spatial_project_design(design, old, new, 'Arena')
        self.assertEqual(result['blocks'][0]['rle'], [[4, 1]])

    def test_visible_endpoint_filters_opposite_and_side_lower_blocks(self):
        payload = {
            'version': 2, 'blickrichtung': 'NORD', 'palette': ['#000000'],
            'blocks': [
                {'id': 1, 'stand': 'NORD', 'tier': 'OBER'},
                {'id': 2, 'stand': 'WEST', 'tier': 'UNTER'},
                {'id': 3, 'stand': 'OST', 'tier': 'OBER'},
                {'id': 4, 'stand': 'SUED', 'tier': 'UNTER'},
            ],
        }
        StadiumDesign.objects.create(
            stadium=self.stadium, design=payload, blickrichtung='NORD')
        self.client.force_login(self.user)
        result = self.client.get(reverse('stadium_editor_visible_design')).json()
        self.assertEqual([block['id'] for block in result['blocks']], [1, 2])

    def _live_scene_records(self, *, quad=None, theta=0):
        self.stadium.nord_seating = 4
        self.stadium.save(update_fields=['nord_seating'])
        raw = _geometry([{
            **_block(0, rows=2, seats=2),
            'quad': quad or [[-2, 4], [2, 4], [1, 2], [-1, 2]],
        }])
        raw['meta']['axisTheta'] = theta
        self.geometry.geometry = raw
        self.geometry.save(update_fields=['geometry'])
        design = StadiumDesign.objects.create(
            stadium=self.stadium,
            blickrichtung='NORD',
            design={
                'version': 2,
                'stadium': self.stadium.name,
                'blickrichtung': 'NORD',
                'palette': ['#000000', '#ffffff'],
                'blocks': [{
                    'id': 0, 'stand': 'NORD', 'tier': 'UNTER',
                    'order': 0, 'rows': 2, 'seats': 2,
                    'rle': [[1, 1], [3, 0]],
                }],
            },
        )
        return raw, design

    def test_live_scene_normalizes_quad_and_uses_pitch_frame(self):
        # Rotate a pitch-frame block into world coordinates; the scene must
        # rotate it back and expose the canonical front-first point order.
        pitch_quad = [[-2, 4], [2, 4], [1, 2], [-1, 2]]
        world_quad = [[-point[1], point[0]] for point in pitch_quad]
        geometry, design = self._live_scene_records(
            quad=world_quad, theta=math.pi / 2)

        result = build_live_scene(self.stadium, geometry, design.design)

        self.assertEqual(result['schema'], 'websoccer.stadium-live-scene')
        self.assertEqual(result['version'], 1)
        self.assertNotIn('axisTheta', result)
        self.assertEqual(
            result['blocks'][0]['quad'],
            [[-1.0, 2.0], [1.0, 2.0], [2.0, 4.0], [-2.0, 4.0]],
        )
        self.assertEqual(result['pitch'], {'length': 105.0, 'width': 68.0})
        self.assertEqual(result['roof'], {
            'mode': 'procedural-ring',
            'center': [0.0, 0.0],
            'depth': 1.35,
            'innerEnvelope': [59.5, 41.0],
            'excludedBlockIds': [],
        })

    def test_live_scene_resolves_editor_roof_inputs(self):
        geometry, design = self._live_scene_records()
        geometry['outline'] = [[8, -2], [12, -2], [12, 2], [8, 2]]
        geometry['meta']['track'] = True
        geometry['meta']['roof'] = {'depth': 1.45}
        geometry['blocks'][0]['noroof'] = True
        result = build_live_scene(self.stadium, geometry, design.design)
        self.assertEqual(result['roof'], {
            'mode': 'procedural-ring',
            'center': [10.0, 0.0],
            'depth': 1.45,
            'innerEnvelope': [82.0, 60.0],
            'excludedBlockIds': [0],
        })

    def test_live_scene_reverses_each_rle_row_when_quad_requires_it(self):
        geometry, design = self._live_scene_records(
            quad=[[2, 4], [-2, 4], [-1, 2], [1, 2]])
        design.design['blocks'][0]['rle'] = [
            [1, 0], [1, 1], [1, 1], [1, 0],
        ]
        result = build_live_scene(self.stadium, geometry, design.design)
        self.assertEqual(
            result['blocks'][0]['quad'],
            [[-1.0, 2.0], [1.0, 2.0], [2.0, 4.0], [-2.0, 4.0]],
        )
        self.assertEqual(
            result['blocks'][0]['rle'],
            [[1, 1], [2, 0], [1, 1]],
        )

    def test_live_scene_exports_explicit_roof_in_pitch_frame(self):
        geometry, design = self._live_scene_records(theta=math.pi / 2)
        geometry['roofs'] = [{
            'id': 'roof-main',
            'quad': [[-4, -2], [-4, 2], [-2, 1], [-2, -1]],
            'heights': [24, 24, 19, 19],
        }]

        result = build_live_scene(self.stadium, geometry, design.design)

        self.assertEqual(result['roof']['mode'], 'explicit')
        self.assertEqual(result['roof']['segments'], [{
            'id': 'roof-main',
            'quad': [[-2.0, 4.0], [2.0, 4.0], [1.0, 2.0], [-1.0, 2.0]],
            'heights': [24.0, 24.0, 19.0, 19.0],
        }])

    def test_live_scene_rejects_duplicate_roof_ids(self):
        geometry, design = self._live_scene_records()
        segment = {
            'id': 'roof-main',
            'quad': [[-2, 4], [2, 4], [1, 2], [-1, 2]],
            'heights': [24, 24, 19, 19],
        }
        geometry['roofs'] = [segment, dict(segment)]
        with self.assertRaisesRegex(LiveSceneError, 'doppelte Segment-IDs'):
            build_live_scene(self.stadium, geometry, design.design)

    def test_live_scene_endpoint_is_public_and_returns_all_blocks(self):
        self._live_scene_records()
        response = self.client.get(
            reverse('stadium_live_scene', args=[self.club.pk]))
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['club']['id'], self.club.pk)
        self.assertEqual([block['id'] for block in result['blocks']], [0])

    def test_live_mode_is_public_and_loads_canonical_scene_endpoint(self):
        self._live_scene_records()
        response = self.client.get(
            reverse('stadium_live_mode', args=[self.club.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('stadium_live_scene', args=[self.club.pk]),
        )
        self.assertContains(response, 'stadium_editor/live_mode.js')

    def test_live_mode_renderer_uses_quads_and_height_not_stand_dimensions(self):
        source = (
            Path(__file__).resolve().parent
            / 'static' / 'stadium_editor' / 'live_mode.js'
        ).read_text(encoding='utf-8')
        self.assertIn('bilinearPoint(block.quad, u0, v0)', source)
        self.assertIn('block.z0 + (block.z1 - block.z0) * v0', source)
        self.assertIn(
            'proceduralRoofRing(scene.blocks, scene.roof.center)',
            source,
        )
        self.assertIn('Math.atan2(point[1], point[0])', source)
        self.assertNotIn('fetch(`/management/stadion/editor/geometry/', source)

    def test_live_scene_endpoint_reports_missing_design_and_bad_geometry(self):
        url = reverse('stadium_live_scene', args=[self.club.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertIn('Design', response.json()['error'])

        _geometry_value, _design = self._live_scene_records(
            quad=[[0, 2], [0, 2], [1, 1], [-1, 1]])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 409)
        self.assertIn('doppelte Punkte', response.json()['error'])

    def test_live_scene_rejects_wrong_rle_length_and_browser_dimensions(self):
        geometry, design = self._live_scene_records()
        design.design['blocks'][0]['rle'] = [[3, 0]]
        with self.assertRaisesRegex(LiveSceneError, 'exakt 4'):
            build_live_scene(self.stadium, geometry, design.design)

        design.design['blocks'][0]['rows'] = 999
        with self.assertRaisesRegex(LiveSceneError, 'Ausbauzustand'):
            build_live_scene(self.stadium, geometry, design.design)

    def test_live_scene_command_matches_the_canonical_serializer(self):
        geometry, design = self._live_scene_records()
        output = Path(self.id().replace('.', '_') + '.json')
        try:
            call_command(
                'export_stadium_live_scene',
                club_id=self.club.pk,
                output=str(output),
                verbosity=0,
            )
            exported = json.loads(output.read_text(encoding='utf-8'))
        finally:
            output.unlink(missing_ok=True)
        self.assertEqual(
            exported,
            build_live_scene(self.stadium, geometry, design.design),
        )

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

    def test_capacity_change_resizes_design_even_when_raw_geometry_is_unchanged(self):
        self.stadium.nord_seating = 50
        self.stadium.save(update_fields=['nord_seating'])
        self.geometry.geometry = _geometry([_block(0, rows=10, seats=10)])
        self.geometry.save(update_fields=['geometry'])
        StadiumDesign.objects.create(
            stadium=self.stadium,
            design={
                'version': 2,
                'stadium': self.stadium.name,
                'blickrichtung': 'NORD',
                'palette': ['#000000', '#ffffff'],
                'blocks': [{
                    'id': 0, 'stand': 'NORD', 'tier': 'UNTER', 'order': 0,
                    'rows': 5, 'seats': 10, 'rle': [[1, 1], [49, 0]],
                }],
            },
        )
        self.stadium.nord_seating = 60
        self.stadium.save(update_fields=['nord_seating'])
        refresh_geometry_after_capacity_change(self.stadium)
        self.geometry.refresh_from_db()
        design = StadiumDesign.objects.get(stadium=self.stadium).design
        self.assertEqual(self.geometry.geometry['blocks'][0]['rows'], 10)
        self.assertEqual((design['blocks'][0]['rows'], design['blocks'][0]['seats']), (6, 10))
        self.assertEqual(sum(run[0] for run in design['blocks'][0]['rle']), 60)
