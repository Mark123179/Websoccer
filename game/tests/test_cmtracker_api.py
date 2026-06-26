"""Netzwerkfreie Tests fuer die cmtracker-API-Bruecke.

Prueft, dass cmtracker-Antworten korrekt nach CSV abgeflacht werden und dass
dieses CSV vom Live-Importer (``game.sofifa_import_service``) erkannt und
korrekt geparst wird — ohne echte API-Aufrufe (reines Mapping/Parsing).
"""

import csv
import io
from datetime import date

from django.test import SimpleTestCase

from game.cmtracker_api import (
    CSV_COLUMNS,
    CmtrackerClient,
    _cell,
    _dig,
    _extract_list,
    player_to_row,
    players_to_csv,
)
from game.sofifa_import_service import _build_header_map, _parse_row


SAMPLE_PLAYER = {
    'info': {
        'playerid': 74102,
        'name': {
            'knownas': 'Fabio Baldé',
            'firstname': 'Fabio',
            'lastname': 'Baldé',
        },
        'teams': {'club_team': {'name': 'Hamburger SV'}},
        'overallrating': 66,
        'potential': 78,
        'birthdate': '2005-07-20T00:00:00.000Z',
    },
    'card_attrs': {'pac': 83},
    'attributes': {
        'stamina': 54,
        'strength': 60,
        'ballcontrol': 64,
        'dribbling': 67,
        'shortpassing': 62,
        'crossing': 55,
        'finishing': 58,
        'headingaccuracy': 50,
        'standingtackle': 45,
        'marking': 44,
        'vision': 57,
        'penalties': 52,
        'freekickaccuracy': 48,
        'gkreflexes': 12,
        'gkhandling': 11,
        'gkpositioning': 13,
        'gkkicking': 14,
        'gkdiving': 10,
    },
}


class DigTests(SimpleTestCase):
    def test_nested(self):
        self.assertEqual(
            _dig(SAMPLE_PLAYER, 'info.name.knownas'), 'Fabio Baldé'
        )

    def test_flat_key(self):
        self.assertEqual(_dig({'info.playerid': 99}, 'info.playerid'), 99)

    def test_missing_path(self):
        self.assertIsNone(_dig(SAMPLE_PLAYER, 'info.foo.bar'))

    def test_non_dict(self):
        self.assertIsNone(_dig(None, 'a.b'))


class CellTests(SimpleTestCase):
    def test_none_to_empty(self):
        self.assertEqual(_cell(None), '')

    def test_bool_to_int_string(self):
        self.assertEqual(_cell(True), '1')
        self.assertEqual(_cell(False), '0')

    def test_int_to_string(self):
        self.assertEqual(_cell(66), '66')


class ExtractListTests(SimpleTestCase):
    def test_plain_list(self):
        self.assertEqual(_extract_list([1, 2]), [1, 2])

    def test_enveloped_dict(self):
        self.assertEqual(_extract_list({'data': [1]}), [1])
        self.assertEqual(_extract_list({'results': [2, 3]}), [2, 3])

    def test_unknown_shape(self):
        self.assertEqual(_extract_list({'foo': 1}), [])


class RowTests(SimpleTestCase):
    def test_row_length_matches_columns(self):
        row = player_to_row(SAMPLE_PLAYER)
        self.assertEqual(len(row), len(CSV_COLUMNS))

    def test_row_values(self):
        row = player_to_row(SAMPLE_PLAYER)
        self.assertEqual(row[CSV_COLUMNS.index('info.playerid')], '74102')
        self.assertEqual(
            row[CSV_COLUMNS.index('info.teams.club_team.name')],
            'Hamburger SV',
        )
        self.assertEqual(row[CSV_COLUMNS.index('card_attrs.pac')], '83')

    def test_csv_header_and_single_data_row(self):
        rows = list(csv.reader(io.StringIO(players_to_csv([SAMPLE_PLAYER]))))
        self.assertEqual(rows[0], CSV_COLUMNS)
        self.assertEqual(len(rows), 2)


