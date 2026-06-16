"""Tests für die geschützte Importer-API (Spec §28/§38)."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from game.models import (
    Club, League, ClubPlayerImportJob, PlayerImportCandidate,
)

TOKEN = 'test-importer-token-0123456789'


@mock.patch.dict(os.environ, {'CFM_IMPORTER_TOKEN': TOKEN})
class ImporterApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.league = League.objects.create(name='ApiLiga', country='DE')
        self.ws_club = Club.objects.create(
            name='FC API', short_name='FCA', founded_year=2001,
            budget=Decimal('1000000'), league=self.league,
        )
        self.client = Client()

    # ── Hilfen ──────────────────────────────────────────────────────────
    def _job(self, **overrides):
        data = dict(
            ws_club=self.ws_club, tm_club_id=27, tm_season_id=2025,
            season_label='2025/26',
        )
        data.update(overrides)
        return ClubPlayerImportJob.objects.create(**data)

    def _auth(self, token=TOKEN):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def _post(self, name, args=None, payload=None, token=TOKEN, lease=None):
        headers = self._auth(token) if token else {}
        if lease:
            headers['HTTP_X_LEASE_TOKEN'] = lease
        return self.client.post(
            reverse(name, args=args or []),
            data=json.dumps(payload or {}),
            content_type='application/json',
            **headers,
        )

    def _claim(self, job):
        resp = self._post('importer_claim_job', args=[job.id])
        self.assertEqual(resp.status_code, 200)
        return resp.json()['lease_token']

    # ── Auth ────────────────────────────────────────────────────────────
    def test_missing_token_rejected(self):
        resp = self.client.get(reverse('importer_next_job'))
        self.assertEqual(resp.status_code, 401)

    def test_wrong_token_rejected(self):
        resp = self.client.get(reverse('importer_next_job'), **self._auth('falsch'))
        self.assertEqual(resp.status_code, 401)

    def test_correct_token_accepted(self):
        self._job()
        resp = self.client.get(reverse('importer_next_job'), **self._auth())
        self.assertEqual(resp.status_code, 200)

    def test_non_ascii_token_accepted(self):
        # Tokens dürfen Nicht-ASCII-Zeichen enthalten (bytes-Vergleich).
        self._job()
        special = 'gehäim-tökén-äöü-🔐'
        with mock.patch.dict(os.environ, {'CFM_IMPORTER_TOKEN': special}):
            ok = self.client.get(reverse('importer_next_job'), **self._auth(special))
            bad = self.client.get(reverse('importer_next_job'), **self._auth('falsch'))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(bad.status_code, 401)

    def test_unconfigured_token_returns_503(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CFM_IMPORTER_TOKEN', None)
            resp = self.client.get(reverse('importer_next_job'), **self._auth())
        self.assertEqual(resp.status_code, 503)

    # ── Next ────────────────────────────────────────────────────────────
    def test_next_returns_oldest_pending(self):
        older = self._job(tm_club_id=10)
        self._job(tm_club_id=11)
        resp = self.client.get(reverse('importer_next_job'), **self._auth())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], older.id)

    def test_next_204_when_none(self):
        resp = self.client.get(reverse('importer_next_job'), **self._auth())
        self.assertEqual(resp.status_code, 204)

    # ── Claim / Lease ───────────────────────────────────────────────────
    def test_claim_sets_lease_and_token(self):
        job = self._job()
        resp = self._post('importer_claim_job', args=[job.id])
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['lease_token'])
        job.refresh_from_db()
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_CLAIMED)
        self.assertEqual(job.lease_token, body['lease_token'])
        self.assertIsNotNone(job.lease_expires_at)

    def test_no_double_claim(self):
        job = self._job()
        self._claim(job)
        resp = self._post('importer_claim_job', args=[job.id])
        self.assertEqual(resp.status_code, 409)

    def test_expired_lease_is_reclaimable(self):
        job = self._job()
        self._claim(job)
        # Lease künstlich ablaufen lassen (kein Heartbeat mehr).
        ClubPlayerImportJob.objects.filter(pk=job.id).update(
            lease_expires_at=timezone.now() - timedelta(minutes=1),
        )
        resp = self._post('importer_claim_job', args=[job.id])
        self.assertEqual(resp.status_code, 200)
        new_token = resp.json()['lease_token']
        job.refresh_from_db()
        self.assertEqual(job.lease_token, new_token)

    def test_claim_unknown_job_404(self):
        resp = self._post('importer_claim_job', args=[999999])
        self.assertEqual(resp.status_code, 404)

    # ── Heartbeat ───────────────────────────────────────────────────────
    def test_heartbeat_renews_lease(self):
        job = self._job()
        token = self._claim(job)
        job.refresh_from_db()
        old_expiry = job.lease_expires_at
        ClubPlayerImportJob.objects.filter(pk=job.id).update(
            lease_expires_at=old_expiry - timedelta(seconds=30),
        )
        resp = self._post('importer_heartbeat', args=[job.id], lease=token)
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertGreater(job.lease_expires_at, old_expiry - timedelta(seconds=30))

    def test_heartbeat_wrong_lease_token_403(self):
        job = self._job()
        self._claim(job)
        resp = self._post('importer_heartbeat', args=[job.id], lease='falsch')
        self.assertEqual(resp.status_code, 403)

    def test_stale_lease_cannot_mutate_after_takeover(self):
        # Importer A übernimmt, Lease läuft ab, Importer B übernimmt neu.
        job = self._job()
        token_a = self._claim(job)
        ClubPlayerImportJob.objects.filter(pk=job.id).update(
            lease_expires_at=timezone.now() - timedelta(minutes=1),
        )
        token_b = self._claim(job)
        self.assertNotEqual(token_a, token_b)
        # Der veraltete Importer A darf nichts mehr schreiben.
        resp = self._post('importer_fail', args=[job.id], lease=token_a,
                          payload={'error': 'stale'})
        self.assertEqual(resp.status_code, 403)
        job.refresh_from_db()
        self.assertNotEqual(job.status, ClubPlayerImportJob.STATUS_FAILED)
        self.assertEqual(job.lease_token, token_b)

    # ── Progress ────────────────────────────────────────────────────────
    def test_progress_updates_fields(self):
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_progress', args=[job.id], lease=token, payload={
            'progress_current': 5, 'progress_total': 25, 'current_step': 'Kader',
        })
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.progress_current, 5)
        self.assertEqual(job.progress_total, 25)
        self.assertEqual(job.current_step, 'Kader')
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_RUNNING)

    def test_progress_rejects_negative(self):
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_progress', args=[job.id], lease=token, payload={
            'progress_current': -1,
        })
        self.assertEqual(resp.status_code, 400)

    # ── Kandidaten ──────────────────────────────────────────────────────
    def _candidate_payload(self, tm_player_id=892160):
        return {
            'tm_player_id': tm_player_id,
            'tm': {
                'display_name': 'Luka Vušković', 'first_name': 'Luka',
                'last_name': 'Vušković', 'date_of_birth': '2007-02-24',
                'height_cm': 193, 'preferred_foot': 'rechts',
                'primary_nationality': 'Kroatien', 'nationalities': ['Kroatien'],
                'market_value_eur': 0, 'profile_position': 'Innenverteidiger',
                'verbotenes_feld': 'sollte verworfen werden',
            },
            'positions': {
                'appearances': [{'source_position': 'Innenverteidiger',
                                 'mapped_position': 'IV', 'matches': 90}],
                'main_positions': ['IV'], 'secondary_positions': [],
            },
            'club_assignment': {
                'real_club': {'tm_club_id': 148, 'name': 'Tottenham', 'url': '...'},
                'loaned_from': None,
            },
            'fmi': {'id': '1', 'rating': 81, 'potential': 83},
            'sofifa': {'id': '2', 'rating': 86, 'potential': 89},
            'warnings': ['Beispielwarnung'],
            'errors': [],
        }

    def test_candidate_stores_raw_and_drops_unknown(self):
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_candidates', args=[job.id], lease=token,
                          payload=self._candidate_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['created'], 1)
        cand = job.candidates.get(tm_player_id=892160)
        self.assertEqual(cand.tm_raw['first_name'], 'Luka')
        self.assertNotIn('verbotenes_feld', cand.tm_raw)
        self.assertEqual(cand.tm_raw['club_assignment']['real_club']['name'], 'Tottenham')
        self.assertEqual(cand.position_raw['main_positions'], ['IV'])
        self.assertEqual(cand.fmi_raw['rating'], 81)
        self.assertEqual(cand.sofifa_raw['rating'], 86)
        self.assertEqual(cand.source_warnings, ['Beispielwarnung'])
        self.assertEqual(cand.status, PlayerImportCandidate.STATUS_NEW)

    def test_candidate_duplicate_tm_id_upserts(self):
        job = self._job()
        token = self._claim(job)
        self._post('importer_candidates', args=[job.id], lease=token,
                   payload=self._candidate_payload())
        payload = self._candidate_payload()
        payload['tm']['first_name'] = 'Geändert'
        resp = self._post('importer_candidates', args=[job.id], lease=token,
                          payload=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['updated'], 1)
        self.assertEqual(job.candidates.filter(tm_player_id=892160).count(), 1)
        cand = job.candidates.get(tm_player_id=892160)
        self.assertEqual(cand.tm_raw['first_name'], 'Geändert')

    def test_candidate_only_attached_to_target_job(self):
        job_a = self._job(tm_club_id=10)
        job_b = self._job(tm_club_id=11)
        token_b = self._claim(job_b)
        self._post('importer_candidates', args=[job_b.id], lease=token_b,
                   payload=self._candidate_payload())
        self.assertEqual(job_a.candidates.count(), 0)
        self.assertEqual(job_b.candidates.count(), 1)

    def test_candidate_invalid_tm_id_reported(self):
        job = self._job()
        token = self._claim(job)
        payload = self._candidate_payload()
        payload['tm_player_id'] = 0
        resp = self._post('importer_candidates', args=[job.id], lease=token,
                          payload=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['created'], 0)
        self.assertEqual(len(body['errors']), 1)

    def test_candidate_batch(self):
        job = self._job()
        token = self._claim(job)
        batch = {'candidates': [self._candidate_payload(1),
                                self._candidate_payload(2)]}
        resp = self._post('importer_candidates', args=[job.id], lease=token,
                          payload=batch)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['created'], 2)
        self.assertEqual(job.candidates.count(), 2)

    # ── Complete / Fail ─────────────────────────────────────────────────
    def test_complete_sets_review_and_clears_lease(self):
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_complete', args=[job.id], lease=token)
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_REVIEW)
        self.assertEqual(job.lease_token, '')

    def test_complete_confirms_provisional_club_name(self):
        # Manuell benannter Neuverein wird per TM-Name aktualisiert.
        self.ws_club.name = 'Mein Verein'
        self.ws_club.short_name = 'MV'
        self.ws_club.import_name_provisional = True
        self.ws_club.save()
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_complete', args=[job.id], lease=token,
                          payload={'tm_club_name': 'Hamburger SV'})
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.ws_club.refresh_from_db()
        self.assertEqual(job.tm_club_name, 'Hamburger SV')
        self.assertEqual(self.ws_club.name, 'Hamburger SV')
        self.assertEqual(self.ws_club.short_name, 'Hamburger SV'[:20])
        self.assertFalse(self.ws_club.import_name_provisional)

    def test_complete_keeps_established_club_name(self):
        # Nicht-vorläufiger (bestehender) Verein wird NICHT umbenannt.
        self.ws_club.name = 'FC API'
        self.ws_club.import_name_provisional = False
        self.ws_club.save()
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_complete', args=[job.id], lease=token,
                          payload={'tm_club_name': 'Hamburger SV'})
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.ws_club.refresh_from_db()
        self.assertEqual(job.tm_club_name, 'Hamburger SV')
        self.assertEqual(self.ws_club.name, 'FC API')

    def test_complete_without_tm_name_leaves_provisional_flag(self):
        # Ohne TM-Name bleibt der vorläufige Verein unverändert.
        self.ws_club.import_name_provisional = True
        self.ws_club.save()
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_complete', args=[job.id], lease=token)
        self.assertEqual(resp.status_code, 200)
        self.ws_club.refresh_from_db()
        self.assertTrue(self.ws_club.import_name_provisional)

    def test_fail_sets_failed_with_message(self):
        job = self._job()
        token = self._claim(job)
        resp = self._post('importer_fail', args=[job.id], lease=token,
                          payload={'error': 'Quelle nicht erreichbar'})
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_FAILED)
        self.assertEqual(job.error_message, 'Quelle nicht erreichbar')
        self.assertEqual(job.lease_token, '')

    # ── CSRF / Hardening ────────────────────────────────────────────────
    def test_token_endpoints_are_csrf_exempt(self):
        job = self._job()
        csrf_client = Client(enforce_csrf_checks=True)
        resp = csrf_client.post(
            reverse('importer_claim_job', args=[job.id]),
            data=json.dumps({}), content_type='application/json',
            **self._auth(),
        )
        self.assertEqual(resp.status_code, 200)

    def test_payload_too_large_rejected(self):
        job = self._job()
        token = self._claim(job)
        big = {'current_step': 'x' * 1_100_000}
        resp = self._post('importer_progress', args=[job.id], lease=token, payload=big)
        self.assertEqual(resp.status_code, 413)
