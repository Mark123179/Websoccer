import base64
import io
import json
import math
import subprocess
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from game.economy.stadium import resolve_due_expansions
from game.models import Club, EconomyParameter, League, Stadium, StadiumExpansion
from stadium_editor.capacity import distribute_capacities
from stadium_editor.contracts import geometry_blocks, project_rle, spatial_project_design
from stadium_editor.image_validation import InvalidImageData, normalize_design_payload, validate_and_quantize_data_url
from stadium_editor.live_scene import LiveSceneError, _canonical_quad, build_live_scene
from stadium_editor.models import StadiumDesign, StadiumGeometry
from stadium_editor.seed import (
    BVB_NORD_STANDING_BLOCK_IDS,
    load_blueprints,
    normalise_block_types,
    seed_existing_stadiums,
)
from stadium_editor.services import refresh_geometry_after_capacity_change
from stadium_editor.blueprints.v2 import imports as blueprint_v2
from stadium_editor.blueprints.v2.dortmund_preview import load_preview
from stadium_editor.management.commands.import_stadium_blueprint_v2 import Command as BlueprintV2Command
from game.management.commands.derive_stadium_club_colors import derive_palette


class DortmundOriginalMiniatureTests(SimpleTestCase):
    def test_expansion_model_uses_real_seat_rows_and_does_not_change_editor(self):
        script = Path(__file__).parent / 'tests_js/test_dortmund_expansion_model.mjs'
        subprocess.run(
            ['node', '--test', str(script)],
            cwd=Path(__file__).parent.parent,
            capture_output=True, text=True, check=True,
        )
        source = Path(__file__).parent / 'templates/stadium_editor/dortmund_original_miniature.html'
        template = source.read_text()
        self.assertIn('data-side="back"', template)
        self.assertIn('data-side="front"', template)
        self.assertIn('data-side="left"', template)
        self.assertIn('data-side="right"', template)
        self.assertIn('roof-plan', template)

    def test_isolated_read_only_page_and_source_manifest(self):
        import struct

        response = self.client.get(reverse('dortmund_original_miniature'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vier unabhängig veränderbare Tribünen')
        self.assertNotContains(response, 'dortmund_original/manifest.json')
        self.assertEqual(self.client.post(reverse('dortmund_original_miniature')).status_code, 405)
        root = Path(__file__).parent / 'static/stadium_editor/dortmund_original'
        manifest = json.loads((root / 'manifest.json').read_text())
        binary = (root / 'geometry.bin').read_bytes()
        size = len(binary)
        self.assertEqual(manifest['format'], 'unity-mesh-binary-v1')
        self.assertGreaterEqual(len(manifest['meshes']), 300)
        self.assertIn('center3_21.001', [m['name'] for m in manifest['meshes']])
        self.assertIn('C_back1_C1-HardcoreHome.001',
                      [m['name'] for m in manifest['meshes']])
        for mesh in manifest['meshes']:
            self.assertLessEqual(mesh['uvOffset'] + mesh['vertexCount'] * 8, size)
            for part in mesh['parts']:
                self.assertLessEqual(part['indexOffset'] + part['indexCount'] * 4, size)
                indices = struct.unpack_from('<' + 'I' * part['indexCount'],
                                             binary, part['indexOffset'])
                self.assertLess(max(indices), mesh['vertexCount'])


class DortmundPreviewGeometryTests(SimpleTestCase):
    def test_ring_renderer_height_contract(self):
        script = Path(__file__).resolve().parent / 'tests_js' / 'test_roof_ring_profile.mjs'
        subprocess.run(
            ['node', '--test', str(script)],
            cwd=Path(__file__).resolve().parent.parent,
            check=True, capture_output=True, text=True,
        )

    def test_measured_scene_has_valid_grid_and_closed_ring(self):
        from shapely.geometry import Polygon, box

        scene = load_preview()
        blocks = scene['blocks']
        self.assertEqual(len(blocks), 120)
        self.assertEqual(len({block['id'] for block in blocks}), len(blocks))
        self.assertEqual(set(block['stand'] for block in blocks),
                         {'NORD', 'OST', 'SUED', 'WEST'})
        self.assertEqual(set(block['tier'] for block in blocks), {'UNTER', 'OBER'})
        for block in blocks:
            with self.subTest(block=block['id']):
                self.assertTrue(Polygon(block['quad']).is_valid)
                self.assertGreater(Polygon(block['quad']).area, 0)
                self.assertGreater(block['z1'], block['z0'])
                self.assertGreater(block['rows'], 0)
                self.assertGreater(block['seats'], 0)
                self.assertEqual(sum(count for count, _ in block['rle']),
                                 block['rows'] * block['seats'])
        ring = scene['roof']['ring']
        outer, inner = Polygon(ring['outer']), Polygon(ring['inner'])
        self.assertTrue(outer.is_valid and inner.is_valid)
        self.assertTrue(outer.contains(inner))
        self.assertTrue(inner.contains(box(-52.5, -34, 52.5, 34)))
        self.assertGreater(ring['zOuter'], max(block['z1'] for block in blocks))
        self.assertGreater(ring['zOuter'], ring['zInner'])
        self.assertEqual(len(scene['roof']['segments']), 60)
        self.assertEqual(len({s['id'] for s in scene['roof']['segments']}), 60)
        self.assertEqual(scene['steckbrief']['pylons']['count'], 8)


class DortmundPreviewEndpointTests(TestCase):
    def test_preview_does_not_modify_stadium_or_manager_design(self):
        league = League.objects.create(name='Vorschau-Liga', country='DE')
        club = Club.objects.create(
            pk=3, name='Borussia Dortmund', short_name='BVB',
            founded_year=1909, budget=0, league=league,
        )
        stadium = Stadium.objects.create(
            club=club, name='Signal Iduna Park', city='Dortmund',
            nord_seating=42000,
        )
        geometry = StadiumGeometry.objects.create(
            stadium=stadium, geometry={'blocks': []}, steckbrief={'test': True},
        )
        design = StadiumDesign.objects.create(
            stadium=stadium, design={'custom': 'saved'},
        )
        page = self.client.get(reverse('dortmund_preview'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, reverse('dortmund_preview_scene'))
        self.assertContains(page, reverse('stadium_live_mode', args=[3]))
        response = self.client.get(reverse('dortmund_preview_scene'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['capacity'], stadium.capacity_total)
        self.assertEqual(len(response.json()['blocks']), 120)
        self.assertEqual(response['Cache-Control'], 'no-store')
        geometry.refresh_from_db()
        design.refresh_from_db()
        self.assertEqual(geometry.geometry, {'blocks': []})
        self.assertEqual(geometry.steckbrief, {'test': True})
        self.assertEqual(design.design, {'custom': 'saved'})


class DortmundEditorIntegrationTests(TestCase):
    def setUp(self):
        EconomyParameter.objects.create(saison='0', key='STADION_MAX', value=120000)
        league = League.objects.create(name='Dortmund-Editor-Liga', country='DE')
        self.user = User.objects.create_user('dortmund-manager', password='pass')
        self.club = Club.objects.create(
            pk=3, name='Borussia Dortmund', short_name='BVB',
            founded_year=1909, budget=1000000,
            league=league, managed_by=self.user.manager_profile,
        )
        self.stadium = Stadium.objects.create(
            club=self.club, name='Signal Iduna Park', city='Dortmund',
            nord_seating=1000,
        )
        StadiumGeometry.objects.create(
            stadium=self.stadium, geometry=_geometry([_block(0)]),
        )

    def test_dortmund_manager_sees_real_editor_without_admin_simulation(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('stadium_editor'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rundum planen.')
        self.assertContains(response, 'stadium_editor/dortmund_editor.css')
        self.assertContains(response, 'data-de-stand="NORD"')
        self.assertContains(response, 'id="deMenuLink"')
        self.assertContains(response, 'data-de-scene="rundum"')
        self.assertContains(response, 'dortmundScene: true')
        self.assertContains(response, 'NoDraw-Materialien sind in dieser Vorschau ausgelassen')
        self.assertNotContains(response, reverse('dortmund_original_miniature'))
        self.assertNotContains(response, 'id="btnExpand"')
        self.assertNotContains(response, 'data-de-amount="20000"')

    def test_admin_sees_preview_but_not_an_order_button(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        StadiumExpansion.objects.create(
            stadium=self.stadium, stand='NORD', seat_type='SITZ',
            seats_added=5000, cost=Decimal('100'), applied=False,
            completes_at=timezone.now() + timedelta(days=2),
        )
        response = self.client.get(reverse('stadium_editor'))
        self.assertContains(response, 'data-de-amount="20000"')
        self.assertContains(response, 'VORSCHAU HINZUFÜGEN')
        self.assertContains(response, f'maxPreviewCapacity: {response.context["preview_capacity_limit"]}')
        self.assertContains(response, 'Im Bau: +5000')
        self.assertContains(response, '1000 Plätze')
        self.stadium.refresh_from_db()
        self.assertEqual(self.stadium.capacity_total, 1000)
        self.assertEqual(self.stadium.expansions.count(), 1)
        self.assertEqual(self.club.budget, 1000000)

    def test_other_club_keeps_existing_editor_and_cannot_access_dortmund(self):
        other = User.objects.create_user('other-manager', password='pass')
        club = Club.objects.create(
            name='Other Club', short_name='OTHER', founded_year=1900,
            budget=0, league=self.club.league,
            managed_by=other.manager_profile,
        )
        Stadium.objects.create(club=club, name='Other Park', city='Other')
        StadiumGeometry.objects.create(
            stadium=club.stadium, geometry=_geometry([_block(0)]),
        )
        self.client.force_login(other)
        response = self.client.get(reverse('stadium_editor'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Rundum planen.')
        self.assertNotContains(response, 'dortmund_editor.css')
        self.assertEqual(self.client.get(reverse('stadium_editor_geometry')).json()['capacity_total'], 0)


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
        self.assertContains(
            response,
            'stadium_editor/editor.js?v=43',
        )
        editor_js = (
            Path(__file__).resolve().parent / 'static' / 'stadium_editor' / 'editor.js'
        ).read_text(encoding='utf-8')
        self.assertIn("const expandButton = document.getElementById('btnExpand');", editor_js)
        self.assertIn('if(expandButton){', editor_js)
        self.assertIn('new ResizeObserver', editor_js)
        self.assertIn('if(!nextW || !nextH || !D) return;', editor_js)
        self.assertIn('if(!D) return;', editor_js)
        self.assertIn("if(view!=='3d' || !stageThree) return;", editor_js)
        self.assertIn('if(stageThree) activateThreeStage();', editor_js)
        self.assertIn('function stadiumMaxRadius(){', editor_js)
        self.assertNotIn('138/D.meta.maxR', editor_js)
        self.assertIn('function editorBackground(){', editor_js)
        self.assertIn('D?.surroundings || {}', editor_js)
        self.assertIn('const MAX_PREVIEW_CAPACITY = Number(EDITOR.maxPreviewCapacity);', editor_js)
        self.assertIn('const MIN_EXPANSION_SEATS = 1000;', editor_js)
        self.assertIn('blocks: expansionGeometry.snapshotBlocks(blocks)', editor_js)
        self.assertIn('designBlockShape.get(b.sourceId)', editor_js)
        self.assertIn('expansionGeometry.persistentBlockEntries(blocks)', editor_js)
        self.assertIn('previewId: `preview-', editor_js)
        self.assertIn('const sourceId = block.simulated', editor_js)
        self.assertIn('function expansionEnvelope(stand){', editor_js)
        self.assertNotIn('function outerTierOf(stand', editor_js)
        self.assertIn('let ref=expansionEnvelope(stand);', editor_js)
        self.assertIn('expansionGeometry.expansionStep(', editor_js)
        self.assertIn('clearToast();', editor_js)
        self.assertIn('function standAngle(stand){', editor_js)
        self.assertIn('function previewRoofs(){', editor_js)
        self.assertIn('for(const roof of roofsFor2D()){', editor_js)
        self.assertIn('const movedQuad=roof.quad.map(point=>{', editor_js)
        self.assertIn('lineageId:lineage, previewLevel:level, supportZ:Number(rb.z1)', editor_js)
        self.assertIn('hoverBlock = null;', editor_js)
        self.assertIn('baseData = seatData.map(data => data.slice());', editor_js)
        self.assertIn('D, previewCapacity(), previewRoofs())', editor_js)
        self.assertIn('requestAnimationFrame(() => requestAnimationFrame(resize))', editor_js)
        self.assertIn('const EDITOR_ASSET_URL = new URL(document.currentScript.src);', editor_js)
        self.assertIn('url.search = EDITOR_ASSET_URL.search;', editor_js)
        self.assertIn("editorModuleUrl('./stadium_stage_adapter.js')", editor_js)
        self.assertNotIn('stadium_stage_adapter.js?v=', editor_js)
        adapter_js = (
            Path(__file__).resolve().parent
            / 'static' / 'stadium_editor' / 'stadium_stage_adapter.js'
        ).read_text(encoding='utf-8')
        self.assertIn("surroundings: mode === 'editor' ? true : null", adapter_js)
        self.assertIn('geometry?.surroundings', adapter_js)
        self.assertIn('next.blocks = Array.from(sourceById.values())', adapter_js)
        self.assertIn('block.previewId ?? block.sourceId ?? block.id', adapter_js)
        self.assertIn('quad: canonicalEditorQuad(block, geometry, target.quad)', adapter_js)
        self.assertIn('Number.isFinite(Number(previewCapacity))', adapter_js)
        self.assertIn('wallBaseZ: Number.isFinite(Number(block.supportZ))', adapter_js)
        self.assertIn("mode: 'explicit'", adapter_js)
        self.assertIn('function conformExteriorPoint(point, baselineBlocks, currentByLineage)', adapter_js)
        self.assertIn('next.facadeSegments = next.facadeSegments.map(edge => edge.map(conform))', adapter_js)
        self.assertIn('const adapterUrl = new URL(import.meta.url);', adapter_js)
        self.assertIn('stageUrl.search = adapterUrl.search;', adapter_js)
        self.assertNotIn('stadium_stage.js?v=', adapter_js)
        self.assertIn(
            "webglCanvas.addEventListener('pointerdown', startDrag)",
            adapter_js,
        )
        self.assertIn("window.addEventListener('pointermove', moveDrag)", adapter_js)
        self.assertIn("state.seatLook.yaw = Math.max(-80", adapter_js)
        self.assertIn("state.seatLook.pitch = Math.max(-20", adapter_js)
        live_mode_js = (
            Path(__file__).resolve().parent
            / 'static' / 'stadium_editor' / 'live_mode.js'
        ).read_text(encoding='utf-8')
        self.assertIn('const LIVE_MODE_ASSET_URL = new URL(import.meta.url);', live_mode_js)
        self.assertIn('url.search = LIVE_MODE_ASSET_URL.search;', live_mode_js)
        self.assertIn(
            "import(liveModeModuleUrl('./stadium_stage_adapter.js'))",
            live_mode_js,
        )
        self.assertNotIn('stadium_stage_adapter.js?v=', live_mode_js)
        shared_entry = (
            Path(__file__).resolve().parent
            / 'templates' / 'stadium_editor' / '_live_mode_script.html'
        ).read_text(encoding='utf-8')
        self.assertRegex(
            shared_entry,
            r"stadium_editor/live_mode\.js' %\}\?v=\d+",
        )
        project_root = Path(__file__).resolve().parents[1]
        direct_consumers = []
        shared_include_consumers = []
        for template_path in project_root.rglob('templates/**/*.html'):
            consumer = template_path.read_text(encoding='utf-8')
            if template_path.name != '_live_mode_script.html':
                if 'stadium_editor/live_mode.js' in consumer:
                    direct_consumers.append(str(template_path.relative_to(project_root)))
                if "{% include 'stadium_editor/_live_mode_script.html' %}" in consumer:
                    shared_include_consumers.append(
                        str(template_path.relative_to(project_root))
                    )
        self.assertEqual(direct_consumers, [])
        self.assertCountEqual(
            shared_include_consumers,
            [
                'game/templates/game/match_report.html',
                'stadium_editor/templates/stadium_editor/live_mode.html',
            ],
        )
        stage_js = (
            Path(__file__).resolve().parent
            / 'static' / 'stadium_editor' / 'stage' / 'stadium_stage.js'
        ).read_text(encoding='utf-8')
        self.assertIn(
            "import {blockSupportQuads, facadeEdgeTopHeights} "
            "from './stadium_geometry_helpers.js?v=25'",
            stage_js,
        )
        self.assertIn(
            "import {buildSeatRenderPlan, seatBasis} "
            "from './seat_rendering.js?v=2'",
            stage_js,
        )
        self.assertIn(
            "import {PITCH, buildPitchLayout} "
            "from './pitch_geometry.js?v=1'",
            stage_js,
        )
        self.assertIn('stadium_sky_day.png?v=1', stage_js)
        self.assertIn('stadium_sky_night.png?v=1', stage_js)
        self.assertIn('const hasExpansion = scene.blocks.some', stage_js)
        self.assertIn(
            'facadeEdgeTopHeights([a, b2], facadeBlocks, 2.5, roofSegs)',
            stage_js,
        )
        self.assertIn('const support = blockSupportQuads(b);', stage_js)
        self.assertIn('for (const wall of support.sideWalls)', stage_js)
        self.assertNotIn('new THREE.Vector3(0, 1, 0), Math.PI', stage_js)

    def test_stage_adapter_roof_fallback_and_expansion_undo_behavior(self):
        script = (
            Path(__file__).resolve().parent
            / 'tests_js'
            / 'test_stadium_stage_adapter.mjs'
        )
        subprocess.run(
            ['node', '--test', str(script)],
            cwd=Path(__file__).resolve().parent.parent,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_stadium_pitch_geometry_quarter_turn_contract(self):
        script = (
            Path(__file__).resolve().parent
            / 'tests_js'
            / 'test_stadium_pitch_geometry.mjs'
        )
        subprocess.run(
            ['node', '--test', str(script)],
            cwd=Path(__file__).resolve().parent.parent,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_stadium_floodlight_planning_contract(self):
        script = (
            Path(__file__).resolve().parent
            / 'tests_js'
            / 'test_stadium_lighting.mjs'
        )
        subprocess.run(
            ['node', '--test', str(script)],
            cwd=Path(__file__).resolve().parent.parent,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_stadium_expansion_geometry_contract(self):
        script = (
            Path(__file__).resolve().parent
            / 'tests_js'
            / 'test_stadium_expansion_geometry.mjs'
        )
        subprocess.run(
            ['node', '--test', str(script)],
            cwd=Path(__file__).resolve().parent.parent,
            check=True,
            capture_output=True,
            text=True,
        )

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
        self.assertContains(response, 'Vorschau bis maximal 150.000 Plätze')
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

    def test_live_scene_accepts_wide_corner_quads_without_moving_points(self):
        canonical_quads = {
            8: [[-38.177404, -51.782271], [-64.17281, -49.130745],
                [-73.683324, -56.418538], [-43.525527, -59.036896]],
            9: [[-17.292988, -51.842815], [-35.744619, -51.803559],
                [-40.752157, -59.059602], [-19.700177, -59.07093]],
            12: [[36.905169, -51.795453], [18.140159, -51.849435],
                 [20.680344, -59.0776], [42.083036, -59.055741]],
            13: [[65.569767, -48.604632], [39.39158, -51.771748],
                 [44.930547, -59.042348], [75.355655, -55.849463]],
            18: [[38.516756, 51.766764], [64.583127, 48.952869],
                 [74.192259, 56.23203], [43.922465, 59.030545]],
            19: [[17.513206, 51.844834], [36.063454, 51.796946],
                 [41.127346, 59.048057], [19.962659, 59.069249]],
            22: [[-36.572245, 51.787607], [-17.921175, 51.837366],
                 [-20.411434, 59.068259], [-41.693759, 59.042963]],
            23: [[-65.177314, 48.790322], [-39.044567, 51.762669],
                 [-44.519521, 59.034765], [-74.882634, 56.063592]],
        }
        for block_id, expected in canonical_quads.items():
            with self.subTest(block_id=block_id):
                # Reconstruct the documented source convention:
                # outer-left, outer-right, inner-right, inner-left.
                source = [expected[3], expected[2], expected[1], expected[0]]
                result, _reverse_rows = _canonical_quad(
                    source, (0, 0), 0, block_id)
                self.assertEqual(result, expected)
                self.assertCountEqual(result, source)

    def test_live_scene_rejects_a_genuinely_self_crossing_source_quad(self):
        geometry, design = self._live_scene_records(
            quad=[[-2, 4], [1, 2], [2, 4], [-1, 2]])
        with self.assertRaisesRegex(LiveSceneError, 'selbstüberschneidend'):
            build_live_scene(self.stadium, geometry, design.design)

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

    def test_elversberg_demo_uses_explicit_pitch_centered_roof_segments(self):
        scene_path = (
            Path(__file__).resolve().parents[1]
            / 'exports' / 'elversberg-live-scene-demo.json'
        )
        scene = json.loads(scene_path.read_text(encoding='utf-8'))

        self.assertEqual(scene['roof']['mode'], 'explicit')
        self.assertEqual(len(scene['roof']['segments']), 26)
        self.assertEqual(
            [segment['id'] for segment in scene['roof']['segments']],
            [f'roof-{index}' for index in range(26)],
        )
        for segment in scene['roof']['segments']:
            self.assertEqual(len(segment['quad']), 4)
            self.assertEqual(len(segment['heights']), 4)
            self.assertGreater(segment['heights'][0], segment['heights'][2])

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
        self.assertContains(response, 'data-stadium-stage')
        self.assertContains(response, 'type="importmap"')
        self.assertContains(response, 'three.module.js')

    def test_match_report_mount_uses_report_home_club_scene_url(self):
        template = (
            Path(__file__).resolve().parents[1]
            / 'game' / 'templates' / 'game' / 'match_report.html'
        ).read_text(encoding='utf-8')
        self.assertIn(
            "{% url 'stadium_live_scene' report.home_club_id %}",
            template,
        )
        self.assertNotIn('data-stadium-geometry', template)
        self.assertIn('data-stadium-live-mode', template)
        self.assertIn('data-stadium-stage', template)
        self.assertIn('type="importmap"', template)
        self.assertIn(
            "{% include 'stadium_editor/_live_mode_script.html' %}",
            template,
        )

    def test_club_colour_derivation_is_distinct_and_never_overwrites_admin_values(self):
        image = Image.new('RGBA', (80, 40), '#c8102e')
        for x in range(40, 80):
            for y in range(40):
                image.putpixel((x, y), (21, 84, 184, 255))
        with tempfile.NamedTemporaryFile(suffix='.png') as handle:
            image.save(handle, format='PNG')
            primary, secondary = derive_palette(Path(handle.name))
        self.assertNotEqual(primary, secondary)

        self.club.color_primary = '#112233'
        self.club.color_secondary = '#445566'
        self.club.save(update_fields=['color_primary', 'color_secondary'])
        with patch(
            'game.management.commands.derive_stadium_club_colors._crest_path',
            return_value=Path('/unused.png'),
        ), patch(
            'game.management.commands.derive_stadium_club_colors.derive_palette',
            return_value=('#abcdef', '#fedcba'),
        ):
            call_command(
                'derive_stadium_club_colors',
                club_ids=[self.club.pk],
                verbosity=0,
            )
        self.club.refresh_from_db()
        self.assertEqual(
            (self.club.color_primary, self.club.color_secondary),
            ('#112233', '#445566'),
        )

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
        self.assertIn('new StadiumCanvasErrorRenderer', source)
        self.assertNotIn('fetch(`/management/stadion/editor/geometry/', source)
        self.assertIn("stage.querySelector('[data-stage-floodlight]')", source)
        self.assertIn('control.addEventListener', source)
        self.assertNotIn('floodlight: !day?.checked', source)
        adapter = (
            Path(__file__).resolve().parent
            / 'static' / 'stadium_editor' / 'stadium_stage_adapter.js'
        ).read_text(encoding='utf-8')
        self.assertIn('selectSeatBlock(options.scene)', adapter)
        self.assertIn('const onlyRuntimeLighting = keys.length > 0', adapter)
        self.assertIn("['day', 'floodlight', 'exposure'].includes(key)", adapter)
        self.assertIn('stage.setLightingMode?.', adapter)
        self.assertIn('stage.setFloodlights?.', adapter)
        self.assertIn('stage.setExposure?.', adapter)
        self.assertNotIn('THREE.Scene.prototype.add', adapter)
        self.assertNotIn('alignPitchStripeMeshes', adapter)

    def test_live_scene_endpoint_reports_missing_design_and_bad_geometry(self):
        url = reverse('stadium_live_scene', args=[self.club.pk])
        self.geometry.geometry['meta'].update(axisTheta=0, fieldC=[0, 0])
        self.geometry.save(update_fields=['geometry'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['blocks'][0]['id'], 0)

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

    def test_v2_reference_generators_produce_valid_physical_scenes(self):
        for key in ('bvb', 'elversberg', 'campnou', 'olympiastadion'):
            with self.subTest(source=key):
                scene = blueprint_v2.generate(key)
                reference = json.loads(
                    (blueprint_v2.ROOT / f'{key}_v2.json').read_text(
                        encoding='utf-8')
                )
                self.assertEqual(scene, reference)
                self.assertTrue(scene['blocks'])
                for block in scene['blocks']:
                    self.assertGreater(block['z1'], block['z0'])
                    self.assertEqual(
                        sum(run[0] for run in block['rle']),
                        block['rows'] * block['seats'],
                    )
                    self.assertEqual(len(block['quad']), 4)

    def test_v2_reference_guard_rejects_geometry_drift(self):
        scene = json.loads(
            (blueprint_v2.ROOT / 'bvb_v2.json').read_text(encoding='utf-8'))
        scene['blocks'][0]['rows'] += 1
        with self.assertRaisesRegex(ValueError, 'geprüften Referenz'):
            blueprint_v2.assert_reviewed_reference('bvb', scene)

    def test_v2_scene_to_geometry_round_trips_quads_and_explicit_roof(self):
        scene = {
            'schema': 'websoccer.stadium-live-scene',
            'version': 1,
            'stadium': 'Test',
            'palette': ['#000000', '#ffffff'],
            'outline': [[-10, -10], [10, -10], [10, 10], [-10, 10]],
            'blocks': [{
                'id': 0, 'stand': 'NORD', 'tier': 'UNTER', 'order': 0,
                'rows': 2, 'seats': 2,
                'quad': [[-2, 4], [2, 4], [1, 2], [-1, 2]],
                'z0': 1, 'z1': 2, 'type': 'seating',
                'rle': [[4, 0]],
            }],
            'roof': {
                'mode': 'explicit',
                'segments': [{
                    'id': 'roof-0',
                    'quad': [[-3, 5], [3, 5], [2, 4], [-2, 4]],
                    'heights': [5, 5, 4, 4],
                }],
            },
        }
        geometry = blueprint_v2.scene_to_geometry(scene)
        self.assertEqual(geometry['roofs'], scene['roof']['segments'])
        effective = distribute_capacities(self.stadium, geometry)
        design = blueprint_v2.standard_design(scene, geometry=effective,
                                              stadium_name=self.stadium.name)
        live = build_live_scene(self.stadium, effective, design)
        self.assertEqual(live['blocks'][0]['quad'], scene['blocks'][0]['quad'])
        self.assertEqual(live['roof'], scene['roof'])

    def test_v2_physical_rows_are_not_rewritten_but_legacy_rows_are(self):
        physical = _geometry([_block(0, rows=1, seats=5)])
        physical['physical_grid'] = 'v2'
        self.stadium.nord_seating = 11
        self.stadium.save(update_fields=['nord_seating'])
        result = distribute_capacities(self.stadium, physical)
        self.assertEqual(result['blocks'][0]['rows'], 1)
        legacy = distribute_capacities(self.stadium, _geometry([
            _block(0, rows=1, seats=5),
        ]))
        self.assertEqual(legacy['blocks'][0]['rows'], 3)

    def test_v2_command_rejects_unmapped_id_and_dry_run_does_not_write(self):
        with self.assertRaisesRegex(CommandError, 'nicht in der expliziten'):
            call_command(
                'import_stadium_blueprint_v2', club_id=999999, verbosity=0,
            )
        before = StadiumGeometry.objects.get(pk=self.geometry.pk).geometry
        fixture_scene = {
            'stadium': self.stadium.name,
            'palette': ['#000000', '#ffffff'],
            'outline': [[-10, -10], [10, -10], [10, 10], [-10, 10]],
            'blocks': [{
                'id': 10, 'stand': 'NORD', 'tier': 'UNTER', 'order': 0,
                'rows': 3, 'seats': 5,
                'quad': [[-2, 4], [2, 4], [1, 2], [-1, 2]],
                'z0': 1, 'z1': 2, 'type': 'seating',
                'rle': [[15, 0]],
            }],
        }
        mapping = {
            self.club.pk: {
                'source_key': 'fixture', 'osm': 'dortmund.json',
                'steckbrief': 'Fixture',
            },
        }
        with patch.object(BlueprintV2Command, 'mapping', mapping), \
                patch.object(blueprint_v2, 'generate', return_value=fixture_scene), \
                patch.object(blueprint_v2, 'assert_reviewed_reference'), \
                patch.object(blueprint_v2, 'load_steckbrief',
                             return_value={'Fixture': {'_global': {}}}):
            call_command(
                'import_stadium_blueprint_v2',
                club_id=self.club.pk,
                source_root=str(Path(__file__).resolve().parent / 'blueprints' / 'v2'),
                dry_run=True,
                verbosity=0,
            )
        self.geometry.refresh_from_db()
        self.assertEqual(self.geometry.geometry, before)

    def test_v2_command_apply_backs_up_and_resets_design_with_injected_mapping(self):
        scene = {
            'stadium': self.stadium.name,
            'palette': ['#000000', '#ffffff'],
            'outline': [[-10, -10], [10, -10], [10, 10], [-10, 10]],
            'blocks': [{
                'id': 10, 'stand': 'NORD', 'tier': 'UNTER', 'order': 0,
                'rows': 3, 'seats': 5,
                'quad': [[-2, 4], [2, 4], [1, 2], [-1, 2]],
                'z0': 1, 'z1': 2, 'type': 'seating',
                'rle': [[15, 0]],
            }],
        }
        self.stadium.nord_seating = 11
        self.stadium.save(update_fields=['nord_seating'])
        old_design = StadiumDesign.objects.create(
            stadium=self.stadium,
            design={'version': 2, 'palette': ['#111111'], 'blocks': []},
        )
        mapping = {
            self.club.pk: {
                'source_key': 'fixture', 'osm': 'dortmund.json',
                'steckbrief': 'Fixture',
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(BlueprintV2Command, 'mapping', mapping), \
                    patch.object(blueprint_v2, 'generate', return_value=scene), \
                    patch.object(blueprint_v2, 'assert_reviewed_reference'), \
                    patch.object(blueprint_v2, 'load_steckbrief',
                                 return_value={'Fixture': {'_global': {}}}):
                call_command(
                    'import_stadium_blueprint_v2',
                    club_id=self.club.pk, source_root=str(
                        Path(__file__).resolve().parent / 'blueprints' / 'v2'),
                    apply=True, confirm=True, backup_dir=tmp, verbosity=0,
                )
            self.assertTrue(list(Path(tmp).glob('*.json')))
        self.geometry.refresh_from_db()
        old_design.refresh_from_db()
        self.assertEqual(self.geometry.source, 'OSM/BLUEPRINT V2')
        self.assertEqual(old_design.design['blocks'][0]['id'], 10)
        self.assertEqual(old_design.design['blocks'][0]['rle'], [[15, 0]])
        self.assertNotEqual(old_design.design, {'version': 2, 'palette': ['#111111'], 'blocks': []})
        self.assertNotIn('steckbrief', self.geometry.geometry)
        self.geometry.steckbrief = {'_global': {'roofType': 'edited'}}
        self.geometry.save(update_fields=['steckbrief'])
        response = self.client.get(
            reverse('stadium_live_scene', args=[self.club.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['steckbrief'], {'roofType': 'edited'})

    def test_v2_expansion_within_physical_grid_preserves_geometry_and_design(self):
        self.stadium.nord_seating = 20
        self.stadium.save(update_fields=['nord_seating'])
        geometry = _geometry([{
            **_block(4, rows=2, seats=10),
            'physical_grid': 'v2',
            'capacity': 11,
        }])
        geometry['physical_grid'] = 'v2'
        self.geometry.geometry = geometry
        self.geometry.save(update_fields=['geometry'])
        StadiumDesign.objects.create(
            stadium=self.stadium,
            design={
                'version': 2, 'palette': ['#000000'],
                'blocks': [{
                    'id': 4, 'stand': 'NORD', 'tier': 'UNTER', 'order': 0,
                    'rows': 2, 'seats': 10, 'rle': [[20, 0]],
                }],
            },
        )
        refresh_geometry_after_capacity_change(self.stadium)
        self.geometry.refresh_from_db()
        updated = self.geometry.geometry['blocks'][0]
        self.assertEqual(updated['id'], 4)
        self.assertEqual(updated['rows'], 2)
        self.assertEqual(updated['quad'], geometry['blocks'][0]['quad'])
        design = StadiumDesign.objects.get(stadium=self.stadium).design
        self.assertEqual(design['blocks'][0]['id'], 4)
        self.assertEqual(design['blocks'][0]['rows'], 2)
        self.assertEqual(design['blocks'][0]['rle'], [[20, 0]])

    def test_v2_outer_tier_starts_beyond_existing_outer_edge(self):
        self.stadium.nord_seating = 431
        self.stadium.save(update_fields=['nord_seating'])
        geometry = _geometry([{
            **_block(4, rows=42, seats=10),
            'capacity': 420,
        }])
        geometry['physical_grid'] = 'v2'
        self.geometry.geometry = geometry
        self.geometry.save(update_fields=['geometry'])

        refresh_geometry_after_capacity_change(self.stadium)

        self.geometry.refresh_from_db()
        old, new = self.geometry.geometry['blocks']
        self.assertEqual(old['id'], 4)
        self.assertGreater(new['id'], old['id'])
        old_outer = [
            sum(point[axis] for point in old['quad'][:2]) / 2
            for axis in (0, 1)
        ]
        old_inner = [
            sum(point[axis] for point in old['quad'][2:]) / 2
            for axis in (0, 1)
        ]
        new_inner = [
            sum(point[axis] for point in new['quad'][2:]) / 2
            for axis in (0, 1)
        ]
        dx, dy = (
            old_outer[0] - old_inner[0],
            old_outer[1] - old_inner[1],
        )
        length = math.hypot(dx, dy)
        outward_gap = (
            (new_inner[0] - old_outer[0]) * dx / length
            + (new_inner[1] - old_outer[1]) * dy / length
        )
        self.assertAlmostEqual(outward_gap, 2.0)
        self.assertEqual(
            sum(block['capacity'] for block in self.geometry.geometry['blocks']),
            431,
        )