class BridgeTests(SimpleTestCase):
    """Der Live-Importer muss das generierte CSV erkennen und parsen."""

    def setUp(self):
        rows = list(csv.reader(io.StringIO(players_to_csv([SAMPLE_PLAYER]))))
        self.header = rows[0]
        self.data = rows[1]
        self.header_map = _build_header_map(self.header)

    def test_core_fields_are_mapped(self):
        for key in ('sofifa_id', 'name', 'club', 'rating', 'potential', 'dob',
                    'tempo', 'ausdauer', 'kraft'):
            self.assertIn(key, self.header_map, f'{key!r} nicht gemappt')

    def test_parse_row_values(self):
        parsed = _parse_row(self.data, self.header_map)
        self.assertEqual(parsed['sofifa_id'], '74102')
        self.assertEqual(parsed['name'], 'Fabio Baldé')
        self.assertEqual(parsed['club'], 'Hamburger SV')
        self.assertEqual(parsed['rating'], 66)
        self.assertEqual(parsed['potential'], 78)
        self.assertEqual(parsed['dob'], date(2005, 7, 20))
        self.assertEqual(parsed['attrs']['tempo'], 83)
        self.assertEqual(parsed['attrs']['ausdauer'], 54)
        self.assertEqual(parsed['attrs']['kraft'], 60)

    def test_flat_payload_also_parses(self):
        """Auch eine bereits abgeflachte API-Antwort wird korrekt verarbeitet."""
        flat = {col: _dig(SAMPLE_PLAYER, col) for col in CSV_COLUMNS}
        rows = list(csv.reader(io.StringIO(players_to_csv([flat]))))
        parsed = _parse_row(rows[1], _build_header_map(rows[0]))
        self.assertEqual(parsed['sofifa_id'], '74102')
        self.assertEqual(parsed['rating'], 66)
        self.assertEqual(parsed['dob'], date(2005, 7, 20))


class IterPlayersRequestTests(SimpleTestCase):
    """Request-Konstruktion von iter_players ohne Netzwerk (``_get`` gemockt)."""

    def _client(self):
        return CmtrackerClient(
            api_key='test-key', base_url='https://example.test'
        )

    def test_sandbox_makes_one_paramfree_call(self):
        client = self._client()
        calls = []

        def fake_get(path, params=None):
            calls.append((path, params))
            return [{'info': {'playerid': 1}}, {'info': {'playerid': 2}}]

        client._get = fake_get
        out = list(client.iter_players(sandbox=True))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'players')
        self.assertIsNone(calls[0][1])  # keinerlei Query-Parameter
        self.assertEqual(len(out), 2)

    def test_sandbox_with_db_sends_only_db(self):
        client = self._client()
        calls = []

        def fake_get(path, params=None):
            calls.append((path, params))
            return [{'info': {'playerid': 9}}]

        client._get = fake_get
        list(client.iter_players(sandbox=True, db='26062400'))
        self.assertEqual(calls[0][1], {'db': '26062400'})

    def test_pagination_advances_and_stops_on_empty(self):
        client = self._client()
        pages = [
            [{'info': {'playerid': 1}}, {'info': {'playerid': 2}}],
            [{'info': {'playerid': 3}}],
            [],
        ]
        seen = []

        def fake_get(path, params=None):
            seen.append(params)
            return pages[params['page']]

        client._get = fake_get
        out = list(client.iter_players(db='26062400', limit=2))
        self.assertEqual([_dig(p, 'info.playerid') for p in out], [1, 2, 3])
        self.assertEqual([p['page'] for p in seen], [0, 1, 2])

    def test_pagination_stops_on_duplicate_first_id(self):
        client = self._client()

        def fake_get(path, params=None):
            # Server ignoriert ``page`` und liefert stets dieselbe erste ID.
            return [{'info': {'playerid': 7}}, {'info': {'playerid': 8}}]

        client._get = fake_get
        out = list(client.iter_players(db='26062400', limit=2, max_pages=10))
        self.assertEqual(len(out), 2)
