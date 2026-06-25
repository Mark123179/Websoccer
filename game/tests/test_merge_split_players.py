"""Zusammenführen geteilter Spieler-Identitäten (merge_split_players).

Hintergrund: Beim HSV-Import (Task #542) existierte derselbe Spieler als ZWEI
Datensätze — einer mit ``fm_inside_id`` ohne ``transfermarkt_id``, der andere
umgekehrt. Der Command findet solche sich ergänzenden Paare (gleicher Name +
Geburtsdatum, disjunkte IDs) und führt sie zusammen.
"""

from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from game.models import (
    Club,
    DataSource,
    League,
    Player,
    PlayerEditLog,
    PlayerExternalId,
    PlayerSourceRating,
)


class MergeSplitPlayersTests(TestCase):
    def setUp(self):
        league = League.objects.create(name='Testliga', country='Deutschland')
        self.hsv = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            budget=Decimal('1000000.00'), league=league)
        self.sofifa, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_CMTRACKER, defaults={'name': 'CMTracker'})

    def _player(self, first, last, dob, **extra):
        defaults = dict(
            first_name=first, last_name=last, age=25, position='ST',
            main_position_1='ST', market_value=Decimal('1000000.00'),
            date_of_birth=dob)
        defaults.update(extra)
        return Player.objects.create(**defaults)

    def _run(self, *args):
        out = StringIO()
        call_command('merge_split_players', *args, stdout=out, stderr=out)
        return out.getvalue()

    # ── Erkennung & Dry-Run ──────────────────────────────────────────────────
    def test_dry_run_lists_pair_without_changes(self):
        a = self._player('Alexander', 'Røssing-Lelesiit', date(2005, 1, 1),
                         fm_inside_id=111, club=self.hsv)
        b = self._player('Alexander', 'Røssing-Lelesiit', date(2005, 1, 1),
                         transfermarkt_id=222)

        output = self._run()  # Dry-Run (Default)

        self.assertIn('geteilte Identität', output)
        self.assertIn('Dry-Run', output)
        # Keine Änderungen.
        self.assertEqual(Player.objects.count(), 2)
        self.assertTrue(Player.objects.filter(pk=a.pk).exists())
        self.assertTrue(Player.objects.filter(pk=b.pk).exists())

    # ── Merge: kanonischer Datensatz erhält beide IDs, Zwilling entfernt ─────
    def test_apply_merges_complementary_ids(self):
        # a hat mehr abhängige Daten (Verein) → wird kanonisch.
        a = self._player('Alexander', 'Røssing-Lelesiit', date(2005, 1, 1),
                         fm_inside_id=111, club=self.hsv)
        b = self._player('Alexander', 'Røssing-Lelesiit', date(2005, 1, 1),
                         transfermarkt_id=222)

        self._run('--apply')

        self.assertEqual(Player.objects.count(), 1)
        self.assertFalse(Player.objects.filter(pk=b.pk).exists())
        a.refresh_from_db()
        self.assertEqual(a.fm_inside_id, 111)
        self.assertEqual(a.transfermarkt_id, 222)
        # Merge ist dokumentiert.
        self.assertTrue(PlayerEditLog.objects.filter(
            player=a, category=PlayerEditLog.CATEGORY_SYSTEM,
            summary__icontains='Geteilte Identität').exists())

    # ── Abhängige Daten des Zwillings werden umgehängt ───────────────────────
    def test_dependent_rows_moved_to_canonical(self):
        a = self._player('Test', 'Spieler', date(2000, 6, 6),
                         fm_inside_id=300, club=self.hsv)
        b = self._player('Test', 'Spieler', date(2000, 6, 6),
                         transfermarkt_id=400)
        # a soll kanonisch sein → mehr abhängige Daten geben (3 Edit-Logs).
        for _ in range(3):
            PlayerEditLog.objects.create(
                player=a, category=PlayerEditLog.CATEGORY_SYSTEM, summary='x')
        # Quell-Rating und externe ID hängen am Zwilling b und müssen wandern.
        PlayerSourceRating.objects.create(
            player=b, source=PlayerSourceRating.SOURCE_CMTRACKER, rating=75)
        PlayerExternalId.objects.create(
            player=b, source=self.sofifa, external_id='99999')

        self._run('--apply')

        a.refresh_from_db()
        self.assertEqual(Player.objects.count(), 1)
        self.assertTrue(PlayerSourceRating.objects.filter(
            player=a, source=PlayerSourceRating.SOURCE_CMTRACKER).exists())
        self.assertTrue(PlayerExternalId.objects.filter(
            player=a, external_id='99999').exists())

    # ── Kollision: kanonische Zeile bleibt, Zwillingszeile wird verworfen ────
    def test_conflicting_dependent_row_keeps_canonical(self):
        a = self._player('Konflikt', 'Spieler', date(1998, 3, 3),
                         fm_inside_id=500, club=self.hsv)
        b = self._player('Konflikt', 'Spieler', date(1998, 3, 3),
                         transfermarkt_id=600)
        # Beide haben ein CMTracker-Rating → (player, source) kollidiert beim Umhängen.
        PlayerSourceRating.objects.create(
            player=a, source=PlayerSourceRating.SOURCE_CMTRACKER, rating=70)
        PlayerSourceRating.objects.create(
            player=b, source=PlayerSourceRating.SOURCE_CMTRACKER, rating=88)

        self._run('--apply')

        a.refresh_from_db()
        ratings = PlayerSourceRating.objects.filter(
            player=a, source=PlayerSourceRating.SOURCE_CMTRACKER)
        self.assertEqual(ratings.count(), 1)
        self.assertEqual(ratings.first().rating, 70)  # kanonische Zeile bleibt

    # ── Kein Merge bei konkurrierender ID-Art (verschiedene Personen) ────────
    def test_no_merge_when_same_id_kind_on_both(self):
        self._player('Doppel', 'Name', date(1995, 5, 5), fm_inside_id=10)
        self._player('Doppel', 'Name', date(1995, 5, 5), fm_inside_id=11)

        self._run('--apply')

        self.assertEqual(Player.objects.count(), 2)

    # ── Kein Merge bei reiner Namensdublette ohne ergänzende IDs ─────────────
    def test_no_merge_without_complementary_ids(self):
        # b trägt keine externe ID → keine "geteilte Identität".
        self._player('Ohne', 'Ids', date(1990, 9, 9), fm_inside_id=20)
        self._player('Ohne', 'Ids', date(1990, 9, 9))

        self._run('--apply')

        self.assertEqual(Player.objects.count(), 2)

    # ── Mehrdeutige Gruppe (>2) wird übersprungen ────────────────────────────
    def test_ambiguous_group_skipped(self):
        self._player('Drei', 'Linge', date(1992, 2, 2), fm_inside_id=30)
        self._player('Drei', 'Linge', date(1992, 2, 2), transfermarkt_id=31)
        self._player('Drei', 'Linge', date(1992, 2, 2), api_football_id=32)

        output = self._run('--apply')

        self.assertIn('mehrdeutige', output.lower())
        self.assertEqual(Player.objects.count(), 3)

    # ── Verschiedene Geburtsdaten → kein Merge ───────────────────────────────
    def test_no_merge_on_different_dob(self):
        self._player('Gleich', 'Name', date(2001, 1, 1), fm_inside_id=40)
        self._player('Gleich', 'Name', date(2002, 2, 2), transfermarkt_id=41)

        self._run('--apply')

        self.assertEqual(Player.objects.count(), 2)
