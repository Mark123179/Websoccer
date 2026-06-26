"""Tests für CMT Auto-Create, extern_loan-Semantik, Positionsmapping und
WS-Club-Auflösung.

Abgedeckt:
  1. extern_loan erscheint nicht im Free-Agent-Pool
  2. extern_loan erscheint nicht in der Creator-vereinslos-Liste
  3. Doppelter Auto-Create erzeugt keine Dublette (Idempotenz)
  4. CMT-ID-Match findet vorhandenen extern_loan-Spieler wieder
  5. Positionsmapping: shortlabel, label (lang), dict, String, Fallback
  6. WS-Club-Auflösung: numerische ID wird ignoriert, Name schlägt fehl,
     CMT-Teamname matcht WS-Club per icontains
  7. Safety-Guard: Auto-Create mit unaufgelöstem Club bricht ab (kein dry-run)
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
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
                 club_team='FC Ausland', loan_team='',
                 roles=None):
    """Minimaler CMT-Rohpayload.

    roles: Liste von Rollen-Dicts, z. B. [{'pos': 'CDM', 'ovr': 82}].
           Wenn None → kein roles-Schlüssel im Payload (Fallback auf
           info.preferredposition für cmt_pos_raw).
    """
    payload = {
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
    if roles is not None:
        payload['roles'] = roles
    return payload


def _auto_create(raw, db_slug='26062400', ws_club=None, dry_run=False,
                 tm_position=None):
    """Wrapper um store_player_profiles zu mocken.

    tm_position muss explizit angegeben werden (WS-Positionscode aus TM-Import).
    Ohne tm_position gibt create_player_from_cmt_raw status='blocked' zurück —
    so wie es im echten Auto-Create-Pfad passiert.
    """
    from game.cmt_profile_service import create_player_from_cmt_raw
    with mock.patch('game.cmt_profile_service.store_player_profiles'):
        return create_player_from_cmt_raw(
            raw, db_slug=db_slug, ws_club=ws_club, dry_run=dry_run,
            tm_position=tm_position,
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
        result = _auto_create(self.raw, tm_position='ZM')
        self.assertEqual(result['status'], 'created')

        player = result['player']
        self.assertEqual(player.loan_status, 'extern_loan')
        self.assertIsNone(player.club)

        # Kanonischer Free-Agent-Filter: club=None UND loan_status='none'
        free_agents = Player.objects.filter(club__isnull=True, loan_status='none')
        self.assertNotIn(player, free_agents)

    def test_extern_loan_excluded_from_vereinslose_view_qs(self):
        """Entspricht der Abfrage in views_creator.creator_vereinslose."""
        result = _auto_create(self.raw, tm_position='ZM')
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
        result = _auto_create(raw_no_loan, tm_position='ZM')
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
        r1 = _auto_create(self.raw, tm_position='ZM')
        r2 = _auto_create(self.raw, tm_position='ZM')

        self.assertEqual(r1['status'], 'created')
        self.assertEqual(r2['status'], 'skipped')
        self.assertIn('bereits vorhanden', r2['reason'])

        count = Player.objects.filter(wsc_player_id='CMT99010').count()
        self.assertEqual(count, 1)

    def test_double_create_preserves_player_id(self):
        r1 = _auto_create(self.raw, tm_position='ZM')
        r2 = _auto_create(self.raw, tm_position='ZM')
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
        r = _auto_create(raw, ws_club=self.ws_club, tm_position='ZM')
        self.assertEqual(r['status'], 'created')
        p = r['player']
        self.assertEqual(p.loan_status, 'loaned_in')
        self.assertEqual(p.club, self.ws_club)

    def test_ws_club_without_loan_team_gives_none_status(self):
        raw = _raw_payload(
            player_id='99021', club_team='FC Bayern', loan_team=''
        )
        r = _auto_create(raw, ws_club=self.ws_club, tm_position='ZM')
        p = r['player']
        self.assertEqual(p.loan_status, 'none')
        self.assertEqual(p.club, self.ws_club)

    def test_no_ws_club_with_loan_team_gives_extern_loan(self):
        raw = _raw_payload(
            player_id='99022', club_team='FC Ausland', loan_team='FC Leihgeber'
        )
        r = _auto_create(raw, ws_club=None, tm_position='ZM')
        p = r['player']
        self.assertEqual(p.loan_status, 'extern_loan')
        self.assertIsNone(p.club)

    def test_no_ws_club_no_loan_team_gives_vereinslos(self):
        raw = _raw_payload(
            player_id='99023', club_team='FC Ausland', loan_team=''
        )
        r = _auto_create(raw, ws_club=None, tm_position='ZM')
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
        # Erst anlegen (mit TM-Position, da Pflicht)
        r1 = _auto_create(self.raw, tm_position='ZM')
        self.assertEqual(r1['status'], 'created')
        created_pk = r1['player'].pk

        # Nochmals: Idempotenz-Check gibt den existierenden Spieler zurück
        r2 = _auto_create(self.raw, tm_position='ZM')
        self.assertEqual(r2['status'], 'skipped')
        self.assertEqual(r2['player'].pk, created_pk)

    def test_player_external_id_exists_after_create(self):
        _auto_create(self.raw, tm_position='ZM')
        cmt_source = DataSource.objects.get(code='CMTRACKER')
        exists = PlayerExternalId.objects.filter(
            source=cmt_source, external_id='99030'
        ).exists()
        self.assertTrue(exists)

    def test_strength_profile_created(self):
        r = _auto_create(self.raw, tm_position='ZM')
        player = r['player']
        self.assertTrue(
            PlayerStrengthProfile.objects.filter(player=player).exists()
        )
        sp = PlayerStrengthProfile.objects.get(player=player)
        self.assertEqual(int(sp.base_strength), 75)  # overall aus _raw_payload

    def test_dry_run_does_not_create_player(self):
        r = _auto_create(self.raw, dry_run=True, tm_position='ZM')
        self.assertEqual(r['status'], 'created')
        self.assertIsNone(r['player'])
        self.assertEqual(Player.objects.filter(wsc_player_id='CMT99030').count(), 0)


# ── TM-Positions-Sperre ──────────────────────────────────────────────────────

class NoTmPositionBlockTest(TestCase):
    """Ohne TM-Position darf kein aktiver Kaderspieler angelegt werden.

    Fachliche Regel: TM.de ist ausschließliche Quelle für WS-Positionen.
    CMT-Positionsdaten (info.positions, roles[*].pos) sind nur Diagnose und
    dürfen NICHT in Player.position / main_position_1 / secondary_position_*
    geschrieben werden.
    """

    def setUp(self):
        _make_cmt_source()
        # Payload mit klar identifizierbarer CMT-Position via roles[0].pos
        # (Primärquelle für cmt_pos_raw) + preferredposition als Fallback.
        self.raw = _raw_payload(
            player_id='88001',
            overall=80,
            roles=[{'pos': 'CDM', 'ovr': 80, 'rle': 'Destroyer'}],
        )
        # preferredposition absichtlich anders als roles[0].pos → Priorität testbar
        self.raw['info']['preferredposition'] = {
            'shortlabel': 'CM',
            'label': 'Central Midfield',
            'abbr': 'CM',
        }

    # ── Kern: Blockade ohne TM-Position ──────────────────────────────────────

    def test_no_tm_position_returns_blocked(self):
        """Ohne tm_position → status='blocked', kein Player angelegt."""
        r = _auto_create(self.raw)  # tm_position=None (Standard)
        self.assertEqual(r['status'], 'blocked')
        self.assertIn('TM-Position fehlt', r['reason'])

    def test_blocked_player_not_created_in_db(self):
        """Blocked → kein Player-Datensatz in der Datenbank."""
        _auto_create(self.raw)  # kein tm_position
        self.assertEqual(
            Player.objects.filter(wsc_player_id='CMT88001').count(), 0,
            'Spieler darf bei blocked nicht angelegt werden.',
        )

    def test_dry_run_also_returns_blocked_without_tm_position(self):
        """Dry-Run ohne tm_position → ebenfalls blocked (keine ST-Vorschau)."""
        r = _auto_create(self.raw, dry_run=True)
        self.assertEqual(r['status'], 'blocked')
        self.assertIsNone(r['player'])

    def test_blocked_result_contains_cmt_pos_raw_for_diagnostics(self):
        """Blocked-Ergebnis enthält cmt_pos_raw als Diagnose-Information."""
        r = _auto_create(self.raw)
        # cmt_pos_raw muss gesetzt sein (CDM, nicht DM — das ist der CMT-Rohwert)
        self.assertIn('cmt_pos_raw', r)
        self.assertTrue(r['cmt_pos_raw'], 'cmt_pos_raw sollte nicht leer sein.')

    # ── CMT-Position nicht in WS-Feldern ─────────────────────────────────────

    def test_cmt_position_not_written_to_player_position_field(self):
        """Auch mit tm_position='RV': Player.position ist 'RV', nicht CDM/DM."""
        r = _auto_create(self.raw, tm_position='RV')
        self.assertEqual(r['status'], 'created')
        player = r['player']
        # TM-Position korrekt gesetzt
        self.assertEqual(player.position, 'RV')
        self.assertEqual(player.main_position_1, 'RV')
        # CMT-Position (CDM→DM) darf NICHT in WS-Feldern stehen
        self.assertNotEqual(player.position, 'DM',
                            'CMT-Position CDM→DM darf nicht in Player.position stehen.')
        self.assertNotEqual(player.position, 'ST',
                            'ST-Fallback aus CMT darf nicht vorkommen.')

    def test_result_position_matches_tm_position_not_cmt(self):
        """result['position'] entspricht tm_position, nicht CMT-Rohposition."""
        r = _auto_create(self.raw, tm_position='IV')
        self.assertEqual(r['position'], 'IV')
        # CMT-Diagnose ist separat
        self.assertNotEqual(r.get('cmt_pos_raw'), r['position'])

    # ── roles[0].pos als primäre Diagnosequelle ───────────────────────────────

    def test_cmt_pos_raw_prefers_roles_pos_over_preferredposition(self):
        """roles[0].pos hat Vorrang vor info.preferredposition für cmt_pos_raw.

        setUp setzt roles[0].pos='CDM' und preferredposition.shortlabel='CM'.
        cmt_pos_raw muss 'CDM' (aus roles) sein, nicht 'CM' (aus preferredposition).
        """
        r = _auto_create(self.raw)  # status=blocked, aber cmt_pos_raw ist gesetzt
        self.assertEqual(r['cmt_pos_raw'], 'CDM',
                         'roles[0].pos soll Vorrang vor preferredposition haben.')

    def test_cmt_pos_raw_falls_back_to_preferredposition_when_no_roles(self):
        """Ohne roles-Schlüssel → Fallback auf info.preferredposition.shortlabel."""
        raw_no_roles = _raw_payload(player_id='88099', overall=70)
        raw_no_roles['info']['preferredposition'] = {
            'shortlabel': 'RB', 'label': 'Right Back', 'abbr': 'RB',
        }
        # kein roles-Schlüssel im Payload
        r = _auto_create(raw_no_roles)
        self.assertEqual(r['cmt_pos_raw'], 'RB',
                         'Fallback auf preferredposition.shortlabel wenn roles fehlt.')

    def test_cmt_pos_raw_empty_roles_pos_falls_back(self):
        """roles[0].pos='' → Fallback auf preferredposition."""
        raw = _raw_payload(
            player_id='88098', overall=70,
            roles=[{'pos': '', 'ovr': 70}],
        )
        raw['info']['preferredposition'] = {
            'shortlabel': 'ST', 'label': 'Striker', 'abbr': 'ST',
        }
        r = _auto_create(raw)
        self.assertEqual(r['cmt_pos_raw'], 'ST',
                         'Leeres roles[0].pos soll auf preferredposition zurückfallen.')

    # ── Spielbarkeit / Transfermarkt ─────────────────────────────────────────

    def test_blocked_player_has_no_player_external_id(self):
        """Blocked → kein PlayerExternalId-Eintrag (Spieler existiert ja nicht)."""
        from game.models import DataSource, PlayerExternalId
        _auto_create(self.raw)
        cmt_source = DataSource.objects.get(code='CMTRACKER')
        self.assertFalse(
            PlayerExternalId.objects.filter(
                source=cmt_source, external_id='88001'
            ).exists(),
            'PlayerExternalId darf bei blocked nicht angelegt werden.',
        )

    def test_blocked_player_not_in_free_agent_pool(self):
        """Blocked → kein Spieler im Free-Agent-Pool (club=None, loan_status=none)."""
        _auto_create(self.raw)
        free_agents = Player.objects.filter(club__isnull=True, loan_status='none')
        self.assertEqual(
            free_agents.filter(wsc_player_id='CMT88001').count(), 0,
            'Blockierter Spieler darf nicht im Free-Agent-Pool erscheinen.',
        )


# ── Positionsmapping ─────────────────────────────────────────────────────────

class PositionMappingTest(TestCase):
    """_cmt_position_to_ws mappt alle relevanten EA-FC-Positionsformate korrekt."""

    def _pos(self, raw):
        from game.cmt_profile_service import _cmt_position_to_ws
        ws, raw_label = _cmt_position_to_ws(raw)
        return ws

    def _raw_with_label(self, label):
        return {'info': {'preferredposition': {'label': label}}}

    def _raw_with_shortlabel(self, shortlabel, label='Unknown Position'):
        return {'info': {'preferredposition': {
            'shortlabel': shortlabel, 'label': label,
        }}}

    def _raw_with_abbr(self, abbr, label='Unknown Position'):
        return {'info': {'preferredposition': {
            'abbr': abbr, 'label': label,
        }}}

    def _raw_with_string_pos(self, pos_string):
        return {'info': {'preferredposition': pos_string}}

    def test_shortlabel_cdm_maps_to_dm(self):
        """shortlabel='CDM' → DM (Schlüssel-Bugfix: vorher fiel es zu ST durch)."""
        self.assertEqual(self._pos(self._raw_with_shortlabel('CDM', 'Centre Defensive Midfield')), 'DM')

    def test_long_label_centre_defensive_midfield(self):
        """Langer EA-Label ohne shortlabel → DM."""
        self.assertEqual(self._pos(self._raw_with_label('Centre Defensive Midfield')), 'DM')

    def test_abbr_rb_maps_to_rv(self):
        """abbr='RB' → RV (Sacha Boey-Fall)."""
        self.assertEqual(self._pos(self._raw_with_abbr('RB', 'Right Back')), 'RV')

    def test_shortlabel_gk_maps_to_tw(self):
        self.assertEqual(self._pos(self._raw_with_shortlabel('GK', 'Goalkeeper')), 'TW')

    def test_shortlabel_cm_maps_to_zm(self):
        self.assertEqual(self._pos(self._raw_with_shortlabel('CM', 'Central Midfield')), 'ZM')

    def test_shortlabel_cam_maps_to_om(self):
        self.assertEqual(self._pos(self._raw_with_shortlabel('CAM', 'Attacking Midfield')), 'OM')

    def test_shortlabel_cb_maps_to_iv(self):
        self.assertEqual(self._pos(self._raw_with_shortlabel('CB', 'Centre Back')), 'IV')

    def test_shortlabel_lw_maps_to_lm(self):
        self.assertEqual(self._pos(self._raw_with_shortlabel('LW', 'Left Wing')), 'LM')

    def test_string_pos_cdm(self):
        """Positionsfeld ist direkt ein String 'CDM'."""
        self.assertEqual(self._pos(self._raw_with_string_pos('CDM')), 'DM')

    def test_string_pos_goalkeeper(self):
        self.assertEqual(self._pos(self._raw_with_string_pos('goalkeeper')), 'TW')

    def test_gk_attr_fallback(self):
        """Kein Positionsfeld → GK-Attribut-Fallback → TW."""
        raw = {
            'info': {},
            'attributes': {'gkreflexes': 85, 'gkdiving': 82},
        }
        self.assertEqual(self._pos(raw), 'TW')

    def test_unknown_position_falls_back_to_st(self):
        """Unbekannte Position → ST."""
        raw = {'info': {'preferredposition': {'label': 'Unknown Exotic Role'}}}
        self.assertEqual(self._pos(raw), 'ST')

    def test_no_position_field_falls_back_to_st(self):
        """Kein Positionsfeld, keine GK-Attribute → ST."""
        raw = {'info': {}, 'attributes': {}}
        self.assertEqual(self._pos(raw), 'ST')

    def test_returns_raw_label_for_debugging(self):
        """Tuple-Rückgabe: raw_label ist der unverarbeitete CMT-String."""
        from game.cmt_profile_service import _cmt_position_to_ws
        _, raw_label = _cmt_position_to_ws(
            self._raw_with_shortlabel('CDM', 'Centre Defensive Midfield')
        )
        self.assertEqual(raw_label, 'CDM')

    def test_mainposition_used_when_preferredposition_missing(self):
        """mainposition als Fallback wenn preferredposition nicht gesetzt."""
        raw = {'info': {'mainposition': {'shortlabel': 'ST', 'label': 'Striker'}}}
        self.assertEqual(self._pos(raw), 'ST')


# ── WS-Club-Auflösung ────────────────────────────────────────────────────────

class WsClubResolveTest(TestCase):
    """_resolve_ws_club löst WS-Club per Name auf; numerische IDs werden ignoriert."""

    def setUp(self):
        league = _make_league()
        self.club = _make_club(league, name='FC Bayern München')
        _make_cmt_source()

    def _resolve(self, cmt_team_id, cmt_team_name, db_slug='26062400'):
        from django.core.management import BaseCommand
        from game.management.commands.import_cmtracker import Command
        cmd = Command()
        return cmd._resolve_ws_club(cmt_team_id, db_slug, cmt_team_name)

    def test_name_match_via_longest_word(self):
        """'FC Bayern München' → FC Bayern München (längster Keyword-Match)."""
        result = self._resolve('21', 'FC Bayern München')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_partial_name_match(self):
        """'Bayern' allein reicht aus."""
        result = self._resolve('21', 'Bayern')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_numeric_cmt_team_name_returns_none(self):
        """Rein numerischer cmt_team_name (= rohe ID) findet keinen Club."""
        result = self._resolve('21', '21')
        self.assertIsNone(result)

    def test_empty_name_returns_none(self):
        result = self._resolve('21', '')
        self.assertIsNone(result)

    def test_nonexistent_name_returns_none(self):
        result = self._resolve('99', 'Club That Does Not Exist FC')
        self.assertIsNone(result)

    def test_external_id_lookup_takes_priority(self):
        """ClubExternalId-Eintrag schlägt Name-Fallback (anderer Club)."""
        from game.models import ClubExternalId, DataSource
        league = _make_league()
        other_club = _make_club(league, name='Borussia Dortmund')
        cmt_source = DataSource.objects.get(code='CMTRACKER')
        ClubExternalId.objects.create(
            club=other_club,
            source=cmt_source,
            external_id='21',
            db_slug='26062400',
        )
        result = self._resolve('21', 'FC Bayern München')
        self.assertEqual(result.pk, other_club.pk)


# ── Safety-Guard ─────────────────────────────────────────────────────────────

class SafetyGuardAutoCreateTest(TestCase):
    """Auto-Create bricht ab wenn WS-Club nicht aufgelöst werden kann (kein dry-run)."""

    def setUp(self):
        _make_cmt_source()
        _make_league()

    def _run_handle_with_mocked_client(self, dry_run=False):
        """Ruft handle() mit einem vollständig gemockten CMT-Client auf."""
        from game.management.commands.import_cmtracker import Command

        fake_player = {
            'info': {
                'playerid': '99999',
                'name': {'firstname': 'Test', 'lastname': 'Player', 'knownas': ''},
                'overallrating': 70,
                'potential': 75,
                'birthdate': '1999-01-01',
                'teams': {
                    'club_team': {'name': 'FC Unbekannt XYZ'},
                    'loan_team': {'name': ''},
                },
            },
            'attributes': {},
            'card_attrs': {},
        }
        mock_client = mock.MagicMock()
        mock_client.find_team_id.return_value = '21'
        mock_client.find_team_name.return_value = 'FC Unbekannt XYZ'
        mock_client.iter_players.return_value = iter([fake_player])

        mock_result = {
            'fatal_error': None,
            'stats': {'new': 0, 'updated': 0, 'unchanged': 0,
                      'unmatched': 0, 'error': 0},
            'row_results': [
                {
                    'action': 'unmatched',
                    'unmatch_reason': 'not_in_ws',
                    'sofifa_id': '99999',
                    'line_no': 1,
                }
            ],
        }

        with mock.patch(
            'game.management.commands.import_cmtracker.CmtrackerClient',
            return_value=mock_client,
        ), mock.patch(
            'game.management.commands.import_cmtracker.run_sofifa_import',
            return_value=mock_result,
        ), mock.patch(
            'game.management.commands.import_cmtracker.players_to_csv',
            return_value='',
        ):
            cmd = Command()
            cmd.stdout = StringIO()
            cmd.stderr = StringIO()
            cmd.style = mock.MagicMock()
            cmd.style.WARNING = lambda s: s
            cmd.style.SUCCESS = lambda s: s
            cmd.style.ERROR   = lambda s: s
            opts = {
                'db': '26062400',
                'team': '21',
                'league': None,
                'min_overall': None,
                'limit': 100,
                'max_pages': None,
                'sandbox': False,
                'dry_run': dry_run,
                'profiles': False,
                'auto_create': True,
                'skip_recalculate': True,
                'list_dbs': False,
                'list_filters': False,
                'probe_players': False,
            }
            cmd.handle(**opts)

    def test_unresolved_club_raises_command_error(self):
        """Kein WS-Club → CommandError im Live-Modus."""
        with self.assertRaises(CommandError) as ctx:
            self._run_handle_with_mocked_client(dry_run=False)
        self.assertIn('kein WS-Club', str(ctx.exception))

    def test_unresolved_club_dry_run_does_not_raise(self):
        """Kein WS-Club → kein Fehler im Dry-Run (Vorschau ist erlaubt)."""
        try:
            self._run_handle_with_mocked_client(dry_run=True)
        except CommandError as exc:
            self.fail(f'Dry-Run darf keinen CommandError werfen, aber: {exc}')
