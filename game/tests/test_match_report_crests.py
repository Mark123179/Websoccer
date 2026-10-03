"""Report image URLs must not be resolved relative to either report route."""
import json
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.templatetags.static import static
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from game.asset_urls import resolve_club_crest_url
from game.models import Club, League, SeasonFixture, SimulatedMatch
from game.views import _ensure_crests_in_report


class ImageSources(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.sources = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.sources.append(dict(attrs).get('src', ''))


@override_settings(ASSETS_BASE_URL='/assets/')
class CrestResolutionTests(SimpleTestCase):
    def test_supported_paths(self):
        for path, expected in (
            ('game/images/crests/915.png', static('game/images/crests/915.png')),
            ('/static/game/images/crests/915.png', '/static/game/images/crests/915.png'),
            ('clubs/logos/915_club.png', '/assets/clubs/logos/915_club.png'),
            ('/static/assets/clubs/logos/915_club.png', '/assets/clubs/logos/915_club.png'),
            ('/assets/clubs/logos/915_club.png', '/assets/clubs/logos/915_club.png'),
            ('https://cdn.example.org/915.png', 'https://cdn.example.org/915.png'),
            ('//cdn.example.org/915.png', '//cdn.example.org/915.png'),
            ('', ''),
            (None, ''),
        ):
            with self.subTest(path=path):
                self.assertEqual(resolve_club_crest_url(path), expected)

    def test_resolution_does_not_mutate_stored_report(self):
        report = {
            'home_club_crest': 'game/images/crests/915.png',
            'man_of_the_match': {'club_crest': 'game/images/crests/915.png'},
        }
        before = json.dumps(report)
        resolved = _ensure_crests_in_report(report)
        self.assertEqual(json.dumps(report), before)
        self.assertEqual(resolved['man_of_the_match']['club_crest'],
                         resolved['home_club_crest'])


@override_settings(ASSETS_BASE_URL='/assets/')
class MatchReportCrestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        league = League.objects.create(name='Wappen-Testliga', country='Deutschland')
        cls.home = Club.objects.create(
            name='Heimverein', short_name='HEIM', league=league, fm_inside_id=915,
            founded_year=1900, budget=0,
        )
        cls.away = Club.objects.create(
            name='Gastverein', short_name='GAST', league=league, fm_inside_id=907,
            founded_year=1900, budget=0,
        )
        cls.user = get_user_model().objects.create_user(username='crest-test')
        cls.match = SimulatedMatch.objects.create(
            home_club=cls.home, away_club=cls.away,
        )
        SeasonFixture.objects.create(
            league=league, matchday=1, home_club=cls.home, away_club=cls.away,
            is_played=True, simulated_match=cls.match,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_images_in_both_report_routes_for_old_and_new_reports(self):
        cases = (
            ('game/images/crests/915.png', 'game/images/crests/907.png',
             static('game/images/crests/915.png'), static('game/images/crests/907.png')),
            (self.home.crest_static_path, self.away.crest_static_path,
             self.home.crest_static_path, self.away.crest_static_path),
            ('/static/assets/clubs/logos/915_club.png',
             '/static/assets/clubs/logos/907_club.png',
             self.home.crest_static_path, self.away.crest_static_path),
            (None, None, self.home.crest_static_path, self.away.crest_static_path),
        )
        routes = (
            reverse('club_match_report', args=[self.home.pk]),
            reverse('club_match_report', args=[self.away.pk]),
            reverse('match_report_by_id', args=[self.match.pk]),
        )
        for home_path, away_path, home_url, away_url in cases:
            report = {
                'home_club_id': self.home.pk, 'away_club_id': self.away.pk,
                'home_club_name': self.home.name, 'away_club_name': self.away.name,
                'home_club_short': 'HEIM', 'away_club_short': 'GAST',
                'home_club_crest': home_path, 'away_club_crest': away_path,
                'home_goals': 0, 'away_goals': 0,
                'man_of_the_match': {
                    'name': 'Testspieler', 'team': 'home',
                    'club_crest': home_path or self.home.crest_static_path,
                },
            }
            self.match.report_data = report
            self.match.save(update_fields=['report_data'])
            for route in routes:
                with self.subTest(home_path=home_path, route=route):
                    response = self.client.get(route)
                    self.assertEqual(response.status_code, 200)
                    html = response.content.decode()
                    self.assertIn(f'class="hero-crest home" src="{home_url}"', html)
                    self.assertIn(f'class="hero-crest away" src="{away_url}"', html)
                    sources = ImageSources(html).sources
                    self.assertGreater(sources.count(home_url), 1)
                    self.assertGreater(sources.count(away_url), 1)
                    crest_sources = [src for src in sources
                                     if '/crests/' in src or '/clubs/logos/' in src]
                    self.assertTrue(all(src.startswith(('/', 'https://', 'http://'))
                                        for src in crest_sources))
                    momentum = response.context['rc']['momentum_payload']
                    self.assertEqual(momentum['home_crest'], home_url)
                    self.assertEqual(momentum['away_crest'], away_url)
                    self.match.refresh_from_db()
                    # Existing weather backfill may persist its own fields.
                    for key in ('home_club_crest', 'away_club_crest', 'man_of_the_match'):
                        self.assertEqual(self.match.report_data[key], report[key])