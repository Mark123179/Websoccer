"""Tests für die Finance-Vollständigkeitsprüfung (Task #763).

Prüft check_finance_completeness() aus game.economy.integrity:
  - Lücken-Erkennung bei fehlendem Marker
  - Kein False-Positive bei vollständig gelaufenen Spieltagen
  - No-Header-Erkennung (Verein hat gar keinen Finanz-Lauf)
  - Heim/Auswärts-Unterscheidung: TICKET nur für Heimvereine Pflicht
  - Saison- / Liga- / Spieltagfilter funktionieren
"""
from decimal import Decimal

from django.test import TestCase

from game.economy.integrity import check_finance_completeness
from game.economy.matchday_run import (
    ALLE_RUN_TYPEN, RUN_TYP_HEADER, RUN_TYP_SPONSOR, RUN_TYP_TICKET,
)
from game.models import (
    Club, FinanceMatchdayRun, GameSeasonState, League, Player, SeasonFixture,
)


def _mk_league(name='FC-Liga'):
    return League.objects.create(name=name, country='Deutschland')


def _mk_club(name, league, budget='0.00'):
    return Club.objects.create(
        name=name, short_name=name[:3].upper(), founded_year=1900,
        budget=Decimal(budget), league=league,
    )


def _mk_fixture(league, home, away, matchday=1, saison='0', played=True):
    return SeasonFixture.objects.create(
        league=league, season=saison, matchday=matchday,
        home_club=home, away_club=away, is_played=played,
    )


def _set_markers(club, saison, spieltag, typen):
    """Setzt explizit die angegebenen Marker-Typen (inkl. Header wenn '' drin)."""
    for typ in typen:
        FinanceMatchdayRun.objects.get_or_create(
            club=club, saison=saison, spieltag=spieltag, typ=typ,
        )


def _set_all_markers(club, saison, spieltag):
    """Setzt alle 7 Marker (Header + 6 Typ-Marker) — vollständiger Lauf."""
    _set_markers(club, saison, spieltag, [''] + sorted(ALLE_RUN_TYPEN))


def _set_pflicht_alle(club, saison, spieltag):
    """Setzt die 5 Pflicht-Marker für Auswärtsvereine + Header."""
    _set_markers(club, saison, spieltag, ['', 'TV_SOCKEL', 'SPONSOR', 'GEHALT', 'STADION', 'BETRIEB'])


class CompletenessCheckBasicTests(TestCase):

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.liga = _mk_league()
        self.heim = _mk_club('FC Heim', self.liga)
        self.gast = _mk_club('FC Gast', self.liga)
        self.fixture = _mk_fixture(self.liga, self.heim, self.gast)

    def test_no_gaps_when_all_markers_present(self):
        """Vollständig gelaufener Spieltag → keine Lücken."""
        _set_all_markers(self.heim, '0', 1)
        _set_all_markers(self.gast, '0', 1)

        result = check_finance_completeness(saison='0')

        self.assertEqual(result['gaps'], [])
        self.assertEqual(result['checked_clubs'], 2)

    def test_away_club_without_ticket_marker_no_gap(self):
        """Auswärtsverein mit nur 5 Pflicht-Markern (kein TICKET) → keine Lücke.

        Auswärtsverein bucht keine Ticketeinnahmen — TICKET-Marker ist daher
        für Auswärtsteams nicht Pflicht. Historische Saison-0-Daten (Migration
        0137 TX-basiert) haben diesen Marker für Auswärtsteams nicht.
        """
        _set_all_markers(self.heim, '0', 1)
        _set_pflicht_alle(self.gast, '0', 1)   # kein TICKET-Marker für Auswärts

        result = check_finance_completeness(saison='0')

        self.assertEqual(result['gaps'], [], 'Kein False-Positive für Auswärts ohne TICKET')

    def test_home_club_missing_ticket_marker_is_gap(self):
        """Heimverein ohne TICKET-Marker → wird als Lücke gemeldet."""
        _set_all_markers(self.gast, '0', 1)
        # Heim nur mit Pflicht-Alle (kein TICKET).
        _set_pflicht_alle(self.heim, '0', 1)

        result = check_finance_completeness(saison='0')

        self.assertEqual(len(result['gaps']), 1)
        gap = result['gaps'][0]
        self.assertEqual(gap['club_id'], self.heim.pk)
        self.assertIn(RUN_TYP_TICKET, gap['missing'])
        self.assertTrue(gap['is_home'])
        self.assertFalse(gap['no_header'])

    def test_detects_missing_single_marker_all_clubs(self):
        """Ein allgemeiner Marker fehlt beim Auswärtsverein → wird gemeldet."""
        _set_all_markers(self.heim, '0', 1)
        # Gast ohne SPONSOR-Marker.
        _set_markers(self.gast, '0', 1, ['', 'TV_SOCKEL', 'TICKET', 'GEHALT', 'STADION', 'BETRIEB'])

        result = check_finance_completeness(saison='0')

        self.assertEqual(len(result['gaps']), 1)
        gap = result['gaps'][0]
        self.assertEqual(gap['club_id'], self.gast.pk)
        self.assertIn(RUN_TYP_SPONSOR, gap['missing'])
        self.assertFalse(gap['no_header'])
        self.assertFalse(gap['is_home'])

    def test_detects_no_header(self):
        """Verein ohne jeglichen Marker → no_header=True + Pflicht-Marker fehlen."""
        _set_all_markers(self.heim, '0', 1)
        # Gastverein hat gar keine Marker.

        result = check_finance_completeness(saison='0')

        self.assertEqual(len(result['gaps']), 1)
        gap = result['gaps'][0]
        self.assertEqual(gap['club_id'], self.gast.pk)
        self.assertTrue(gap['no_header'])
        # Auswärtsverein: Pflicht-Alle (5) fehlen, nicht TICKET (kein False-Positive).
        self.assertNotIn(RUN_TYP_TICKET, gap['missing'])
        self.assertEqual(len(gap['missing']), 5)  # TV, SPONSOR, GEHALT, STADION, BETRIEB

    def test_no_false_positive_for_unplayed_fixture(self):
        """Nicht gespielte Fixtures → kein Check (is_played=False → ignoriert)."""
        unplayed_liga = _mk_league('Liga2')
        h2 = _mk_club('FC A', unplayed_liga)
        g2 = _mk_club('FC B', unplayed_liga)
        _mk_fixture(unplayed_liga, h2, g2, played=False)

        result = check_finance_completeness(liga_id=unplayed_liga.pk)
        self.assertEqual(result['gaps'], [])
        self.assertEqual(result['checked_clubs'], 0)


