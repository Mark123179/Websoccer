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


class BorussiaMgladbachResolveTest(TestCase):
    """Alias-Lookup + Eindeutigkeitsprüfung verhindert Borussia-Verwechslung.

    Reproduziert den Bug: team_id=23 / CMT-Name "Borussia M'gladbach" wurde
    fälschlich auf Borussia Dortmund aufgelöst, weil Token "Borussia"
    mehrdeutig war und icontains den DB-ersten Treffer (BVB) zurückgab.
    """

    def setUp(self):
        league = _make_league()
        self.bvb = _make_club(league, name='Borussia Dortmund')
        self.bmg = _make_club(league, name='Borussia Mönchengladbach')
        _make_cmt_source()

    def _resolve(self, cmt_team_id, cmt_team_name, db_slug='26062400'):
        from game.management.commands.import_cmtracker import Command
        return Command()._resolve_ws_club(cmt_team_id, db_slug, cmt_team_name)

    # ── Kern: Alias schlägt mehrdeutigen Token-Match ──────────────────────

    def test_mgladbach_apostrophe_resolves_to_bmg(self):
        """CMT-Name "Borussia M'gladbach" → Borussia Mönchengladbach (nicht BVB)."""
        result = self._resolve('23', "Borussia M'gladbach")
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.bmg.pk,
                         f'Erwartet BMG ({self.bmg.pk}), bekam {result}')

    def test_mgladbach_short_alias_resolves_to_bmg(self):
        """Alias "M'gladbach" allein → Borussia Mönchengladbach."""
        result = self._resolve('23', "M'gladbach")
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.bmg.pk)

    def test_bor_mgladbach_alias_resolves_to_bmg(self):
        """Alias "Bor. M'gladbach" → Borussia Mönchengladbach."""
        result = self._resolve('23', "Bor. M'gladbach")
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.bmg.pk)

    def test_borussia_alone_returns_none_when_ambiguous(self):
        """Token "Borussia" allein → None (mehrdeutig: BVB + BMG vorhanden)."""
        result = self._resolve('23', 'Borussia')
        self.assertIsNone(result,
                          'Mehrdeutiger Token "Borussia" darf keinen Club liefern.')

    def test_bvb_still_resolves_correctly(self):
        """BVB-Name matcht weiterhin korrekt auf Borussia Dortmund."""
        result = self._resolve('9', 'Borussia Dortmund')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.bvb.pk)

    def test_borussia_dortmund_not_returned_for_mgladbach(self):
        """Sanity-Check: BVB darf beim M'gladbach-Alias nie zurückkommen."""
        result = self._resolve('23', "Borussia M'gladbach")
        if result is not None:
            self.assertNotEqual(result.pk, self.bvb.pk,
                                'BVB darf für "Borussia M\'gladbach" nicht matchen.')


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


# ── RB Leipzig Alias-Tests ────────────────────────────────────────────────────

class RbLeipzigAliasResolveTest(TestCase):
    """CMT-Sonderschreibweisen für RB Leipzig werden korrekt aufgelöst.

    Hintergrund: CMT verwendet teils den eingetragenen Vereinsnamen
    "RasenBallsport Leipzig" statt der Kurzform "RB Leipzig". Auch
    "Red Bull Leipzig" taucht in älteren DB-Exporten auf.
    """

    def setUp(self):
        league = _make_league()
        self.club = _make_club(league, name='RB Leipzig')
        _make_cmt_source()

    def _resolve(self, cmt_team_name, cmt_team_id='35'):
        from game.management.commands.import_cmtracker import Command
        return Command()._resolve_ws_club(cmt_team_id, '26062400', cmt_team_name)

    def test_rasenballsport_leipzig_resolves(self):
        """'RasenBallsport Leipzig' → RB Leipzig."""
        result = self._resolve('RasenBallsport Leipzig')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_rb_leipzig_lowercase_resolves(self):
        """'rb leipzig' (Kleinschreibung) → RB Leipzig."""
        result = self._resolve('rb leipzig')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_red_bull_leipzig_resolves(self):
        """'Red Bull Leipzig' → RB Leipzig."""
        result = self._resolve('Red Bull Leipzig')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_rbl_abbreviation_resolves(self):
        """Abkürzung 'RBL' → RB Leipzig."""
        result = self._resolve('RBL')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)


