"""Tests für CMT Auto-Create und extern_loan-Semantik.

Abgedeckt:
  1. extern_loan erscheint nicht im Free-Agent-Pool
  2. extern_loan erscheint nicht in der Creator-vereinslos-Liste
  3. Doppelter Auto-Create erzeugt keine Dublette (Idempotenz)
  4. CMT-ID-Match findet vorhandenen extern_loan-Spieler wieder
"""

from unittest import mock

from django.test import TestCase

from game.models import (
    Club,
    DataSource,
    League,
    Player,
    PlayerExternalId,
    PlayerStrengthProfile,
)


# ── Minimal-Fixtures ────────────────────────────────────────────────────────

def _make_league():
    return League.objects.create(name='Testliga', country='Testland')


def _make_club(league, name='FC Test'):
    return Club.objects.create(
        name=name,
        short_name=name[:8],
        founded_year=1900,
        budget=1_000_000,
        league=league,
        fan_popularity=50,
    )


def _make_cmt_source():
    return DataSource.objects.get_or_create(
        code='CMTRACKER',
        defaults={'name': 'CMTracker', 'url': 'https://cmtracker.net'},
    )[0]


def _raw_payload(player_id='99001', firstname='Max', lastname='Mustermann',
                 overall=75, potential=80, dob='1998-05-15',
                 club_team='FC Ausland', loan_team=''):
    """Minimaler CMT-Rohpayload."""
    return {
        'info': {
            'playerid': player_id,
            'name': {'firstname': firstname, 'lastname': lastname, 'knownas': ''},
            'overallrating': overall,
            'potential': potential,
            'birthdate': dob,
            'teams': {
                'club_team': {'name': club_team},
                'loan_team': {'name': loan_team},
            },
        },
        'attributes': {},
        'card_attrs': {},
    }


def _auto_create(raw, db_slug='26062400', ws_club=None, dry_run=False):
    """Wrapper um store_player_profiles zu mocken."""
    from game.cmt_profile_service import create_player_from_cmt_raw
    with mock.patch('game.cmt_profile_service.store_player_profiles'):
        return create_player_from_cmt_raw(
            raw, db_slug=db_slug, ws_club=ws_club, dry_run=dry_run
        )


# ── Tests ────────────────────────────────────────────────────────────────────

class ExternLoanFreeAgentPoolTest(TestCase):
    """extern_loan erscheint nicht im Free-Agent-Pool (club=None AND loan_status=none)."""

    def setUp(self):
        _make_cmt_source()
        self.raw = _raw_payload(
            player_id='99001',
            club_team='FC Ausland',
            loan_team='FC Leihgeber',
        )

    def test_extern_loan_excluded_from_free_agent_qs(self):
        result = _auto_create(self.raw)
        self.assertEqual(result['status'], 'created')

        player = result['player']
        self.assertEqual(player.loan_status, 'extern_loan')
        self.assertIsNone(player.club)

        # Kanonischer Free-Agent-Filter: club=None UND loan_status='none'
        free_agents = Player.objects.filter(club__isnull=True, loan_status='none')
        self.assertNotIn(player, free_agents)

    def test_extern_loan_excluded_from_vereinslose_view_qs(self):
        """Entspricht der Abfrage in views_creator.creator_vereinslose."""
        result = _auto_create(self.raw)
        player = result['player']

        creator_qs = Player.objects.filter(club__isnull=True).exclude(
            loan_status='extern_loan'
        )
        self.assertNotIn(player, creator_qs)

    def test_regular_vereinsloser_still_in_free_agent_qs(self):
        """Echter vereinsloser Spieler (kein Leihverhältnis) erscheint im Pool."""
        raw_no_loan = _raw_payload(
            player_id='99002', loan_team='',
        )
        result = _auto_create(raw_no_loan)
        player = result['player']
        self.assertEqual(player.loan_status, 'none')

        free_agents = Player.objects.filter(club__isnull=True, loan_status='none')
        self.assertIn(player, free_agents)


