"""Tests für den seed_cmt_club_ids-Management-Command.

Abgedeckt:
  1. Dry-Run schreibt nichts in die DB
  2. Fehlende WS-Clubs werden als nicht gefunden gezählt
  3. Bekannte Clubs werden korrekt angelegt
  4. Alle 18 Bundesliga-Clubs werden in einem normalen Lauf angelegt
  5. Idempotenz: zweiter Aufruf → skipped
  6. Bestehender Eintrag mit falscher ID wird aktualisiert
  7. CMT-ID-Konflikt (gleiche ID für anderen WS-Club) wird abgelehnt
  8. Fehlende DataSource CMTRACKER → kein Crash, keine Einträge
"""

from io import StringIO

from django.test import TestCase

from game.models import Club, ClubExternalId, DataSource, League
from game.management.commands.seed_cmt_club_ids import BUNDESLIGA_CMT_IDS, DB_SLUG


def _make_league():
    return League.objects.create(name='Bundesliga Test', country='Deutschland')


def _make_cmt_source():
    return DataSource.objects.get_or_create(
        code='CMTRACKER',
        defaults={'name': 'CMTracker', 'url': 'https://cmtracker.net'},
    )[0]


def _make_club(league, name):
    return Club.objects.create(
        name=name,
        short_name=name[:8],
        founded_year=1900,
        budget=1_000_000,
        league=league,
        fan_popularity=50,
    )


def _make_all_bundesliga_clubs(league):
    """Legt alle 18 Bundesliga-Clubs so an, dass seed_cmt_club_ids alle findet."""
    clubs = {}
    for _cmt_id, ws_name in BUNDESLIGA_CMT_IDS:
        clubs[ws_name] = _make_club(league, ws_name)
    return clubs