# ── 1. FC Union Berlin Alias-Tests ───────────────────────────────────────────

class UnionBerlinAliasResolveTest(TestCase):
    """CMT-Sonderschreibweisen für 1. FC Union Berlin werden korrekt aufgelöst.

    Hintergrund: 'berlin' als Token wäre bei Anwesenheit von Hertha BSC Berlin
    mehrdeutig → Alias-Lookup schlägt Token-Match und verhindert Verwechslung.
    """

    def setUp(self):
        league = _make_league()
        self.union = _make_club(league, name='1. FC Union Berlin')
        self.hertha = _make_club(league, name='Hertha BSC Berlin')
        _make_cmt_source()

    def _resolve(self, cmt_team_name, cmt_team_id='28'):
        from game.management.commands.import_cmtracker import Command
        return Command()._resolve_ws_club(cmt_team_id, '26062400', cmt_team_name)

    def test_one_fc_union_berlin_resolves(self):
        """'1. FC Union Berlin' → 1. FC Union Berlin (nicht Hertha)."""
        result = self._resolve('1. FC Union Berlin')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.union.pk)

    def test_union_berlin_resolves(self):
        """'Union Berlin' → 1. FC Union Berlin."""
        result = self._resolve('Union Berlin')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.union.pk)

    def test_fc_union_berlin_resolves(self):
        """'FC Union Berlin' → 1. FC Union Berlin."""
        result = self._resolve('FC Union Berlin')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.union.pk)

    def test_berlin_alone_ambiguous_returns_none(self):
        """'Berlin' allein → None (Hertha + Union = mehrdeutig)."""
        result = self._resolve('Berlin')
        self.assertIsNone(result,
                          '"Berlin" allein darf keinen Club liefern (mehrdeutig).')

    def test_hertha_not_returned_for_union_alias(self):
        """Hertha darf bei Union-Aliases nie zurückkommen."""
        for alias in ('1. FC Union Berlin', 'Union Berlin', 'FC Union Berlin'):
            with self.subTest(alias=alias):
                result = self._resolve(alias)
                if result is not None:
                    self.assertNotEqual(result.pk, self.hertha.pk,
                                        f'Hertha darf für "{alias}" nicht matchen.')


# ── FC St. Pauli Alias-Tests ──────────────────────────────────────────────────

class StPauliAliasResolveTest(TestCase):
    """CMT-Sonderschreibweisen für FC St. Pauli werden korrekt aufgelöst.

    Hintergrund: CMT hängt die Gründungszahl 1910 an oder lässt "FC" weg.
    Da "St." auf 2 Zeichen bereinigt wird und unter der Mindestlänge 4 liegt,
    kann der Token-Match nur über "Pauli" oder "1910" gehen — Alias ist sicherer.
    """

    def setUp(self):
        league = _make_league()
        self.club = _make_club(league, name='FC St. Pauli')
        _make_cmt_source()

    def _resolve(self, cmt_team_name, cmt_team_id='65'):
        from game.management.commands.import_cmtracker import Command
        return Command()._resolve_ws_club(cmt_team_id, '26062400', cmt_team_name)

    def test_fc_st_pauli_1910_resolves(self):
        """'FC St. Pauli 1910' → FC St. Pauli."""
        result = self._resolve('FC St. Pauli 1910')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_st_pauli_1910_resolves(self):
        """'St. Pauli 1910' → FC St. Pauli."""
        result = self._resolve('St. Pauli 1910')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_fc_st_pauli_resolves(self):
        """'FC St. Pauli' (ohne Jahreszahl) → FC St. Pauli."""
        result = self._resolve('FC St. Pauli')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)

    def test_st_pauli_short_resolves(self):
        """'St. Pauli' (Kurzform) → FC St. Pauli."""
        result = self._resolve('St. Pauli')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.club.pk)


# ── Weitere Bundesliga-Alias-Tests ────────────────────────────────────────────

