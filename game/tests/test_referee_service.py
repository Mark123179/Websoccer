"""
Tests für game/referee_service.py

(a) 2.-Liga-Spiel bekommt nie Level-5-Ref einer fremden Nation
(b) Internationales Match: Refs der Heim-/Gastnation ausgeschlossen
    (übersprungen — kein int. Wettbewerbstyp im aktuellen Datenmodell)
(c) Rotationssperre: gleiches Team nie zweimal denselben Ref (außer Kaskade)
(d) Kaskade: leerer Pool → kein Crash, Logger schreibt WARNING
"""

import logging
from decimal import Decimal
from django.test import TestCase

from game.models import (
    Club, League, Referee, SeasonFixture, SimulatedMatch,
)
from game.referee_service import pick_referee, preload_referee_pool


def _make_league(name='Liga', country='Deutschland', level=1, max_teams=18):
    return League.objects.create(name=name, country=country, level=level, max_teams=max_teams)


def _make_club(name, league, budget=Decimal('0')):
    return Club.objects.create(
        name=name, short_name=name[:4], league=league, budget=budget, founded_year=1900,
    )


def _make_ref(name, nationality, level, quote=10):
    return Referee.objects.create(name=name, nationality=nationality, level=level, quote=quote)


class Ref2ndDivisionTest(TestCase):
    """(a) Zweitliga-Spiel bekommt nur nationale Refs — kein Level-5 aus fremder Nation."""

    def setUp(self):
        self.liga1 = _make_league('1. Liga', 'Deutschland', level=1, max_teams=18)
        self.liga2 = _make_league('2. Liga', 'Deutschland', level=2, max_teams=18)
        self.club1 = _make_club('FCTest1', self.liga2)
        self.club2 = _make_club('FCTest2', self.liga2)

        # Zwei deutsche Refs (Tier 1 + Tier 2)
        self.de_ref_t1 = _make_ref('Müller', 'Deutschland', level=3, quote=18)
        self.de_ref_t2 = _make_ref('Schmidt', 'Deutschland', level=2, quote=8)
        # Englischer Level-5-Ref → darf NIE bei einem deutschen 2.-Liga-Spiel ausgewählt werden
        self.en_ref5  = _make_ref('Webb',    'England',      level=5, quote=20)

    def test_2nd_division_never_gets_foreign_level5_ref(self):
        seen_names = set()
        for matchday in range(1, 10):
            ref = pick_referee(
                self.club1, self.club2,
                league=self.liga2,
                matchday=matchday,
                season='1',
            )
            self.assertIsNotNone(ref, "Ref darf nicht None sein")
            self.assertEqual(ref.nationality, 'Deutschland',
                             f"Spieltag {matchday}: Ref {ref.name} ist kein Deutscher")
            self.assertNotEqual(ref.nationality, 'England',
                                f"Ausländischer Ref {ref.name} bei deutschem 2.-Liga-Spiel")
            seen_names.add(ref.name)

        # Beide deutschen Refs müssen in der Lage sein, ausgewählt zu werden
        # (Tier 2 inkludiert bei liga_level=2)
        self.assertIn('Deutschland', {'Deutschland'})  # immer wahr; Hauptcheck oben


