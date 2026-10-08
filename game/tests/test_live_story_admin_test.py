import copy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client, TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from game.live_story_test import SESSION_KEY, generate_run
from game.models import Club, League, MatchStory, SimulatedMatch


def sample_run():
    event = lambda order, offset, cls, minute, added=0: {
        'order': order, 'offset_s': offset, 'duration_s': 0, 'cls': cls,
        'kind': cls, 'minute': minute, 'added': added, 'level': 3,
        'text': f'line-{order}', 'team': 'home' if cls == 'goal' else None,
    }
    story = {
        'home': 'Bayern', 'away': 'Dortmund', 'duration_s': 900,
        'events': [event(2, 20, 'goal', 90, 2), event(0, 0, 'phase', 0),
                   event(1, 10, 'analysis', 90)], 'issues': [],
    }
    return {
        'run_id': 'test-run', 'kickoff_at': timezone.now().isoformat(),
        'duration_s': 900, 'stories': [{**copy.deepcopy(story), 'id': i}
                                     for i in range(1, 4)],
    }


class AdminLiveStoryTestTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            'ticker-sandbox-admin', is_superuser=True, is_staff=True)
        self.user = get_user_model().objects.create_user(
            'ticker-sandbox-staff', is_staff=True)

    def store(self, run):
        session = self.client.session
        session[SESSION_KEY] = run
        session.save()

    def test_every_route_denies_non_admin_without_generation(self):
        names = [('story_test_start', []), ('story_test_ticker', [1]),
                 ('story_test_conference', []), ('story_test_ticker_api', [1]),
                 ('story_test_conference_api', []), ('story_test_reset', [])]
        with patch('game.views_story_test.generate_run') as generate:
            for name, args in names:
                url = reverse(name, args=args)
                self.assertEqual(self.client.get(url).status_code, 302)
                self.client.force_login(self.user)
                response = self.client.post(url) if name == 'story_test_reset' else self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.client.logout()
            generate.assert_not_called()

    def test_auto_start_reload_and_reset_are_different_actions(self):
        self.client.force_login(self.admin)
        first = sample_run()
        second = sample_run()
        second['run_id'] = 'new-simulation'
        with patch('game.views_story_test.generate_run', side_effect=[first, second]) as generate:
            for _ in range(2):
                response = self.client.get(reverse('story_test_start'))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Test zurücksetzen')
                self.assertNotContains(response, 'Story neu aufbauen')
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(self.client.session[SESSION_KEY]['kickoff_at'], first['kickoff_at'])
            self.assertEqual(self.client.get(reverse('story_test_reset')).status_code, 405)
            response = self.client.post(reverse('story_test_reset'))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(self.client.session[SESSION_KEY]['run_id'], second['run_id'])
        self.assertEqual(SimulatedMatch.objects.count(), 0)
        self.assertEqual(MatchStory.objects.count(), 0)

    def test_dortmund_preview_is_only_in_admin_test_ticker(self):
        self.client.force_login(self.admin)
        self.store(sample_run())
        response = self.client.get(reverse('story_test_start'))
        self.assertContains(response, 'id="ticker-stadium-preview"')
        self.assertContains(response, 'ticker_stadium_preview.js?v=17')
        self.assertContains(response, 'ticker_stadium_preview.css?v=17')
        self.assertNotContains(response, 'id="ticker-camera-height"')
        self.assertNotContains(response, 'id="ticker-camera-reset"')
        self.assertContains(response, 'Feste Kamera')
        self.assertContains(response, 'BILDBASIERTES UMFELD')
        self.assertContains(response, 'id="ticker-roof-visible"')
        self.assertContains(response, 'Mit Dach')
        self.assertContains(response, 'stage/vendor/three.module.js')
        self.assertContains(response, 'noch ohne Spieleranimation')
        self.assertContains(response, 'id="ticker-stadium-environment"')
        background = response.context['ticker_stadium_environment']['imageBackground']
        self.assertEqual(background['clubFmId'], 907)
        self.assertEqual(background['model'], 'dortmund')
        self.assertEqual(set(background['images']), {'day', 'night'})
        self.assertNotIn('naturalPackage', response.context['ticker_stadium_environment'])
        self.assertNotContains(
            self.client.get(reverse('story_test_conference')), 'ticker-stadium-preview')
        normal = render_to_string('game/live_ticker.html', {
            'home_name': 'Home', 'away_name': 'Away', 'match_id': 1,
            'api_url': '/api/live/matches/1/', 'is_test': False,
        })
        self.assertNotIn('ticker-stadium-preview', normal)
        self.assertNotIn('ticker_stadium_preview', normal)
        self.assertNotIn('type="importmap"', normal)
        self.assertNotIn('ticker-camera-height', normal)
        self.assertNotIn('ticker-roof-visible', normal)

    def test_original_clock_offset_gate_order_and_conference_aggregation(self):
        self.client.force_login(self.admin)
        run = sample_run()
        now = timezone.now()
        run['kickoff_at'] = (now - timedelta(seconds=15)).isoformat()
        self.store(run)
        with patch('game.views_story_test.timezone.now', return_value=now):
            data = self.client.get(reverse('story_test_ticker_api', args=[1])).json()
            self.assertEqual(data['elapsed_s'], 15)
            self.assertEqual([e['order'] for e in data['events']], [0, 1])
            self.assertEqual(data['score'], '0:0')
            self.assertFalse(data['released'])
            conference = self.client.get(reverse('story_test_conference_api')).json()
            self.assertEqual(len(conference['matches']), 3)
            self.assertTrue(all(m['score'] == '0:0' for m in conference['matches']))
            self.assertEqual(conference['elapsed_s'], 15)
        with patch('game.views_story_test.timezone.now', return_value=now + timedelta(seconds=10)):
            data = self.client.get(reverse('story_test_ticker_api', args=[1])).json()
            self.assertEqual([e['order'] for e in data['events']], [0, 1, 2])
            self.assertEqual(data['events'][-1]['added'], 2)
            self.assertEqual(data['score'], '1:0')
        with patch('game.views_story_test.timezone.now', return_value=now + timedelta(seconds=900)):
            self.assertTrue(self.client.get(reverse('story_test_ticker_api', args=[1])).json()['released'])

    def test_reset_requires_csrf_and_failed_reset_keeps_old_run(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse('story_test_reset')).status_code, 403)
        self.client.force_login(self.admin)
        run = sample_run()
        self.store(run)
        with patch('game.views_story_test.generate_run', side_effect=ValueError('test failure')):
            self.assertEqual(self.client.post(reverse('story_test_reset')).status_code, 503)
        self.assertEqual(self.client.session[SESSION_KEY]['run_id'], run['run_id'])

    def test_real_generation_boundary_rolls_back_engine_writes_and_hooks(self):
        league = League.objects.create(name='Sandbox rollback')
        home = Club.objects.create(name='Bayern', league=league, fm_inside_id=915, founded_year=1900, budget=0)
        away = Club.objects.create(name='Dortmund', league=league, fm_inside_id=907, founded_year=1900, budget=0)
        callbacks = []
        def engine(h, a):
            Club.objects.filter(pk=h.pk).update(name='MUST ROLL BACK')
            transaction.on_commit(lambda: callbacks.append(True))
            return {'home_goals': 1, 'away_goals': 0}
        line = SimpleNamespace(minute=90, added=2, team='home', cls='goal',
                               kind='goal', text='New goal', payload={'level': 5},
                               offset_s=899, duration_s=1)
        with patch('game.live_story_test.simulate_match', side_effect=engine) as sim, \
             patch('game.live_story_test.tactic_snapshot', return_value={}), \
             patch('game.live_story_test.narrate', return_value={'lines': [line], 'issues': []}):
            first = generate_run()
            second = generate_run()
        home.refresh_from_db()
        self.assertEqual(home.name, 'Bayern')
        self.assertEqual(callbacks, [])
        self.assertEqual(sim.call_count, 6)
        self.assertEqual(sim.call_args.args, (home, away))
        self.assertNotEqual(first['run_id'], second['run_id'])
        self.assertEqual(first['duration_s'], 900)
        self.assertEqual(SimulatedMatch.objects.count(), 0)