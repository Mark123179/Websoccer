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
        self.assertIn('match-preview.js?v=preview-13', html)

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
        self.assertIn('Kein aktueller Spielbericht', html)
        self.assertIn('Kein 3D-Modell verfügbar', html)

    def test_reference_layout_has_model_beside_stats_and_referee_portrait(self):
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
        self.assertIn('Form &amp; Stats', html)
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
        self.assertIn('height: 380px;', css)
        self.assertNotIn('.mp-pitch::before', css)

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