def _run_cmd(**kwargs):
    """Führt seed_cmt_club_ids aus und gibt (stdout, stderr) zurück."""
    from django.core.management import call_command
    out, err = StringIO(), StringIO()
    call_command('seed_cmt_club_ids', stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


class SeedCmtClubIdsDryRunTest(TestCase):
    """Dry-Run schreibt nichts."""

    def setUp(self):
        _make_cmt_source()
        league = _make_league()
        _make_club(league, 'FC Bayern München')

    def test_dry_run_creates_no_records(self):
        _run_cmd(dry_run=True)
        self.assertEqual(ClubExternalId.objects.count(), 0)

    def test_dry_run_output_mentions_dry(self):
        out, _ = _run_cmd(dry_run=True)
        self.assertIn('DRY', out.upper())


class SeedCmtClubIdsAll18Test(TestCase):
    """Alle 18 Bundesliga-Clubs werden in einem normalen Lauf angelegt."""

    def setUp(self):
        self.cmt_source = _make_cmt_source()
        self.league = _make_league()
        self.clubs = _make_all_bundesliga_clubs(self.league)

    def test_all_18_clubs_get_external_ids(self):
        _run_cmd()
        self.assertEqual(
            ClubExternalId.objects.filter(source=self.cmt_source).count(),
            18,
            'Erwartet 18 ClubExternalId-Einträge – einen pro Bundesliga-Club.',
        )

    def test_union_berlin_is_included(self):
        _run_cmd()
        ext = ClubExternalId.objects.filter(
            source=self.cmt_source,
            external_id='1831',
            db_slug=DB_SLUG,
        ).select_related('club').first()
        self.assertIsNotNone(ext, '1. FC Union Berlin (CMT-ID 1831) muss eingetragen sein.')
        self.assertEqual(ext.club.name, '1. FC Union Berlin')

    def test_all_db_slugs_are_correct(self):
        _run_cmd()
        wrong = ClubExternalId.objects.filter(
            source=self.cmt_source,
        ).exclude(db_slug=DB_SLUG)
        self.assertEqual(wrong.count(), 0,
                         f'Alle Einträge müssen db_slug={DB_SLUG} haben.')

    def test_all_18_cmt_ids_present(self):
        _run_cmd()
        inserted_ids = set(
            ClubExternalId.objects.filter(source=self.cmt_source)
            .values_list('external_id', flat=True)
        )
        expected_ids = {cmt_id for cmt_id, _ in BUNDESLIGA_CMT_IDS}
        self.assertEqual(inserted_ids, expected_ids,
                         f'Fehlende IDs: {expected_ids - inserted_ids}')


class SeedCmtClubIdsCreateTest(TestCase):
    """Einzelne Clubs anlegen und Idempotenz prüfen."""

    def setUp(self):
        self.cmt_source = _make_cmt_source()
        self.league = _make_league()
        self.bayern = _make_club(self.league, 'FC Bayern München')
        self.bvb = _make_club(self.league, 'Borussia Dortmund')

    def test_known_clubs_get_external_ids(self):
        _run_cmd()
        self.assertEqual(
            ClubExternalId.objects.filter(source=self.cmt_source, external_id='21').count(), 1
        )
        self.assertEqual(
            ClubExternalId.objects.filter(source=self.cmt_source, external_id='22').count(), 1
        )

    def test_external_id_linked_to_correct_club(self):
        _run_cmd()
        ext = ClubExternalId.objects.get(source=self.cmt_source, external_id='21')
        self.assertEqual(ext.club.pk, self.bayern.pk)

    def test_db_slug_is_set(self):
        _run_cmd()
        ext = ClubExternalId.objects.get(source=self.cmt_source, external_id='21')
        self.assertEqual(ext.db_slug, DB_SLUG)

    def test_idempotent_second_run_skips(self):
        _run_cmd()
        count_after_first = ClubExternalId.objects.count()
        out, _ = _run_cmd()
        self.assertEqual(ClubExternalId.objects.count(), count_after_first)
        self.assertIn('bereits vorhanden', out)

    def test_missing_ws_club_is_counted_not_raised(self):
        out, _ = _run_cmd()
        self.assertIn('nicht gefunden', out)


class SeedCmtClubIdsUpdateTest(TestCase):
    """Bestehende Einträge mit falscher ID werden aktualisiert."""

    def setUp(self):
        self.cmt_source = _make_cmt_source()
        self.league = _make_league()
        self.bayern = _make_club(self.league, 'FC Bayern München')
        ClubExternalId.objects.create(
            club=self.bayern,
            source=self.cmt_source,
            external_id='9999',
            db_slug=DB_SLUG,
        )

    def test_wrong_id_is_updated_to_correct_id_with_force(self):
        _run_cmd(force=True)
        ext = ClubExternalId.objects.get(source=self.cmt_source, club=self.bayern)
        self.assertEqual(ext.external_id, '21')

    def test_wrong_id_without_force_shows_conflict_warning(self):
        out, _ = _run_cmd()
        self.assertIn('9999', out)

    def test_update_is_reported_in_output(self):
        out, _ = _run_cmd(force=True)
        self.assertIn('aktualisiert', out)


class SeedCmtClubIdsConflictTest(TestCase):
    """CMT-ID-Konflikt (gleiche ID für einen anderen WS-Club) wird abgelehnt."""

    def setUp(self):
        self.cmt_source = _make_cmt_source()
        self.league = _make_league()
        self.imposteur = _make_club(self.league, 'FC Imposteur')
        self.bayern = _make_club(self.league, 'FC Bayern München')
        ClubExternalId.objects.create(
            club=self.imposteur,
            source=self.cmt_source,
            external_id='21',
            db_slug=DB_SLUG,
        )

    def test_conflicting_external_id_is_not_overwritten(self):
        _run_cmd()
        ext = ClubExternalId.objects.get(source=self.cmt_source, external_id='21')
        self.assertEqual(ext.club.pk, self.imposteur.pk,
                         'Konflikt darf vorhandenen Eintrag nicht überschreiben.')

    def test_conflict_is_reported_in_output(self):
        out, _ = _run_cmd()
        self.assertIn('Konflikt', out)


class SeedCmtClubIdsMissingDataSourceTest(TestCase):
    """Fehlende DataSource CMTRACKER → kein Crash, keine Einträge."""

    def setUp(self):
        league = _make_league()
        _make_club(league, 'FC Bayern München')
        DataSource.objects.filter(code='CMTRACKER').delete()

    def test_missing_datasource_creates_no_entries_and_returns(self):
        """Ohne DataSource CMTRACKER werden keine ClubExternalId-Einträge angelegt."""
        self.assertFalse(DataSource.objects.filter(code='CMTRACKER').exists(),
                         'Test-Voraussetzung: CMTRACKER darf nicht existieren.')
        try:
            _run_cmd()
        except Exception as exc:
            self.fail(f'Command darf keinen Fehler werfen: {exc}')
        self.assertEqual(ClubExternalId.objects.count(), 0)