class AutoCreateIdempotencyTest(TestCase):
    """Doppelter Auto-Create erzeugt keine Dublette."""

    def setUp(self):
        _make_cmt_source()
        self.raw = _raw_payload(player_id='99010')

    def test_double_create_no_duplicate(self):
        r1 = _auto_create(self.raw)
        r2 = _auto_create(self.raw)

        self.assertEqual(r1['status'], 'created')
        self.assertEqual(r2['status'], 'skipped')
        self.assertIn('bereits vorhanden', r2['reason'])

        count = Player.objects.filter(wsc_player_id='CMT99010').count()
        self.assertEqual(count, 1)

    def test_double_create_preserves_player_id(self):
        r1 = _auto_create(self.raw)
        r2 = _auto_create(self.raw)
        self.assertEqual(r1['player'].pk, r2['player'].pk)


class WsClubDecisionMatrixTest(TestCase):
    """Entscheidungsmatrix: ws_club × loan_team → korrekte club/loan_status."""

    def setUp(self):
        league = _make_league()
        self.ws_club = _make_club(league, name='FC Bayern')
        _make_cmt_source()

    def test_ws_club_with_loan_team_gives_loaned_in(self):
        raw = _raw_payload(
            player_id='99020', club_team='FC Bayern', loan_team='FC Leihgeber'
        )
        r = _auto_create(raw, ws_club=self.ws_club)
        self.assertEqual(r['status'], 'created')
        p = r['player']
        self.assertEqual(p.loan_status, 'loaned_in')
        self.assertEqual(p.club, self.ws_club)

    def test_ws_club_without_loan_team_gives_none_status(self):
        raw = _raw_payload(
            player_id='99021', club_team='FC Bayern', loan_team=''
        )
        r = _auto_create(raw, ws_club=self.ws_club)
        p = r['player']
        self.assertEqual(p.loan_status, 'none')
        self.assertEqual(p.club, self.ws_club)

    def test_no_ws_club_with_loan_team_gives_extern_loan(self):
        raw = _raw_payload(
            player_id='99022', club_team='FC Ausland', loan_team='FC Leihgeber'
        )
        r = _auto_create(raw, ws_club=None)
        p = r['player']
        self.assertEqual(p.loan_status, 'extern_loan')
        self.assertIsNone(p.club)

    def test_no_ws_club_no_loan_team_gives_vereinslos(self):
        raw = _raw_payload(
            player_id='99023', club_team='FC Ausland', loan_team=''
        )
        r = _auto_create(raw, ws_club=None)
        p = r['player']
        self.assertEqual(p.loan_status, 'none')
        self.assertIsNone(p.club)


class CmtIdMatchExistingPlayerTest(TestCase):
    """CMT-ID-Match findet vorhandenen extern_loan-Spieler korrekt wieder."""

    def setUp(self):
        _make_cmt_source()
        self.raw = _raw_payload(
            player_id='99030', loan_team='FC Leihgeber'
        )

    def test_cmt_id_match_finds_existing_extern_loan(self):
        # Erst anlegen
        r1 = _auto_create(self.raw)
        self.assertEqual(r1['status'], 'created')
        created_pk = r1['player'].pk

        # Nochmals: Idempotenz-Check gibt den existierenden Spieler zurück
        r2 = _auto_create(self.raw)
        self.assertEqual(r2['status'], 'skipped')
        self.assertEqual(r2['player'].pk, created_pk)

    def test_player_external_id_exists_after_create(self):
        _auto_create(self.raw)
        cmt_source = DataSource.objects.get(code='CMTRACKER')
        exists = PlayerExternalId.objects.filter(
            source=cmt_source, external_id='99030'
        ).exists()
        self.assertTrue(exists)

    def test_strength_profile_created(self):
        r = _auto_create(self.raw)
        player = r['player']
        self.assertTrue(
            PlayerStrengthProfile.objects.filter(player=player).exists()
        )
        sp = PlayerStrengthProfile.objects.get(player=player)
        self.assertEqual(int(sp.base_strength), 75)  # overall aus _raw_payload

    def test_dry_run_does_not_create_player(self):
        r = _auto_create(self.raw, dry_run=True)
        self.assertEqual(r['status'], 'created')
        self.assertIsNone(r['player'])
        self.assertEqual(Player.objects.filter(wsc_player_id='CMT99030').count(), 0)
