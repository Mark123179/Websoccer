import base64
import io
import math
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
from stadium_editor.contracts import (contract_quad, geometry_blocks, hydrate_design,
                                      legacy_seat_axis_reversed, project_rle,
                                      reverse_rle_rows, spatial_project_design)
from stadium_editor.image_validation import InvalidImageData, normalize_design_payload, validate_and_quantize_data_url
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.seed import load_blueprints, seed_existing_stadiums
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
        self.assertIn('function renderableBlock(block, index, isContract=true)', editor_js)
        self.assertIn('[contractQuad[3], contractQuad[2], contractQuad[1], contractQuad[0]]', editor_js)
        self.assertIn('axisTheta:D.axisTheta', editor_js)
        self.assertIn('quad:[b.quad[3], b.quad[2], b.quad[1], b.quad[0]]', editor_js)
        self.assertIn('renderableBlock(nb, blocks.length, false)', editor_js)

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
        self.client.force_login(self.user)
        editor = self.client.get(reverse('stadium_editor'))
        self.assertEqual(editor.status_code, 200)
        geometry = self.client.get(reverse('stadium_editor_geometry')).json()
        self.assertEqual(
            sum(block['capacity'] for block in geometry['blocks']),
            self.stadium.capacity_total,
        )

    def test_bvb_override_is_exact_52_block_prototype(self):
        blocks = load_blueprints()['borussiadortmund']['blocks']
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
            'axisTheta': geometry['axisTheta'],
            'blickrichtung': 'NORD',
            'palette': ['#112233'],
            'blocks': [
                {
                    **{key: block[key] for key in ('id', 'stand', 'tier', 'order', 'rows', 'seats', 'quad', 'z0', 'z1')},
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
            'version': 2, 'axisTheta': geometry['meta'].get('axisTheta', 0),
            'palette': ['#112233'], 'blickrichtung': 'NORD',
            'blocks': [{
                'id': 0, 'stand': block['stand'], 'tier': 'UNTER', 'order': 0,
                'rows': block['rows'], 'seats': block['seats'],
                'quad': geometry_blocks(geometry)[0]['quad'], 'z0': block['z0'], 'z1': block['z1'],
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

    def test_blueprints_and_bvb_expose_valid_spatial_contracts(self):
        blueprints = load_blueprints()
        self.assertEqual(len(blueprints), 22)
        for blueprint in blueprints.values():
            self.assertTrue(math.isfinite(blueprint['meta']['axisTheta']))
            for block in geometry_blocks(blueprint):
                self.assertEqual(len(block['quad']), 4)
                self.assertTrue(all(len(point) == 2 and all(math.isfinite(v) for v in point)
                                    for point in block['quad']))
                self.assertGreater(block['z1'], block['z0'])
        bvb = geometry_blocks(blueprints['borussiadortmund'])
        self.assertEqual(len(bvb), 52)
        self.assertEqual(len({block['id'] for block in bvb}), 52)

    def test_contract_quad_uses_pitch_view_left_to_right_and_rle_zero_is_front_left(self):
        examples = [
            [[-1, 2], [1, 2], [1, 1], [-1, 1]],
            [[1, -2], [-1, -2], [-1, -1], [1, -1]],
            [[2, 1], [2, -1], [1, -1], [1, 1]],
            [[-2, -1], [-2, 1], [-1, 1], [-1, -1]],
        ]
        for legacy in examples:
            self.assertEqual(contract_quad(legacy), [legacy[3], legacy[2], legacy[1], legacy[0]])
        geometry = _geometry([{**_block(0, rows=1, seats=2), 'quad': examples[0]}])
        hydrated = hydrate_design(
            {'palette': ['#000000', '#ffffff'], 'blickrichtung': 'NORD',
             'blocks': [{'id': 0, 'rows': 1, 'seats': 2, 'rle': [[1, 1], [1, 0]]}]},
            geometry, 'Arena')
        self.assertEqual(hydrated['blocks'][0]['quad'][0], examples[0][3])
        self.assertEqual(hydrated['blocks'][0]['rle'], [[1, 1], [1, 0]])

    def test_bundled_legacy_rle_hydration_preserves_contract_world_seat_axis_once(self):
        blueprints = load_blueprints()
        bvb = blueprints['borussiadortmund']
        self.assertTrue(legacy_seat_axis_reversed(bvb['blocks'][4]['quad']))
        # Check BVB block 4 plus every bundled raw orientation.  The old first
        # seat is raw D; after hydration it must color the same world point,
        # now found at whichever canonical front endpoint is raw D.
        seen = {True: False, False: False}
        for blueprint in blueprints.values():
            for raw in blueprint['blocks']:
                if raw['seats'] < 3:
                    continue
                reversed_axis = legacy_seat_axis_reversed(
                    raw['quad'], blueprint['meta'].get('fieldC', [0, 0]))
                seen[reversed_axis] = True
                old = {'version': 2, 'palette': ['#000000', '#111111', '#222222', '#333333'],
                       'blickrichtung': 'NORD',
                       'blocks': [{'id': raw['id'], 'rows': raw['rows'], 'seats': raw['seats'],
                                   'rle': [[1, 1], [raw['seats'] - 2, 3], [1, 2],
                                           [raw['rows'] * raw['seats'] - raw['seats'], 3]]}]}
                single = {**blueprint, 'blocks': [raw]}
                hydrated = hydrate_design(old, single, 'Arena')
                block = hydrated['blocks'][0]
                values = [color for count, color in block['rle'] for _ in range(count)]
                # In the legacy row, D is color 1 and C is color 2.
                self.assertEqual(values[0 if not reversed_axis else raw['seats'] - 1], 1)
                self.assertEqual(values[raw['seats'] - 1 if not reversed_axis else 0], 2)
                self.assertEqual(hydrate_design(hydrated, single, 'Arena')['blocks'][0]['rle'],
                                 block['rle'])
        self.assertTrue(seen[True])
        # The bundled imports are consistently wound with raw C as pitch-left;
        # explicitly cover the equally valid raw-D orientation as well.
        raw_d_front_left = [[-1, 2], [1, 2], [1, 1], [-1, 1]]
        self.assertFalse(legacy_seat_axis_reversed(raw_d_front_left))
        d_geometry = _geometry([{**_block(0, rows=1, seats=3), 'quad': raw_d_front_left}])
        d_hydrated = hydrate_design(
            {'version': 2, 'palette': ['#000000', '#111111', '#222222', '#333333'],
             'blocks': [{'id': 0, 'rows': 1, 'seats': 3, 'rle': [[1, 1], [1, 3], [1, 2]]}]},
            d_geometry, 'Arena')
        self.assertEqual(d_hydrated['blocks'][0]['rle'], [[1, 1], [1, 3], [1, 2]])

    def test_reverse_rle_rows_pads_and_preserves_row_order(self):
        self.assertEqual(reverse_rle_rows([[1, 1], [2, 2]], 2, 3),
                         [[2, 2], [1, 1], [3, 0]])

    def test_canonical_rle_is_not_reversed_again_after_geometry_resize(self):
        old_geometry = _geometry([{
            **_block(0, rows=1, seats=3),
            'quad': [[-1, 2], [1, 2], [1, 1], [-1, 1]],
        }])
        canonical = hydrate_design(
            {'version': 2, 'palette': ['#000000', '#111111', '#222222'],
             'blocks': [{'id': 0, 'rows': 1, 'seats': 3,
                         'rle': [[1, 1], [1, 0], [1, 2]]}]},
            old_geometry, 'Arena')
        resized_geometry = _geometry([{
            **_block(0, rows=2, seats=3),
            'quad': [[-1, 3], [1, 3], [1, 1], [-1, 1]],
            'z1': 2,
        }])
        resized = hydrate_design(canonical, resized_geometry, 'Arena')
        self.assertEqual(resized['blocks'][0]['rle'],
                         [[1, 1], [1, 0], [1, 2], [1, 1], [1, 0], [1, 2]])

    def test_hydrate_malformed_design_uses_safe_empty_visual_layer(self):
        hydrated = hydrate_design(None, self.geometry.geometry, self.stadium.name)
        self.assertEqual(hydrated['version'], 2)
        self.assertEqual(len(hydrated['blocks']), 2)

    def test_v2_spatial_fields_are_strictly_server_owned(self):
        geometry = distribute_capacities(self.stadium, _geometry([_block(0, rows=1, seats=11)]))
        meta = geometry_blocks(geometry)[0]
        payload = {
            'version': 2, 'axisTheta': 0, 'palette': ['#112233'], 'blickrichtung': 'NORD',
            'blocks': [{**meta, 'rle': [[meta['rows'] * meta['seats'], 0]]}],
        }
        self.assertEqual(normalize_design_payload(payload, geometry=geometry, stadium_name='Arena')['axisTheta'], 0)
        for key, bad in (('axisTheta', 1), ('quad', [[0, 0]] * 4), ('z0', meta['z0'] + 1),
                         ('z1', meta['z1'] + 1)):
            manipulated = {**payload, 'blocks': [dict(payload['blocks'][0])]}
            if key == 'axisTheta':
                manipulated[key] = bad
            else:
                manipulated['blocks'][0][key] = bad
            with self.assertRaises(InvalidImageData):
                normalize_design_payload(manipulated, geometry=geometry, stadium_name='Arena')

    def test_hydrate_old_v2_and_endpoints_enrich_spatial_metadata_in_parity(self):
        self.stadium.nord_seating = 10
        self.stadium.save(update_fields=['nord_seating'])
        self.geometry.geometry = _geometry([{
            **_block(0, rows=2, seats=5),
            'quad': [[-1, 2], [1, 2], [1, 1], [-1, 1]],
        }])
        self.geometry.save(update_fields=['geometry'])
        old = {
            'version': 2, 'stadium': 'old', 'blickrichtung': 'NORD',
            'palette': ['#000000', '#ffffff'],
            'blocks': [{'id': 0, 'stand': 'NORD', 'tier': 'UNTER', 'order': 0,
                        'rows': 2, 'seats': 5, 'rle': [[1, 1], [9, 0]]}],
        }
        effective = distribute_capacities(self.stadium, self.geometry.geometry)
        hydrated = hydrate_design(old, effective, self.stadium.name)
        self.assertEqual(hydrated['palette'], old['palette'])
        self.assertEqual(hydrated['blickrichtung'], 'NORD')
        self.assertEqual(hydrated['blocks'][0]['rle'], [[1, 1], [9, 0]])
        self.assertIn('axisTheta', hydrated)
        StadiumDesign.objects.create(stadium=self.stadium, design=old, blickrichtung='NORD')
        self.client.force_login(self.user)
        geometry = self.client.get(reverse('stadium_editor_geometry')).json()
        design = self.client.get(reverse('stadium_editor_design')).json()
        visible = self.client.get(reverse('stadium_editor_visible_design')).json()
        self.assertEqual(design['axisTheta'], geometry['axisTheta'])
        by_geometry = {block['id']: block for block in geometry['blocks']}
        for block in design['blocks'] + visible['blocks']:
            for key in ('stand', 'tier', 'order', 'rows', 'seats', 'quad', 'z0', 'z1'):
                self.assertEqual(block[key], by_geometry[block['id']][key])

    def test_capacity_spatial_scaling_uses_immutable_reference_baseline(self):
        raw = _geometry([{
            **_block(0, rows=10, seats=1),
            'quad': [[-1, 20], [1, 20], [1, 10], [-1, 10]],
            'z0': 2, 'z1': 12,
            'reference_rows': 10,
            'reference_quad': [[-1, 20], [1, 20], [1, 10], [-1, 10]],
            'reference_z0': 2, 'reference_z1': 12,
        }])
        self.stadium.nord_seating = 20
        self.stadium.save(update_fields=['nord_seating'])
        first = distribute_capacities(self.stadium, raw)['blocks'][0]
        self.assertEqual(first['quad'][2:], [[1, 10], [-1, 10]])
        self.assertEqual(first['z0'], 2)
        self.assertEqual(first['quad'][:2], [[-1, 30], [1, 30]])
        self.assertEqual(first['z1'], 22)
        # A raw row-weight change must not become the new reference baseline.
        changed_raw = _geometry([{**first, 'rows': 17}])
        self.stadium.nord_seating = 30
        self.stadium.save(update_fields=['nord_seating'])
        second = distribute_capacities(self.stadium, changed_raw)['blocks'][0]
        direct = distribute_capacities(self.stadium, raw)['blocks'][0]
        self.assertEqual(second['quad'], direct['quad'])
        self.assertEqual(second['z1'], direct['z1'])

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
        self.assertEqual(result['blocks'][0]['rle'], [[1, 0], [1, 1], [2, 0]])

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
        self.geometry.geometry = _geometry([
            {**_block(1, stand='NORD'), 'tier': 'OBER'},
            {**_block(2, stand='WEST'), 'tier': 'UNTER'},
            {**_block(3, stand='OST'), 'tier': 'OBER'},
            {**_block(4, stand='SUED'), 'tier': 'UNTER'},
        ])
        self.geometry.save(update_fields=['geometry'])
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
        for block in result['blocks']:
            self.assertEqual(len(block['quad']), 4)
            self.assertTrue(all(len(point) == 2 for point in block['quad']))
            self.assertGreater(block['z1'], block['z0'])

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