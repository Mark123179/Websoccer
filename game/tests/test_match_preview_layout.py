"""The empty preview uses the real competition without mutating match data."""
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from PIL import Image, ImageChops
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.template.loader import render_to_string

from game.views import club_match_preview


class MatchPreviewLayoutTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/clubs/1/matches/next/')
        self.club = SimpleNamespace(id=1, league=SimpleNamespace(name='Bundesliga'))

    def preview_context(self, fixture=None, explicit=False):
        with (
            patch('game.views.get_object_or_404',
                  side_effect=[self.club, fixture] if explicit else [self.club]) as lookup,
            patch('game.fixture_display.get_next_fixture', return_value=fixture) as next_fixture,
            patch('game.competition_assets.competition_logo_static_path', return_value='/league.png'),
            patch('game.match_preview.build_match_preview_context', return_value={}),
            patch('game.views.render', return_value=HttpResponse()) as render,
        ):
            club_match_preview(self.request, 1, fixture_id=3 if explicit else None)
            self.assertEqual(render.call_args.args[1], 'game/club_match_preview.html')
            if explicit:
                next_fixture.assert_not_called()
                # Preserve both fixture ID and club-membership checks.
                self.assertIn(('pk', 3), lookup.call_args.args[1].children)
            return render.call_args.args[2]

    def test_next_fixture_uses_its_competition(self):
        fixture = SimpleNamespace(league=SimpleNamespace(name='Pokal'))
        self.assertEqual(self.preview_context(fixture)['competition_name'], 'Pokal')

    def test_explicit_fixture_uses_its_competition(self):
        fixture = SimpleNamespace(league=SimpleNamespace(name='Pokal'))
        self.assertEqual(self.preview_context(fixture, explicit=True)['competition_name'], 'Pokal')

    def test_without_fixture_uses_club_league(self):
        self.assertEqual(self.preview_context()['competition_name'], 'Bundesliga')

    def test_without_league_does_not_invent_a_competition(self):
        self.club.league = None
        context = self.preview_context()
        self.assertEqual(context['competition_name'], 'Wettbewerb')
        self.assertEqual(context['competition_logo'], '')

    def test_template_has_three_briefing_panels_and_empty_state(self):
        html = render_to_string('game/club_match_preview.html', {
            'competition_name': 'Bundesliga', 'competition_logo': '', 'preview': {},
        })
        self.assertEqual(html.count('class="match-preview-panel'), 4)  # container + 3 panels
        self.assertIn('>Bundesliga</h1>', html)
        self.assertIn('match-preview-content', html)
        self.assertNotIn('match-preview-scene__foreground', html)
        self.assertNotIn('foreground.png', html)
        self.assertNotIn('Vorbericht für das Spiel', html)
        self.assertIn('Der Spielplan ist derzeit frei.', html)
        self.assertIn('match-preview.js?v=preview-18', html)

    def test_partial_fixture_handles_missing_reports_and_zero_temperature(self):
        html = render_to_string('game/club_match_preview.html', {
            'competition_name': 'Bundesliga', 'competition_logo': '',
            'preview': {
                'has_fixture': True, 'home': {'name': 'Heim'},
                'away': {'name': 'Gast'}, 'opponent': {'name': 'Gast'},
                'weather': {'label': 'Schnee', 'temperature': 0},
            },
        })
        self.assertIn('Schnee · 0 °C', html)
        self.assertIn('Keine verletzungsbedingten Ausfälle', html)
        self.assertIn('Keine Sperren', html)
        self.assertIn('Kein 3D-Modell verfügbar', html)

    def test_approved_arrangement_has_model_beside_photo_and_inline_weather(self):
        html = render_to_string('game/club_match_preview.html', {
            'competition_name': 'Bundesliga', 'competition_logo': '',
            'preview': {
                'has_fixture': True, 'home': {'name': 'Heim'},
                'away': {'name': 'Gast'}, 'opponent': {'name': 'Gast'},
                'trainer': {'name': 'Demo-Trainer', 'is_demo': True},
                'referee': {
                    'name': 'Demo-Referee', 'is_demo': True,
                    'portrait_url': '/referee-face.png', 'nationality': 'Schweiz',
                    'level_label': 'International',
                },
                'weather': {'label': 'Sonnig', 'temperature': 18, 'is_demo': True},
                'stadium': {
                    'name': 'Heimstadion', 'photo_url': '/venue.jpg',
                    'model_available': True, 'model_is_demo': True,
                    'model_name': 'Signal Iduna Park · Dortmund',
                    'model_scene_url': '/dortmund-scene.js',
                },
            },
        })
        self.assertGreaterEqual(html.count('Testdaten'), 3)
        self.assertIn('Testmodell', html)
        self.assertIn('mp-report-layout', html)
        self.assertNotIn('Form &amp; Stats', html)
        self.assertNotIn('mp-report-stats', html)
        self.assertIn('mp-weather-animation', html)
        self.assertIn('mp-suspensions-title', html)
        self.assertIn('mp-referee-profile', html)
        self.assertIn('/referee-face.png', html)
        self.assertIn('Schweiz', html)
        self.assertIn('International', html)
        self.assertLess(html.index('mp-form-stats'), html.index('mp-model-card'))
        self.assertNotIn('SPIEL STARTEN', html.upper())
        self.assertNotIn('Trainerzitat', html)
        self.assertIn('data-club-stadium-stage', html)
        self.assertIn('club-stadium.js', html)
        self.assertIn('type="importmap"', html)
        self.assertIn('stage/vendor/three.module.js', html)
        self.assertNotIn('data-stadium-tab', html)
        self.assertNotIn('data-stadium-view', html)

    def test_pitch_uses_tactics_image_and_has_more_length(self):
        from pathlib import Path
        css = Path('game/static/game/css/match-preview.css').read_text()
        self.assertIn('../images/backgrounds/spielfeld.png', css)
        self.assertIn('height: 460px;', css)
        self.assertNotIn('.mp-pitch::before', css)

    def test_personal_layout_tools_are_wired_without_game_mutation_controls(self):
        html = render_to_string('game/club_match_preview.html', {
            'competition_name': 'Bundesliga', 'preview': {},
            'request': SimpleNamespace(user=SimpleNamespace(pk=42)),
        })
        self.assertIn('data-layout-owner="42"', html)
        self.assertIn('match-preview-layout.css?v=layout-5', html)
        self.assertIn('match-preview-layout.js?v=layout-5', html)
        self.assertIn('data-layout-revision="3"', html)
        self.assertNotIn('Die letzten fünf', html)
        self.assertNotIn('Form der letzten fünf Spiele', html)
        for name in ('open', 'tools', 'select', 'parent', 'x', 'y', 'width', 'height',
                     'font', 'visible', 'front', 'back', 'save', 'cancel', 'reset', 'status'):
            self.assertIn(f'id="mp-layout-{name}"', html)
        self.assertIn('in diesem Browser gespeichert', html)
        self.assertIn('keine Änderung der Aufstellung', html)

    def test_layout_editor_has_independent_handles_and_only_local_storage(self):
        js = Path('game/static/game/js/match-preview-layout.js').read_text()
        css = Path('game/static/game/css/match-preview-layout.css').read_text()
        self.assertIn('localStorage.setItem', js)
        self.assertIn('root.dataset.layoutOwner', js)
        self.assertIn('setPointerCapture', js)
        self.assertIn('["n", "ne", "e", "se", "s", "sw", "w", "nw"]', js)
        self.assertNotIn('fetch(', js)
        self.assertNotIn('XMLHttpRequest', js)
        self.assertIn('mp-layout-editing', css)

    def test_injuries_and_suspensions_render_in_separate_ordered_blocks(self):
        html = render_to_string('game/club_match_preview.html', {
            'competition_name': 'Bundesliga', 'preview': {
                'has_fixture': True,
                'home': {'name': 'Heim'}, 'away': {'name': 'Gast'}, 'opponent': {'name': 'Gast'},
                'injuries': [{'player': {'name': 'Verletzter Testspieler'},
                             'reason': 'Muskel', 'duration': '4 Tage'}],
                'suspensions': [{'player': {'name': 'Gesperrter Testspieler'},
                                'reason': 'Rot', 'duration': '2 Spiele'}],
            },
        })
        self.assertLess(html.index('mp-injuries-title'), html.index('Verletzter Testspieler'))
        self.assertLess(html.index('Verletzter Testspieler'), html.index('mp-suspensions-title'))
        self.assertLess(html.index('mp-suspensions-title'), html.index('Gesperrter Testspieler'))
        self.assertEqual(html.count('Verletzter Testspieler'), 1)
        self.assertEqual(html.count('Gesperrter Testspieler'), 1)

    def test_preview_reuses_all_six_existing_weather_animations_and_zero_degrees(self):
        for kind, marker in (
            ('normal', 'wxs-sun'), ('regen', 'wxs-rf'), ('wind', 'wxs-streak'),
            ('nebel', 'wxs-fogband'), ('hitze', 'wxs-heatsun'), ('schnee', 'wxs-sf'),
        ):
            with self.subTest(kind=kind):
                wx = {'type': kind, 'label': 'Prognose', 'temperature': 0}
                html = render_to_string('game/club_match_preview.html', {
                    'competition_name': 'Bundesliga',
                    'preview': {'has_fixture': True, 'weather': wx,
                                'home': {'name': 'Heim'}, 'away': {'name': 'Gast'},
                                'opponent': {'name': 'Gast'}},
                })
                popup = render_to_string('game/partials/weather_icon.html', {'wx': wx})
                for rendered in (html, popup):
                    self.assertIn(f'wx-scene--{kind}', rendered)
                    self.assertIn(marker, rendered)
                self.assertIn('0 °C', html)

    def test_pitch_coordinates_are_unlocalized_and_snapshot_text_is_escaped(self):
        html = render_to_string('game/club_match_preview.html', {
            'competition_name': 'Bundesliga', 'competition_logo': '',
            'preview': {'lineup': [{
                'id': 1, 'name': '<script>bad</script>', 'short_name': '<script>',
                'x': 12.5, 'y': 84.5, 'number': None, 'url': '', 'portrait_url': '',
            }]},
        })
        self.assertIn('left:12.5%;top:84.5%', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>bad', html)
        self.assertNotIn('>None<', html)

    def test_sam_mask_preserves_approved_segmentation_and_frame(self):
        assets = Path(settings.BASE_DIR) / 'game/static/game/images/match-preview'
        with (
            Image.open(assets / 'locker-room.png') as photo,
            Image.open(assets / 'object-mask-sam.png') as objects,
            Image.open(assets / 'panel-mask-sam.png') as panels,
        ):
            self.assertEqual(photo.size, objects.size)
            self.assertEqual(photo.size, panels.size)
            self.assertIsNone(ImageChops.difference(
                panels.getchannel('A'), ImageChops.invert(objects.convert('L')),
            ).getbbox())
            for x, y in [(110, 510), (840, 510), (895, 520)]:
                point = (round(x * photo.width / 1024), round(y * photo.height / 572))
                self.assertEqual(panels.getchannel('A').getpixel(point), 0)
            self.assertEqual(panels.getchannel('A').getpixel((photo.width // 2, 100)), 255)