class CompletenessCheckFilterTests(TestCase):

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.liga = _mk_league('Filter-Liga')
        self.heim = _mk_club('FC F-Heim', self.liga)
        self.gast = _mk_club('FC F-Gast', self.liga)
        _mk_fixture(self.liga, self.heim, self.gast, matchday=1, saison='0')
        # ST2: Rückspiel (Heim/Gast vertauscht)
        _mk_fixture(self.liga, self.gast, self.heim, matchday=2, saison='0')

        # Alle Marker für beide Spieltage setzen.
        for spieltag in (1, 2):
            _set_all_markers(self.heim, '0', spieltag)
            _set_all_markers(self.gast, '0', spieltag)

        # GEHALT-Marker bei ST2 Heim löschen.
        FinanceMatchdayRun.objects.filter(
            club=self.heim, saison='0', spieltag=2, typ='GEHALT',
        ).delete()

    def test_spieltag_filter_only_checks_target(self):
        """--spieltag 1 findet keine Lücke; ST2 hat eine aber wird nicht geprüft."""
        result = check_finance_completeness(saison='0', spieltag=1)
        self.assertEqual(result['gaps'], [])
        self.assertEqual(result['checked_clubs'], 2)

    def test_spieltag_filter_finds_gap(self):
        """--spieltag 2 findet die GEHALT-Lücke."""
        result = check_finance_completeness(saison='0', spieltag=2)
        self.assertEqual(len(result['gaps']), 1)
        self.assertEqual(result['gaps'][0]['club_id'], self.heim.pk)
        self.assertIn('GEHALT', result['gaps'][0]['missing'])

    def test_saison_filter_scopes_correctly(self):
        """Saison '1' existiert nicht → checked_clubs=0."""
        result = check_finance_completeness(saison='1', liga_id=self.liga.pk)
        self.assertEqual(result['checked_clubs'], 0)

    def test_liga_filter_scopes_correctly(self):
        """liga_id-Filter auf anderer Liga → 0 Ergebnisse."""
        other_liga = _mk_league('Andere Liga')
        result = check_finance_completeness(liga_id=other_liga.pk)
        self.assertEqual(result['checked_clubs'], 0)


class CompletenessCheckMultipleGapsTests(TestCase):
    """Mehrere Lücken auf einmal — Gesamtüberblick korrekt."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.liga = _mk_league('Multi-Liga')
        self.clubs = [_mk_club(f'FC {i}', self.liga) for i in range(4)]
        _mk_fixture(self.liga, self.clubs[0], self.clubs[1], matchday=1)
        _mk_fixture(self.liga, self.clubs[2], self.clubs[3], matchday=1)

    def test_all_missing_reported(self):
        """4 Vereine ohne Marker → 4 Lücken im Report."""
        result = check_finance_completeness(saison='0')
        self.assertEqual(len(result['gaps']), 4)
        self.assertEqual(result['checked_clubs'], 4)
        for gap in result['gaps']:
            self.assertTrue(gap['no_header'])

    def test_partial_coverage_leaves_right_gaps(self):
        """2 von 4 Vereinen korrekt → 2 Lücken für die anderen beiden."""
        _set_all_markers(self.clubs[0], '0', 1)
        _set_all_markers(self.clubs[1], '0', 1)

        result = check_finance_completeness(saison='0')
        self.assertEqual(len(result['gaps']), 2)
        gap_ids = {g['club_id'] for g in result['gaps']}
        self.assertEqual(gap_ids, {self.clubs[2].pk, self.clubs[3].pk})

    def test_home_flag_set_correctly(self):
        """is_home-Flag entspricht der Heim/Auswärts-Rolle im Fixture."""
        # Keine Marker → alle 4 werden gemeldet; is_home muss korrekt sein.
        result = check_finance_completeness(saison='0')
        home_ids = {g['club_id'] for g in result['gaps'] if g['is_home']}
        away_ids = {g['club_id'] for g in result['gaps'] if not g['is_home']}
        self.assertEqual(home_ids, {self.clubs[0].pk, self.clubs[2].pk})
        self.assertEqual(away_ids, {self.clubs[1].pk, self.clubs[3].pk})
