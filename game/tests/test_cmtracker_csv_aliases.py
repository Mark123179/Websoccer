"""Tests für die CMTracker-CSV-Header-Akzeptanz.

Nach der Quellen-Konsolidierung sind ``cmtracker_*`` die bevorzugten (kanonischen)
CSV-Header; die alten ``sofifa_*``-Header bleiben als rückwärtskompatibler Alias
erhalten. Interne Schlüssel/Feldnamen (``sofifa_id``, ``sofifa_ratings``,
DataSource-Code) ändern sich dadurch NICHT.
"""
from django.test import SimpleTestCase

from game.club_import.import_ready_csv import row_to_normalized
from game.sofifa_import import COLUMN_ALIASES, normalize_header


def _base_row(**extra):
    row = {
        'display_name': 'Test Spieler',
        'first_name': 'Test',
        'last_name': 'Spieler',
        'hp_positions': 'ST',
        'np_positions': '',
    }
    row.update(extra)
    return row


class ImportReadyCmtrackerHeaderTests(SimpleTestCase):
    """``row_to_normalized`` akzeptiert cmtracker_*-Spalten gleichwertig."""

    def test_cmtracker_columns_parse(self):
        row = _base_row(
            cmtracker_id='202126',
            cmtracker_url='https://cmtracker.net/player/202126',
            cmtracker_rating='90',
            cmtracker_potential='91',
            cmtracker_pace='95',
        )
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['sofifa_id'], '202126')
        self.assertEqual(
            nd['sofifa_profile_url'], 'https://cmtracker.net/player/202126'
        )
        self.assertIsNotNone(nd['sofifa_ratings'])
        self.assertEqual(nd['sofifa_ratings']['rating'], 90)
        self.assertEqual(nd['sofifa_ratings']['potential'], 91)
        self.assertEqual(nd['sofifa_ratings']['attrs']['tempo'], 95)
        self.assertEqual(
            nd['sofifa_ratings']['source_url'],
            'https://cmtracker.net/player/202126',
        )

    def test_legacy_sofifa_columns_still_parse(self):
        row = _base_row(
            sofifa_id='202126',
            sofifa_url='https://sofifa.com/player/202126',
            sofifa_rating='90',
            sofifa_pace='95',
        )
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['sofifa_id'], '202126')
        self.assertEqual(nd['sofifa_ratings']['rating'], 90)
        self.assertEqual(nd['sofifa_ratings']['attrs']['tempo'], 95)

    def test_cmtracker_takes_precedence_over_sofifa(self):
        row = _base_row(
            cmtracker_id='111', sofifa_id='999',
            cmtracker_rating='90', sofifa_rating='70',
            cmtracker_pace='95', sofifa_pace='40',
        )
        nd, _ = row_to_normalized(row)
        self.assertEqual(nd['sofifa_id'], '111')
        self.assertEqual(nd['sofifa_ratings']['rating'], 90)
        self.assertEqual(nd['sofifa_ratings']['attrs']['tempo'], 95)


class SofifaImportCmtrackerAliasTests(SimpleTestCase):
    """Der eigenständige Importer akzeptiert cmtracker_id/cmtracker_url als Alias."""

    def test_cmtracker_identity_aliases_resolve(self):
        self.assertEqual(
            COLUMN_ALIASES[normalize_header('cmtracker_id')], 'sofifa_id'
        )
        self.assertEqual(
            COLUMN_ALIASES[normalize_header('cmtracker')], 'sofifa_id'
        )
        self.assertEqual(
            COLUMN_ALIASES[normalize_header('cmtracker_url')], 'profile_url'
        )

    def test_legacy_sofifa_aliases_still_resolve(self):
        self.assertEqual(
            COLUMN_ALIASES[normalize_header('sofifa_id')], 'sofifa_id'
        )
        self.assertEqual(
            COLUMN_ALIASES[normalize_header('sofifa_url')], 'profile_url'
        )
