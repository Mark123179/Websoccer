"""The empty preview uses the real competition without mutating match data."""
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_template_has_three_empty_panels_and_decorative_layers(self):
        html = render_to_string('game/club_match_preview.html', {
            'competition_name': 'Bundesliga', 'competition_logo': '',
        })
        self.assertEqual(html.count('class="match-preview-panel'), 4)  # container + 3 panels
        self.assertIn('<h1>Bundesliga</h1>', html)
        self.assertIn('match-preview-content', html)
        self.assertIn('locker-room.png', html)
        self.assertNotIn('match-preview-scene__foreground', html)
        self.assertNotIn('foreground.png', html)
        self.assertNotIn('Vorbericht für das Spiel', html)