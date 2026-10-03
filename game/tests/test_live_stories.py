"""Acceptance of frozen narration, timed eligibility and result boundaries."""
import io
import json
import zipfile
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from game.models import (
    Club, League, SimulatedMatch, MatchStory, MatchStoryRound, MatchEvent,
    StorySettings, StoryAudit, TacticSetup, SeasonFixture, FriendlyFixture,
)
from game.match_story.django_bridge import build_story_for, expected_duration, tactic_snapshot
from game.story_release import ensure_round, refresh_barrier, round_is_released, is_released

ROOT = Path(__file__).resolve().parents[2]


class LiveStoryAcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='ticker-viewer', password='test-only')
        cls.admin = get_user_model().objects.create_superuser(
            username='ticker-admin', password='test-only', email='')
        cls.league = League.objects.create(name='Live Test League')
        cls.home = Club.objects.create(name='Live Home', short_name='HOM', league=cls.league,
                                       founded_year=1900, budget=0)
        cls.away = Club.objects.create(name='Live Away', short_name='AWY', league=cls.league,
                                       founded_year=1900, budget=0)

    def setUp(self):
        self.client.force_login(self.user)
        self.now = timezone.now()

    def match(self, rd=None, **kwargs):
        return SimulatedMatch.objects.create(
            home_club=self.home, away_club=self.away,
            home_goals=(rd or {}).get('home_goals', 0),
            away_goals=(rd or {}).get('away_goals', 0),
            report_data=rd or {}, **kwargs)

    def story(self, *, round_=None, duration=900, source='1'):
        round_ = round_ or ensure_round(
            f'unit:{source}', [source], [self.home.pk, self.away.pk], 'Test round',
            league_id=self.league.pk, kickoff_at=self.now)
        sm = self.match(story_round=round_, story_source_key=source)
        story = MatchStory.objects.create(
            match=sm, round=round_, source_key=source, kickoff_at=round_.kickoff_at,
            duration_s=duration, final_score='9:8')
        refresh_barrier(round_.pk)
        return story

    def event(self, story, order, offset, *, cls='analysis', team=None, duration=0, text=None):
        return MatchEvent.objects.create(
            story=story, order=order, seq=order, beat=1, minute=order,
            offset_s=offset, duration_s=duration, cls=cls, kind=cls,
            team=team, text=text or f'line-{order}', visible=False)

    def test_reference_real_regeneration_and_hard_core_counts(self):
        from game.match_story.django_bridge import _core_issues
        # Uploaded original inputs are mandatory, never silently skipped.
        with zipfile.ZipFile(ROOT / 'attached_assets/0_files_1791022230871.zip') as z:
            for ident, allowed, duration in ((114, 1, 900), (179, 0, 900), (6, 5, 1310)):
                with self.subTest(match=ident):
                    export = json.loads(z.read(f'match_{ident}.json'))
                    sm = self.match(export['report_data'], pk=ident,
                                    match_type=export['match']['match_type'])
                    snapshot = {'home': export['home_tactic'], 'away': export['away_tactic'],
                                'provenance': 'reference_export'}
                    with patch('game.match_story.django_bridge.narrate',
                               wraps=__import__('game.match_story', fromlist=['narrate']).narrate) as narrator:
                        first = build_story_for(sm, snapshot=snapshot)
                        a = list(first.events.values('text', 'offset_s', 'duration_s', 'payload'))
                        second = build_story_for(sm, force=True)
                        b = list(second.events.values('text', 'offset_s', 'duration_s', 'payload'))
                        self.assertEqual(narrator.call_count, 2)
                    self.assertEqual(a, b)
                    self.assertAlmostEqual(second.duration_s, duration, places=2)
                    self.assertEqual(len(second.issues), allowed)
                    self.assertFalse(any('Kernzahlen' in i for i in second.issues))
                    self.assertFalse(_core_issues(sm, list(second.events.all())))
                    self.assertTrue(all('Engine' in i for i in second.issues))
                    self.assertTrue(any(e.payload.get('beats') for e in second.events.all()))
                    self.assertTrue(second.round.historical)
                    sm.refresh_from_db()
                    self.assertEqual(sm.report_data, export['report_data'])
                    self.assertEqual(StoryAudit.objects.filter(target=str(ident)).count(), 1)

    def test_frozen_package_byte_for_byte(self):
        with zipfile.ZipFile(ROOT / 'attached_assets/files_1791021008494.zip') as outer:
            with zipfile.ZipFile(io.BytesIO(outer.read('match_story_v4_baseline.zip'))) as inner:
                for name in inner.namelist():
                    if not name.endswith('/'):
                        self.assertEqual((ROOT / 'game' / name).read_bytes(), inner.read(name), name)

    def test_offset_boundary_order_and_zero_duration(self):
        story = self.story()
        self.event(story, 0, 10, cls='phase')
        self.event(story, 1, 10, cls='analysis')
        self.event(story, 2, 9, cls='goal', team='home', text='eligible goal')
        self.event(story, 3, 11, cls='goal', team='away', text='FUTURE SECRET')
        with patch('game.views_story.timezone.now', return_value=self.now + timedelta(seconds=10)):
            data = self.client.get(reverse('story_ticker_api', args=[story.match_id])).json()
            conf = self.client.get(reverse('story_conference_api', args=[story.round_id])).json()
        self.assertEqual([e['order'] for e in data['events']], [0, 1, 2])
        self.assertEqual(data['score'], '1:0')
        self.assertNotIn('FUTURE SECRET', json.dumps(data))
        self.assertEqual(conf['matches'][0]['last_event']['order'], 2)
        self.assertEqual(conf['matches'][0]['score'], '1:0')
        self.assertFalse(data['released'])

    def test_round_waits_for_missing_story_then_latest_whistle(self):
        round_ = ensure_round('test:shared', ['one', 'two'], [self.home.pk], 'Shared', kickoff_at=self.now)
        one = self.story(round_=round_, source='one')
        round_.refresh_from_db()
        self.assertIsNone(round_.release_at)
        self.assertFalse(round_is_released(round_, self.now + timedelta(days=1)))
        self.story(round_=round_, source='two', duration=1310)
        round_.refresh_from_db()
        self.assertEqual(round_.release_at, self.now + timedelta(seconds=1310))
        self.assertFalse(round_is_released(round_, self.now + timedelta(seconds=1309)))
        self.assertTrue(round_is_released(round_, self.now + timedelta(seconds=1310)))
        self.assertEqual(one.kickoff_at, round_.kickoff_at)

    def test_independent_friendlies_and_no_clock_reset(self):
        short = self.story(source='short')
        long = self.story(source='long', duration=1310)
        now = self.now + timedelta(seconds=901)
        self.assertTrue(is_released(short.match, now))
        self.assertFalse(is_released(long.match, now))
        again = ensure_round('unit:short', ['short'], [self.home.pk], 'Changed', kickoff_at=now)
        self.assertEqual(again.kickoff_at, self.now)

    def test_conference_constant_query_count_no_per_match_requests(self):
        round_ = ensure_round('large', ['1', '2', '3', '4'], [self.home.pk], 'Large', kickoff_at=self.now)
        for i in range(1, 5):
            story = self.story(round_=round_, source=str(i))
            self.event(story, 1, 0)
        # Authentication/session/last-seen middleware add fixed overhead.
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('story_conference_api', args=[round_.pk]))
        self.assertEqual(len(response.json()['matches']), 4)
        story_queries = [q['sql'] for q in queries if 'game_matchstory' in q['sql'] or 'game_matchevent' in q['sql']]
        self.assertEqual(len(story_queries), 3)
        script = (ROOT / 'game/static/game/js/live_story.js').read_text()
        self.assertNotIn('api/live/matches', script)
        self.assertIn('no-store', response['Cache-Control'])

    def test_admin_override_auth_confirmation_audit(self):
        story = self.story()
        url = reverse('story_admin_action')
        form = {'action': 'round_override', 'round_id': story.round_id,
                'enabled': 'false', 'confirmed': 'yes'}
        self.assertEqual(self.client.post(url, form).status_code, 403)
        self.client.force_login(self.admin)
        unconfirmed = dict(form, confirmed='no')
        self.assertEqual(self.client.post(url, unconfirmed).status_code, 400)
        self.assertEqual(self.client.post(url, form).status_code, 302)
        self.assertTrue(is_released(story.match))
        self.assertEqual(StoryAudit.objects.filter(action='round_override').count(), 1)
        self.client.post(url, {'action': 'global_override', 'enabled': 'false', 'confirmed': 'yes'})
        self.assertFalse(StorySettings.objects.get(pk=1).story_release_enabled)
        conference = self.client.get(reverse('story_conference_api', args=[story.round_id])).json()
        self.assertTrue(conference['matches'][0]['ended'])

    def test_fallback_failure_is_persisted_and_timed(self):
        rd = {'home_goals': 1, 'away_goals': 0,
              'goal_events': [{'minute': 90, 'team': 'home', 'scorer_name': 'Real scorer'}]}
        sm = self.match(rd)
        round_ = ensure_round('failed', [str(sm.pk)], [self.home.pk], 'Failed', kickoff_at=self.now)
        with patch('game.match_story.django_bridge.narrate', side_effect=ValueError('fixture error')):
            story = build_story_for(sm, round_=round_)
        self.assertTrue(story.issues[0].startswith('narrator_failed'))
        self.assertEqual(story.duration_s, 900)
        with patch('game.views_story.timezone.now', return_value=self.now + timedelta(seconds=899)):
            data = self.client.get(reverse('story_ticker_api', args=[sm.pk])).json()
        self.assertEqual(data['score'], '0:0')
        self.assertTrue(data['fallback'])
        self.assertFalse(data['events'])

    def test_pages_admins_and_embedded_json_cannot_bypass_lock(self):
        story = self.story()
        self.event(story, 1, 800, cls='goal', team='home', text='FUTURE SECRET')
        for user in (self.user, self.admin):
            self.client.force_login(user)
            for name, args in (
                ('home', []), ('club_detail', [self.home.pk]),
                ('league_detail', [self.league.pk]), ('club_table', [self.home.pk]),
                ('club_news', [self.home.pk]), ('calendar', []),
                ('notifications_page', []), ('club_professional_squad', [self.home.pk]),
            ):
                with self.subTest(role=user.username, route=name):
                    response = self.client.get(reverse(name, args=args))
                    self.assertEqual(response.status_code, 423)
                    self.assertNotContains(response, 'FUTURE SECRET', status_code=423)
            report = self.client.get(reverse('match_report_by_id', args=[story.match_id]))
            self.assertEqual(report.status_code, 200)
            self.assertNotContains(report, 'FUTURE SECRET')
            self.assertNotContains(report, '9:8')
            self.assertNotContains(report, 'report_data')

    def test_calendar_results_hidden_on_other_pages(self):
        from game.context_processors import _build_global_calendar
        round_ = ensure_round(f'league:{self.league.pk}:0:1', ['calendar'],
                              [self.home.pk], 'Calendar live', kickoff_at=self.now)
        story = self.story(round_=round_, source='calendar')
        SeasonFixture.objects.create(
            league=self.league, season='0', matchday=1, home_club=self.home, away_club=self.away,
            scheduled_date=self.now.date(), is_played=True, home_goals=7, away_goals=6,
            simulated_match=story.match,
        )
        payload = _build_global_calendar(self.home, 0)
        self.assertNotIn('7:6', json.dumps(payload, default=str))

    def test_backfill_dry_run_no_writes_and_old_games_stay_released(self):
        sm = self.match()
        stream = io.StringIO()
        call_command('build_match_stories', since=sm.pk, dry_run=True, stdout=stream)
        self.assertFalse(MatchStory.objects.filter(match=sm).exists())
        self.assertFalse(MatchStoryRound.objects.exists())
        call_command('build_match_stories', since=sm.pk, stdout=stream)
        story = MatchStory.objects.get(match=sm)
        self.assertTrue(story.round.historical)
        self.assertTrue(is_released(sm))
        created = story.created_at
        call_command('build_match_stories', since=sm.pk, stdout=stream)
        story.refresh_from_db()
        self.assertEqual(story.created_at, created)

    def test_snapshot_uses_friendly_context_and_is_detached(self):
        tactic = TacticSetup.objects.create(
            club=self.home, context='freundschaft', instructions={'attack_focus': 'ueber_links'})
        snapshot = tactic_snapshot(self.home, self.away, context='freundschaft')
        tactic.instructions['attack_focus'] = 'ueber_rechts'
        tactic.save()
        self.assertEqual(snapshot['home']['instructions']['attack_focus'], 'ueber_links')
        self.assertIsNone(snapshot['away'])

    def test_missing_story_cannot_bypass_registered_round(self):
        round_ = ensure_round('incomplete', ['1'], [self.home.pk], 'Incomplete')
        sm = self.match(story_round=round_)
        self.assertFalse(is_released(sm, self.now + timedelta(days=1)))
        data = self.client.get(reverse('story_ticker_api', args=[sm.pk])).json()
        self.assertEqual(data['status'], 'preparing')
        self.assertEqual(data['score'], '0:0')
        self.assertFalse(data['released'])

    def test_match_id_changes_seed_not_reloading_time(self):
        with zipfile.ZipFile(ROOT / 'attached_assets/0_files_1791022230871.zip') as z:
            export = json.loads(z.read('match_114.json'))
        snapshot = {'home': export['home_tactic'], 'away': export['away_tactic']}
        first = build_story_for(self.match(export['report_data']), snapshot=snapshot)
        second = build_story_for(self.match(export['report_data']), snapshot=snapshot)
        self.assertNotEqual(
            list(first.events.values_list('text', 'offset_s')),
            list(second.events.values_list('text', 'offset_s')))

    def test_independent_league_and_historical_season_are_not_locked(self):
        ensure_round(f'league:{self.league.pk}:99:1', ['pending'], [self.home.pk],
                     'Season 99', league_id=self.league.pk)
        other = League.objects.create(name='Independent')
        self.assertNotEqual(self.client.get(reverse('league_detail', args=[other.pk])).status_code, 423)
        # A registered new league round must not lock a historical season.
        self.assertNotEqual(self.client.get(reverse('league_detail', args=[self.league.pk]),
                                           {'season': '0'}).status_code, 423)

    def test_admin_model_list_is_also_result_protected(self):
        self.story()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin/game/simulatedmatch/').status_code, 423)

    def test_public_result_routes_cannot_bypass_lock_when_logged_out(self):
        story = self.story()
        self.client.logout()
        for name, args in (
                ('league_detail', [self.league.pk]), ('club_table', [self.home.pk]),
                ('club_news', [self.home.pk])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 423)
        response = self.client.get(reverse('match_report_by_id', args=[story.match_id]))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(b'9:8', response.content)

    def test_repair_missing_live_story_does_not_make_it_historical(self):
        round_ = ensure_round('repair', ['match-source'], [self.home.pk], 'Repair', kickoff_at=self.now)
        sm = self.match(story_round=round_, story_source_key='match-source',
                        story_tactic_snapshot={'home': None, 'away': None, 'provenance': 'simulation'})
        story = build_story_for(sm)
        self.assertEqual(story.round_id, round_.pk)
        self.assertFalse(story.round.historical)
        self.assertEqual(story.source_key, 'match-source')
        self.assertEqual(story.kickoff_at, self.now)

    def test_csrf_rebuild_and_invalid_override_are_rejected(self):
        from django.test import Client
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(reverse('story_admin_action'), {
            'action': 'global_override', 'confirmed': 'yes', 'enabled': 'false'}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('story_admin_action'), {
            'action': 'global_override', 'confirmed': 'yes'}).status_code, 400)

    def test_segment_momentum_uses_observed_pressure_and_preserves_goal_side(self):
        from game.views import _build_match_momentum
        segments = [
            {'minute_from': 0, 'minute_to': 45, 'home': {'shots': 9, 'corners': 4},
             'away': {'shots': 0}},
            {'minute_from': 45, 'minute_to': 90, 'home': {'shots': 0},
             'away': {'shots': 9, 'corners': 4}},
        ]
        curve = _build_match_momentum([], segment_log=segments)
        self.assertGreater(curve[25], 0)
        self.assertLess(curve[75], 0)
        goal_curve = _build_match_momentum([{'type': 'goal', 'minute': 75, 'team': 'home'}],
                                          segment_log=segments)
        self.assertGreater(goal_curve[75], 0)
        extended = _build_match_momentum([], segment_log=[
            {'minute_from': 90, 'minute_to': 120, 'home': {'shots': 5}, 'away': {'shots': 0}}])
        self.assertEqual(len(extended), 121)
        self.assertGreater(extended[115], 0)

    def test_pending_conference_contains_unsimulated_fixtures(self):
        fixture = SeasonFixture.objects.create(
            league=self.league, season='0', matchday=1, home_club=self.home, away_club=self.away,
            scheduled_date=self.now.date())
        round_ = ensure_round(f'league:{self.league.pk}:0:1', [str(fixture.pk)], [self.home.pk],
                              'Pending league', league_id=self.league.pk)
        data = self.client.get(reverse('story_conference_api', args=[round_.pk])).json()
        self.assertEqual(data['pending_count'], 1)
        self.assertEqual(len(data['matches']), 1)
        self.assertEqual(data['matches'][0]['score'], '0:0')
        self.assertEqual(data['matches'][0]['home'], self.home.name)
        self.assertIsNone(data['matches'][0]['ticker_url'])