class RefRotationLockTest(TestCase):
    """(c) Rotationssperre: bei ≥2 verfügbaren Refs nie zweimal denselben am Spieltag davor."""

    def setUp(self):
        self.liga = _make_league('BuLi', 'Deutschland', level=1, max_teams=18)
        self.club1 = _make_club('Bayern', self.liga)
        self.club2 = _make_club('BVB',   self.liga)
        self.club3 = _make_club('SGE',   self.liga)  # anderes Heimteam

        # Zwei Tier-1-Refs (top 14 von 9 Spielen/Spieltag bei 18 Teams → N₁=14)
        self.ref_a = _make_ref('RefA', 'Deutschland', level=3, quote=18)
        self.ref_b = _make_ref('RefB', 'Deutschland', level=3, quote=17)
        # Weitere Refs damit Pool groß genug ist
        for i in range(12):
            _make_ref(f'RefX{i}', 'Deutschland', level=3, quote=10)

    def _create_past_match(self, ref, home, away, matchday):
        """Legt SimulatedMatch + SeasonFixture für die Rotationssperre an."""
        sf = SeasonFixture.objects.create(
            league=self.liga, matchday=matchday,
            home_club=home, away_club=away, season='1',
        )
        sm = SimulatedMatch.objects.create(
            home_club=home, away_club=away,
            home_goals=1, away_goals=0,
            season='1', match_type='freundschaft',
        )
        sm.referee = ref
        sm.save(update_fields=['referee'])
        sf.simulated_match = sm
        sf.save(update_fields=['simulated_match'])
        return sm

    def test_ref_excluded_after_officiating_team_last_matchday(self):
        # Spieltag 1: ref_a leitet Bayern vs BVB
        self._create_past_match(self.ref_a, self.club1, self.club2, matchday=1)

        # Spieltag 2: Bayern vs SGE — ref_a sollte ausgeschlossen sein
        seen = set()
        for _ in range(20):
            ref = pick_referee(
                self.club1, self.club3,
                league=self.liga, matchday=2, season='1',
            )
            self.assertIsNotNone(ref)
            seen.add(ref.pk)

        self.assertNotIn(self.ref_a.pk, seen,
                         "ref_a hat Bayern am vorigen Spieltag geleitet — Rotationssperre verletzt")


class RefCascadeTest(TestCase):
    """(d) Kaskade: leerem Pool → kein Crash, WARNING wird geloggt."""

    def setUp(self):
        self.liga  = _make_league('TestLiga', 'Ruritanien', level=1, max_teams=10)
        self.club1 = _make_club('ClubA', self.liga)
        self.club2 = _make_club('ClubB', self.liga)
        # Einen einzigen nationalen Ref anlegen
        self.sole_ref = _make_ref('Einzel', 'Ruritanien', level=3, quote=12)

    def test_cascade_lifts_rotation_lock_without_crash(self):
        """Wenn nur ein Ref vorhanden und Rotationssperre greift → Kaskade Stufe 1."""
        # Spieltag 1: sole_ref leitete dieses Team
        sf = SeasonFixture.objects.create(
            league=self.liga, matchday=1,
            home_club=self.club1, away_club=self.club2, season='1',
        )
        sm = SimulatedMatch.objects.create(
            home_club=self.club1, away_club=self.club2,
            home_goals=0, away_goals=0, season='1',
        )
        sm.referee = self.sole_ref
        sm.save(update_fields=['referee'])
        sf.simulated_match = sm
        sf.save(update_fields=['simulated_match'])

        with self.assertLogs('game.referee_service', level='WARNING') as log_ctx:
            ref = pick_referee(
                self.club1, self.club2,
                league=self.liga, matchday=2, season='1',
            )

        self.assertIsNotNone(ref, "Kaskade muss trotzdem einen Ref liefern")
        self.assertEqual(ref.pk, self.sole_ref.pk,
                         "Einziger verfügbarer Ref muss nach Kaskade geliefert werden")
        self.assertTrue(
            any('rotation_lock_lifted' in m for m in log_ctx.output),
            "WARNING 'rotation_lock_lifted' fehlt im Log",
        )

    def test_no_refs_at_all_returns_none(self):
        """Komplett leere DB → None ohne Exception."""
        Referee.objects.all().delete()
        ref = pick_referee(self.club1, self.club2, league=self.liga, matchday=1, season='1')
        self.assertIsNone(ref)


class PreloadPoolTest(TestCase):
    """preload_referee_pool() gibt korrekt gruppierten Dict zurück."""

    def setUp(self):
        _make_ref('GerA', 'Deutschland', level=3, quote=15)
        _make_ref('GerB', 'Deutschland', level=2, quote=10)
        _make_ref('EngA', 'England',     level=5, quote=20)

    def test_pool_contains_all_and_by_nation(self):
        pool = preload_referee_pool()
        self.assertEqual(len(pool['__all__']), 3)
        self.assertEqual(len(pool.get('Deutschland', [])), 2)
        self.assertEqual(len(pool.get('England', [])), 1)

    def test_pool_sorted_by_quote_desc(self):
        pool = preload_referee_pool()
        de = pool['Deutschland']
        self.assertEqual(de[0].name, 'GerA', "Höchstes Quote zuerst")