class WeitereAliasResolveTest(TestCase):
    """Alias-Lookups für weitere Bundesliga-Clubs mit CMT-Sonderschreibweisen.

    Jede setUp-Methode ist per-Klasse geteilt; einzelne Clubs werden als
    Fixtures erzeugt und jeder Alias mit genau einem Test abgedeckt.
    """

    def setUp(self):
        league = _make_league()
        self.hoffenheim = _make_club(league, name='TSG Hoffenheim')
        self.leverkusen = _make_club(league, name='Bayer Leverkusen')
        self.mainz      = _make_club(league, name='1. FSV Mainz 05')
        self.heidenheim = _make_club(league, name='1. FC Heidenheim 1846')
        self.koeln      = _make_club(league, name='1. FC Köln')
        self.hsv        = _make_club(league, name='Hamburger SV')
        self.paderborn  = _make_club(league, name='SC Paderborn')
        self.kiel       = _make_club(league, name='Holstein Kiel')
        _make_cmt_source()

    def _resolve(self, cmt_team_name, cmt_team_id='99'):
        from game.management.commands.import_cmtracker import Command
        return Command()._resolve_ws_club(cmt_team_id, '26062400', cmt_team_name)

    # Hoffenheim
    def test_tsg_1899_hoffenheim_resolves(self):
        result = self._resolve('TSG 1899 Hoffenheim')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.hoffenheim.pk)

    def test_1899_hoffenheim_resolves(self):
        result = self._resolve('1899 Hoffenheim')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.hoffenheim.pk)

    def test_tsg_hoffenheim_resolves(self):
        result = self._resolve('TSG Hoffenheim')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.hoffenheim.pk)

    # Leverkusen
    def test_bayer_04_leverkusen_resolves(self):
        result = self._resolve('Bayer 04 Leverkusen')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.leverkusen.pk)

    # Mainz
    def test_1_fsv_mainz_05_resolves(self):
        result = self._resolve('1. FSV Mainz 05')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.mainz.pk)

    def test_fsv_mainz_05_resolves(self):
        result = self._resolve('FSV Mainz 05')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.mainz.pk)

    def test_mainz_05_resolves(self):
        result = self._resolve('Mainz 05')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.mainz.pk)

    # Heidenheim
    def test_1_fc_heidenheim_1846_resolves(self):
        result = self._resolve('1. FC Heidenheim 1846')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.heidenheim.pk)

    def test_fc_heidenheim_1846_resolves(self):
        result = self._resolve('FC Heidenheim 1846')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.heidenheim.pk)

    def test_heidenheim_1846_resolves(self):
        result = self._resolve('Heidenheim 1846')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.heidenheim.pk)

    # Köln
    def test_1_fc_koeln_ascii_resolves(self):
        """ASCII-Transliteration 'Koeln' (CMT-Export) → 1. FC Köln."""
        result = self._resolve('1. FC Koeln')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.koeln.pk)

    def test_1_fc_koeln_umlaut_resolves(self):
        """'1. FC Köln' (Umlaut-Variante) → 1. FC Köln."""
        result = self._resolve('1. FC Köln')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.koeln.pk)

    def test_fc_koeln_ascii_resolves(self):
        """'FC Koeln' (ohne Präfix) → 1. FC Köln."""
        result = self._resolve('FC Koeln')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.koeln.pk)

    # Hamburger SV
    def test_hamburger_sv_resolves(self):
        result = self._resolve('Hamburger SV')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.hsv.pk)

    def test_hsv_abbreviation_resolves(self):
        """Abkürzung 'HSV' → Hamburger SV."""
        result = self._resolve('HSV')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.hsv.pk)

    # SC Paderborn
    def test_sc_paderborn_07_resolves(self):
        result = self._resolve('SC Paderborn 07')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.paderborn.pk)

    def test_paderborn_07_resolves(self):
        result = self._resolve('Paderborn 07')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.paderborn.pk)

    # Holstein Kiel
    def test_holstein_kiel_resolves(self):
        result = self._resolve('Holstein Kiel')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.kiel.pk)

    def test_ksh_kiel_resolves(self):
        """'KSH Kiel' (seltene CMT-Abkürzung) → Holstein Kiel."""
        result = self._resolve('KSH Kiel')
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, self.kiel.pk)
