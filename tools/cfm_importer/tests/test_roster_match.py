"""Tests für die Name+Geburtsdatum-Zuordnung des Vereinskaders."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cfm_importer.roster_match import RosterMatcher  # noqa: E402


def _entry(fm_id, first, last, dob=''):
    return {
        'fm_inside_id': fm_id,
        'first_name': first,
        'last_name': last,
        'date_of_birth': dob,
    }


class RosterMatcherTests(unittest.TestCase):
    def test_match_by_name_and_dob(self):
        m = RosterMatcher([_entry(28049320, 'Harry', 'Kane', '1993-07-28')])
        self.assertEqual(m.match('Harry Kane', '28.07.1993'), 28049320)

    def test_match_ignores_accents_and_case(self):
        # "Vušković" -> "vuskovic": Diakritika werden auf beiden Seiten entfernt.
        m = RosterMatcher([_entry(111, 'Luka', 'Vušković', '2007-02-24')])
        self.assertEqual(m.match('LUKA VUSKOVIC', '2007-02-24'), 111)

    def test_unique_name_without_dob_falls_back(self):
        m = RosterMatcher([_entry(222, 'Joshua', 'Kimmich', '1995-02-08')])
        self.assertEqual(m.match('Joshua Kimmich', ''), 222)

    def test_ambiguous_name_without_dob_returns_none(self):
        m = RosterMatcher([
            _entry(1, 'Danny', 'Williams', '1989-03-08'),
            _entry(2, 'Danny', 'Williams', '1995-05-05'),
        ])
        self.assertIsNone(m.match('Danny Williams', ''))
        # Mit passendem Geburtsdatum wird es wieder eindeutig.
        self.assertEqual(m.match('Danny Williams', '1995-05-05'), 2)

    def test_same_name_same_dob_different_ids_returns_none(self):
        # Gleicher Name + gleiches Geburtsdatum, aber zwei verschiedene IDs →
        # niemals last-write-wins, immer None.
        m = RosterMatcher([
            _entry(10, 'Jens', 'Müller', '1990-06-01'),
            _entry(20, 'Jens', 'Müller', '1990-06-01'),
        ])
        self.assertIsNone(m.match('Jens Müller', '1990-06-01'))
        self.assertIsNone(m.match('Jens Müller', ''))

    def test_conflicting_dob_returns_none(self):
        m = RosterMatcher([_entry(333, 'Max', 'Mustermann', '1990-01-01')])
        self.assertIsNone(m.match('Max Mustermann', '2000-12-31'))

    def test_no_match_returns_none(self):
        m = RosterMatcher([_entry(444, 'A', 'B', '1990-01-01')])
        self.assertIsNone(m.match('Unbekannt Spieler', '1990-01-01'))

    def test_entries_without_fm_id_are_skipped(self):
        m = RosterMatcher([_entry(None, 'Ohne', 'Id', '1990-01-01')])
        self.assertEqual(len(m), 0)
        self.assertIsNone(m.match('Ohne Id', '1990-01-01'))

    def test_empty_roster(self):
        m = RosterMatcher([])
        self.assertEqual(len(m), 0)
        self.assertIsNone(m.match('Irgendwer', '1990-01-01'))


if __name__ == '__main__':
    unittest.main()
