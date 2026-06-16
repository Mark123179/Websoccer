"""game/tests/test_club_import_ui.py

Creator-Mode Vereins-/Spielerimport — Web-Oberfläche & Roh→Normalisiert-Glue
(Task: Creator-Mode Import-Oberfläche).

Abgedeckte Bereiche:
  - build_normalized_data: Rohfelder → import-fähiges normalized_data-Schema
  - compute_detected_changes: Alt→Neu-Diffs gegen vorhandenen Spieler
  - refresh_candidate: Klassifizierung (neu / geändert / unverändert / ungültig)
  - Views: Staff-Zugriffsschutz, Auftrag anlegen, Kontrollansicht, Sammelaktionen,
    Einzelkorrektur, verbindlicher Import (Ende-zu-Ende über die Oberfläche)
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from game.models import (
    Club,
    ClubPlayerImportJob,
    League,
    Player,
    PlayerImportCandidate,
    PlayerSourceRating,
)
from game.club_import.review import (
    build_normalized_data,
    compute_detected_changes,
    refresh_candidate,
)


def _tm_raw(**over):
    raw = {
        'profile_url': 'https://www.transfermarkt.de/x/28049320',
        'first_name': 'Harry', 'last_name': 'Kane',
        'date_of_birth': '28.07.1993',
        'height_cm': '1,88 m', 'preferred_foot': 'rechts',
        'nationalities': ['England'],
        'market_value_eur': '100,00 Mio. €',
        'profile_position': 'Mittelstürmer',
        'club_assignment': {},
    }
    raw.update(over)
    return raw


class BuildNormalizedTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='C', short_name='C', founded_year=2000,
            budget=Decimal('0'), league=self.league)
        self.job = ClubPlayerImportJob.objects.create(
            ws_club=self.club, tm_club_id=27, tm_season_id=2025,
            season_label='2025/26')

    def _cand(self, **fields):
        defaults = dict(
            job=self.job, tm_player_id=28049320,
            tm_raw=_tm_raw(),
            position_raw={'appearances': [
                {'source_position': 'Mittelstürmer', 'matches': 30},
                {'source_position': 'Hängende Spitze', 'matches': 12},
            ]},
            fmi_raw={'id': 123456, 'url': 'https://fminside.net/x',
                     'rating': 88, 'potential': 90,
                     'attrs': {'abschluss': 95}},
            sofifa_raw={'id': '202126', 'url': 'https://sofifa.com/player/202126',
                        'rating': 90, 'potential': 91, 'attrs': {'abschluss': 93}},
        )
        defaults.update(fields)
        return PlayerImportCandidate.objects.create(**defaults)

    def test_build_maps_all_core_fields(self):
        nd, warnings = build_normalized_data(self._cand())
        self.assertEqual(nd['first_name'], 'Harry')
        self.assertEqual(nd['last_name'], 'Kane')
        self.assertEqual(nd['date_of_birth'], '1993-07-28')
        self.assertEqual(nd['height_cm'], 188)
        self.assertEqual(nd['strong_foot'], 'R')
        self.assertEqual(nd['market_value'], 100_000_000)
        self.assertEqual(nd['primary_nationality'], 'England')
        self.assertEqual(nd['main_positions'], ['ST'])
        self.assertEqual(nd['fm_inside_id'], 123456)
        self.assertEqual(nd['sofifa_id'], '202126')
        self.assertEqual(nd['fmi_ratings']['rating'], 88)
        self.assertEqual(nd['sofifa_ratings']['attrs']['abschluss'], 93)

    def test_missing_values_stay_null_never_zero(self):
        cand = self._cand(tm_raw=_tm_raw(market_value_eur='-', height_cm=''))
        nd, _ = build_normalized_data(cand)
        self.assertIsNone(nd['market_value'])
        self.assertIsNone(nd['height_cm'])

    def test_missing_fmi_yields_none_ratings(self):
        cand = self._cand(fmi_raw={}, sofifa_raw={})
        nd, _ = build_normalized_data(cand)
        self.assertIsNone(nd['fmi_ratings'])
        self.assertIsNone(nd['sofifa_ratings'])
        self.assertIsNone(nd['fm_inside_id'])

    def test_loan_assignment_mapped(self):
        cand = self._cand(tm_raw=_tm_raw(club_assignment={
            'loaned_from': {'tm_club_id': 148, 'name': 'Tottenham',
                            'url': 'https://tm/148'}}))
        nd, _ = build_normalized_data(cand)
        self.assertEqual(nd['loaned_from']['tm_id'], 148)
        self.assertEqual(nd['loaned_from']['name'], 'Tottenham')

    def test_explicit_positions_take_precedence(self):
        cand = self._cand(position_raw={
            'main_positions': ['IV'], 'secondary_positions': ['DM']})
        nd, _ = build_normalized_data(cand)
        self.assertEqual(nd['main_positions'], ['IV'])
        self.assertEqual(nd['secondary_positions'], ['DM'])

    def test_display_name_split_fallback(self):
        cand = self._cand(tm_raw=_tm_raw(first_name='', last_name='',
                                         display_name='Leroy Sané'))
        nd, _ = build_normalized_data(cand)
        self.assertEqual(nd['first_name'], 'Leroy')
        self.assertEqual(nd['last_name'], 'Sané')


class RefreshClassifyTests(TestCase):
    def setUp(self):
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='C', short_name='C', founded_year=2000,
            budget=Decimal('0'), league=self.league)
        self.job = ClubPlayerImportJob.objects.create(
            ws_club=self.club, tm_club_id=27, tm_season_id=2025,
            season_label='2025/26')

    def _cand(self, **fields):
        defaults = dict(
            job=self.job, tm_player_id=28049320,
            tm_raw=_tm_raw(),
            position_raw={'appearances': [
                {'source_position': 'Mittelstürmer', 'matches': 30}]},
            fmi_raw={'id': 123456, 'rating': 88, 'potential': 90, 'attrs': {}},
            sofifa_raw={'id': '202126', 'rating': 90, 'potential': 91, 'attrs': {}},
        )
        defaults.update(fields)
        return PlayerImportCandidate.objects.create(**defaults)

    def test_new_when_no_existing(self):
        cand = refresh_candidate(self._cand(), reset_selection=True)
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_NEW)
        self.assertTrue(cand.selected_for_import)

    def test_invalid_when_no_positions(self):
        cand = self._cand(position_raw={}, tm_raw=_tm_raw(profile_position=''))
        cand = refresh_candidate(cand, reset_selection=True)
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_INVALID)
        self.assertFalse(cand.selected_for_import)
        self.assertTrue(cand.validation_errors)

    def test_existing_changed_sets_overwrite_and_diff(self):
        Player.objects.create(
            first_name='Harry', last_name='Kane', age=30,
            transfermarkt_id=28049320, club=self.club,
            market_value=50_000_000)
        cand = refresh_candidate(self._cand(), reset_selection=True)
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_EXISTING_CHANGED)
        self.assertTrue(cand.overwrite_existing)
        keys = [c['key'] for c in cand.detected_changes['items']]
        self.assertIn('market_value', keys)

    def test_existing_unchanged_when_identical(self):
        p = Player.objects.create(
            first_name='Harry', last_name='Kane', age=30,
            transfermarkt_id=28049320, club=self.club,
            date_of_birth=date(1993, 7, 28), height_cm=188,
            strong_foot='R', nationalities='England',
            market_value=100_000_000, fm_inside_id=123456)
        p.main_position_1 = 'ST'
        p.save()
        PlayerSourceRating.objects.create(
            player=p, source=PlayerSourceRating.SOURCE_FM, rating=88)
        PlayerSourceRating.objects.create(
            player=p, source=PlayerSourceRating.SOURCE_EA, rating=90)
        from game.models import DataSource, PlayerExternalId
        src, _ = DataSource.objects.get_or_create(
            code=DataSource.CODE_SOFIFA, defaults={'name': 'SoFIFA'})
        PlayerExternalId.objects.create(player=p, source=src, external_id='202126')

        cand = refresh_candidate(self._cand(), reset_selection=True)
        changes = compute_detected_changes(p, cand.normalized_data)
        self.assertEqual(changes, [])
        self.assertEqual(
            cand.status, PlayerImportCandidate.STATUS_EXISTING_UNCHANGED)
        self.assertFalse(cand.selected_for_import)


class ImportUiViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='staff', password='pw', is_staff=True)
        self.normal = User.objects.create_user(username='joe', password='pw')
        self.league = League.objects.create(name='L', country='DE')
        self.club = Club.objects.create(
            name='FC Import', short_name='FCI', founded_year=2000,
            budget=Decimal('1000000'), league=self.league)

    def _job(self, status=ClubPlayerImportJob.STATUS_REVIEW):
        return ClubPlayerImportJob.objects.create(
            ws_club=self.club, tm_club_id=27, tm_season_id=2025,
            season_label='2025/26', status=status)

    def _cand(self, job, tm_player_id=28049320, **fields):
        defaults = dict(
            job=job, tm_player_id=tm_player_id,
            tm_raw=_tm_raw(),
            position_raw={'appearances': [
                {'source_position': 'Mittelstürmer', 'matches': 30}]},
            fmi_raw={'id': 123456, 'rating': 88, 'potential': 90, 'attrs': {}},
            sofifa_raw={'id': '202126', 'rating': 90, 'potential': 91, 'attrs': {}},
        )
        defaults.update(fields)
        return PlayerImportCandidate.objects.create(**defaults)

    def test_non_staff_is_forbidden(self):
        self.client.force_login(self.normal)
        resp = self.client.get(reverse('creator_import_index'))
        self.assertEqual(resp.status_code, 403)

    def test_index_lists_for_staff(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('creator_import_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Importauftrag')

    def test_create_job(self):
        self.client.force_login(self.staff)
        resp = self.client.post(reverse('creator_import_create'), {
            'ws_club': self.club.pk, 'tm_club_id': '27'})
        self.assertEqual(resp.status_code, 302)
        job = ClubPlayerImportJob.objects.latest('created_at')
        self.assertEqual(job.ws_club, self.club)
        self.assertEqual(job.tm_club_id, 27)
        self.assertTrue(job.season_label)

    def test_create_rejects_bad_tm_id(self):
        self.client.force_login(self.staff)
        resp = self.client.post(reverse('creator_import_create'), {
            'ws_club': self.club.pk, 'tm_club_id': 'abc'})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ClubPlayerImportJob.objects.exists())

    def test_review_detail_builds_candidates(self):
        job = self._job()
        self._cand(job)
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('creator_import_detail', args=[job.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kane')
        cand = job.candidates.first()
        self.assertNotEqual(cand.normalized_data, {})
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_NEW)

    def test_review_flags_missing_fmid_for_manual_entry(self):
        job = self._job()
        # Kandidat ohne FM-ID (Importer konnte FMInside nicht auflösen).
        self._cand(job, fmi_raw={}, sofifa_raw={})
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('creator_import_detail', args=[job.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'FM-ID manuell setzen')
        self.assertContains(resp, 'FM-ID prüfbedürftig')
        self.assertEqual(resp.context['counts']['fmi_needs_manual'], 1)

    def test_review_does_not_flag_when_fmid_present(self):
        job = self._job()
        self._cand(job)  # hat eine FM-ID
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('creator_import_detail', args=[job.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['counts']['fmi_needs_manual'], 0)
        self.assertNotContains(resp, 'FM-ID manuell setzen')

    def test_status_endpoint_json(self):
        job = self._job(status=ClubPlayerImportJob.STATUS_RUNNING)
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('creator_import_status', args=[job.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'running')

    def test_bulk_deselect_unchanged(self):
        job = self._job()
        cand = self._cand(job)
        cand.status = PlayerImportCandidate.STATUS_EXISTING_UNCHANGED
        cand.selected_for_import = True
        cand.normalized_data = {'x': 1}
        cand.save()
        self.client.force_login(self.staff)
        self.client.post(reverse('creator_import_bulk', args=[job.pk]),
                         {'action': 'deselect_unchanged'})
        cand.refresh_from_db()
        self.assertFalse(cand.selected_for_import)

    def test_candidate_toggle_select(self):
        job = self._job()
        cand = self._cand(job)
        cand.normalized_data = {'x': 1}
        cand.save()
        self.client.force_login(self.staff)
        self.client.post(
            reverse('creator_import_candidate_update', args=[job.pk, cand.pk]),
            {'action': 'toggle_select'})
        cand.refresh_from_db()
        self.assertTrue(cand.selected_for_import)

    def test_confirm_imports_selected_end_to_end(self):
        job = self._job()
        cand = self._cand(job)
        refresh_candidate(cand, reset_selection=True)
        self.assertTrue(cand.selected_for_import)
        self.client.force_login(self.staff)
        resp = self.client.post(reverse('creator_import_confirm', args=[job.pk]))
        self.assertEqual(resp.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_COMPLETED)
        self.assertTrue(Player.objects.filter(transfermarkt_id=28049320).exists())
        cand.refresh_from_db()
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_IMPORTED)

    def test_cancel_job(self):
        job = self._job()
        self.client.force_login(self.staff)
        self.client.post(reverse('creator_import_bulk', args=[job.pk]),
                         {'action': 'cancel'})
        job.refresh_from_db()
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_CANCELLED)

    def test_completed_job_candidate_immutable(self):
        job = self._job(status=ClubPlayerImportJob.STATUS_COMPLETED)
        cand = self._cand(job)
        cand.normalized_data = {'x': 1}
        cand.selected_for_import = False
        cand.save()
        self.client.force_login(self.staff)
        resp = self.client.post(
            reverse('creator_import_candidate_update', args=[job.pk, cand.pk]),
            {'action': 'toggle_select'})
        self.assertEqual(resp.status_code, 302)
        cand.refresh_from_db()
        self.assertFalse(cand.selected_for_import)

    def test_completed_job_bulk_blocked(self):
        job = self._job(status=ClubPlayerImportJob.STATUS_COMPLETED)
        cand = self._cand(job)
        cand.status = PlayerImportCandidate.STATUS_NEW
        cand.selected_for_import = False
        cand.save()
        self.client.force_login(self.staff)
        self.client.post(reverse('creator_import_bulk', args=[job.pk]),
                         {'action': 'select_new_changed'})
        cand.refresh_from_db()
        self.assertFalse(cand.selected_for_import)

    def test_completed_job_cannot_be_cancelled(self):
        job = self._job(status=ClubPlayerImportJob.STATUS_COMPLETED)
        self.client.force_login(self.staff)
        self.client.post(reverse('creator_import_bulk', args=[job.pk]),
                         {'action': 'cancel'})
        job.refresh_from_db()
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_COMPLETED)

    def test_completed_job_cannot_reconfirm(self):
        job = self._job(status=ClubPlayerImportJob.STATUS_COMPLETED)
        self.client.force_login(self.staff)
        resp = self.client.post(
            reverse('creator_import_confirm', args=[job.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Player.objects.filter(transfermarkt_id=28049320).exists())
