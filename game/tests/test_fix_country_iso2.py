"""Tests für den Audit-/Korrektur-Command ``fix_country_iso2``."""

from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from game.management.commands.fix_country_iso2 import (
    is_valid_iso2,
    normalize_iso2,
)
from game.models import CountryNetwork


def _insert_raw(iso2, name):
    """Fügt eine Zeile per Raw-SQL ein, um die save()-Normalisierung zu umgehen."""
    with connection.cursor() as c:
        c.execute(
            "INSERT INTO game_countrynetwork "
            "(iso2, name, continent, region, community_points, activity_points, "
            "is_paused, created_at, updated_at) "
            "VALUES (%s, %s, '', '', 0, 0, false, now(), now()) RETURNING id",
            [iso2, name],
        )
        return c.fetchone()[0]


class NormalizeIso2UnitTests(TestCase):
    def test_lowercase_is_normalized(self):
        self.assertEqual(normalize_iso2('de'), 'DE')

    def test_surrounding_spaces_are_stripped(self):
        self.assertEqual(normalize_iso2(' fr '), 'FR')

    def test_already_valid_passes_through(self):
        self.assertEqual(normalize_iso2('GB'), 'GB')

    def test_wrong_length_is_unfixable(self):
        self.assertIsNone(normalize_iso2('X'))
        self.assertIsNone(normalize_iso2('USA'))

    def test_digits_and_symbols_are_unfixable(self):
        self.assertIsNone(normalize_iso2('D1'))
        self.assertIsNone(normalize_iso2('!!'))

    def test_non_ascii_is_unfixable(self):
        # 'ß'.upper() == 'SS' – darf NICHT als korrigierbar gelten.
        self.assertIsNone(normalize_iso2('ß'))
        self.assertIsNone(normalize_iso2('Ün'))
        self.assertIsNone(normalize_iso2('Ñ'))

    def test_is_valid_iso2(self):
        self.assertTrue(is_valid_iso2('DE'))
        self.assertFalse(is_valid_iso2('de'))
        self.assertFalse(is_valid_iso2('D'))
        self.assertFalse(is_valid_iso2('DEU'))
        self.assertFalse(is_valid_iso2('Ñ'))


class FixCountryIso2CommandTests(TestCase):
    def test_dry_run_does_not_change_data(self):
        _insert_raw('de', 'Testland Lower')
        out = StringIO()
        call_command('fix_country_iso2', stdout=out, stderr=out)
        # Nicht geschrieben.
        self.assertTrue(CountryNetwork.objects.filter(iso2='de').exists())
        self.assertFalse(CountryNetwork.objects.filter(iso2='DE').exists())
        self.assertIn('Dry-Run', out.getvalue())

    def test_apply_corrects_lowercase(self):
        _insert_raw('de', 'Testland Lower')
        out = StringIO()
        call_command('fix_country_iso2', '--apply', stdout=out, stderr=out)
        self.assertTrue(CountryNetwork.objects.filter(iso2='DE').exists())
        self.assertFalse(CountryNetwork.objects.filter(iso2='de').exists())

    def test_wrong_length_reported_not_changed(self):
        _insert_raw('X', 'Testland Short')
        out = StringIO()
        call_command('fix_country_iso2', '--apply', stdout=out, stderr=out)
        # Unverändert + als manuell gemeldet.
        self.assertTrue(CountryNetwork.objects.filter(iso2='X').exists())
        self.assertIn('manuell', out.getvalue())

    def test_non_ascii_reported_not_changed(self):
        _insert_raw('ß', 'Testland NonAscii')
        out = StringIO()
        call_command('fix_country_iso2', '--apply', stdout=out, stderr=out)
        self.assertTrue(CountryNetwork.objects.filter(iso2='ß').exists())
        self.assertFalse(CountryNetwork.objects.filter(iso2='SS').exists())
        self.assertIn('manuell', out.getvalue())

    def test_collision_with_existing_is_reported(self):
        CountryNetwork.objects.create(iso2='DE', name='Deutschland')
        _insert_raw('de', 'Testland Lower Dup')
        out = StringIO()
        call_command('fix_country_iso2', '--apply', stdout=out, stderr=out)
        # Kollidierende Kleinschreibung darf den vorhandenen DE nicht überschreiben.
        self.assertTrue(CountryNetwork.objects.filter(iso2='de').exists())
        self.assertEqual(CountryNetwork.objects.filter(iso2='DE').count(), 1)
        self.assertIn('kollidiert', out.getvalue())

    def test_all_valid_reports_nothing_to_do(self):
        CountryNetwork.objects.create(iso2='DE', name='Deutschland')
        out = StringIO()
        call_command('fix_country_iso2', stdout=out, stderr=out)
        self.assertIn('bereits gültig', out.getvalue())
