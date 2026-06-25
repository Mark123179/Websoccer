"""End-to-End-Abnahme des Vereins-/Spielerimports (Task „Doku & Abnahme").

Durchläuft die komplette Kette über die echten Komponenten:

    Auftrag anlegen
        → geschützte Token-API (next → claim → candidates → complete)
        → Kontrollaufbereitung (review.refresh_job_candidates, Klassifizierung)
        → verbindlicher DB-Import (import_service.import_selected_candidates)
        → Ergebniszusammenfassung

Als manueller Referenzfall dient der HSV (Transfermarkt-Vereins-ID 41,
Saison-ID 2025) mit Luka Vušković (Transfermarkt-Spieler-ID 892160). Diese
Werte sind reine Testfixtures — sie sind NICHT als Sonderregel im
Produktivcode verdrahtet, sondern fließen ausschließlich als normale
Eingabedaten durch die generische Pipeline.

Abgedeckte Definition-of-Done-Punkte:
    * neuer Spieler (Vušković) wird angelegt,
    * vorhandener Spieler wird gezielt überschrieben,
    * fehlendes CMTracker blockiert nicht (kein externer CMTracker-Eintrag),
    * Platzhalterverein (Leihgeber) wird automatisch erzeugt,
    * NULL-Erhalt (fehlende Werte bleiben None/''),
    * Importbestätigung liefert eine korrekte Zusammenfassung.
"""

import json
import os
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from game.models import (
    Club,
    ClubPlayerImportJob,
    DataSource,
    League,
    Player,
    PlayerExternalId,
    PlayerImportCandidate,
    PlayerSourceRating,
)
from game.club_import.review import refresh_job_candidates
from game.club_import.import_service import import_selected_candidates

TOKEN = 'e2e-importer-token-0123456789abcdef'

# ── Referenzfall HSV / Luka Vušković (nur Testfixtures) ──────────────────────
HSV_TM_CLUB_ID = 41
HSV_TM_SEASON_ID = 2025
VUSKOVIC_TM_ID = 892160
TOTTENHAM_TM_CLUB_ID = 148  # Leihgeber — existiert in der DB noch nicht.

EXISTING_TM_ID = 11111  # vorhandener HSV-Spieler für den Überschreibfall.


@mock.patch.dict(os.environ, {'CFM_IMPORTER_TOKEN': TOKEN})
class ClubImportEndToEndTests(TestCase):
    """Ein durchgehender Abnahmelauf gegen den HSV-/Vušković-Referenzfall."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {TOKEN}'}

        self.league = League.objects.create(name='Bundesliga (Test)', country='DE')
        self.hsv = Club.objects.create(
            name='Hamburger SV', short_name='HSV', founded_year=1887,
            budget=Decimal('25000000'), league=self.league,
        )

        # Vorhandener HSV-Spieler, der später gezielt überschrieben wird.
        self.existing = Player.objects.create(
            first_name='Sebastian', last_name='Schonlau', age=30,
            date_of_birth=date(1994, 12, 1), club=self.hsv,
            transfermarkt_id=EXISTING_TM_ID,
            market_value=Decimal('2000000'),
            main_position_1='IV',
        )

    # ── Hilfen für die Roh-Payloads des lokalen Importers ────────────────────
    def _vuskovic_payload(self):
        """Neuer Spieler, Leihe von Tottenham, FMInside vorhanden, CMTracker fehlt."""
        return {
            'tm_player_id': VUSKOVIC_TM_ID,
            'tm': {
                'profile_url': 'https://www.transfermarkt.de/luka-vuskovic/profil/spieler/892160',
                'display_name': 'Luka Vušković',
                'first_name': 'Luka',
                'last_name': 'Vušković',
                'date_of_birth': '07.02.2007',
                'height_cm': '1,97 m',
                'preferred_foot': 'rechts',
                'primary_nationality': 'Kroatien',
                'nationalities': ['Kroatien'],
                'market_value_eur': '20,00 Mio. €',
                'profile_position': 'Innenverteidiger',
            },
            'club_assignment': {
                'loaned_from': {
                    'tm_club_id': TOTTENHAM_TM_CLUB_ID,
                    'name': 'Tottenham Hotspur',
                    'url': 'https://www.transfermarkt.de/tottenham-hotspur/startseite/verein/148',
                },
            },
            'positions': {
                'main_positions': ['IV'],
                'secondary_positions': [],
                'appearances': [],
            },
            'fmi': {
                'id': 7654321,
                'url': 'https://fminside.net/players/7-fm-26/7654321-luka-vuskovic',
                'rating': 78,
                'potential': 90,
                'attrs': {'zweikampf': 16, 'kopfball': 15},
            },
            # Kein 'sofifa'-Block → fehlendes CMTracker darf NICHT blockieren.
            'warnings': ['CMTracker: kein eindeutiger Treffer (optional).'],
            'errors': [],
        }

    def _existing_player_payload(self):
        """Bekannter Spieler (gleiche TM-ID) mit geänderten Werten → Überschreiben."""
        return {
            'tm_player_id': EXISTING_TM_ID,
            'tm': {
                'profile_url': 'https://www.transfermarkt.de/x/profil/spieler/11111',
                'display_name': 'Sebastian Schonlau',
                'first_name': 'Sebastian',
                'last_name': 'Schonlau',
                'date_of_birth': '01.12.1994',
                'height_cm': '1,90 m',
                'preferred_foot': 'rechts',
                'primary_nationality': 'Deutschland',
                'nationalities': ['Deutschland'],
                'market_value_eur': '3,50 Mio. €',  # geändert (vorher 2,0 Mio.)
                'profile_position': 'Innenverteidiger',
            },
            'club_assignment': {
                'real_club': {
                    'tm_club_id': HSV_TM_CLUB_ID,
                    'name': 'Hamburger SV',
                    'url': 'https://www.transfermarkt.de/hamburger-sv/startseite/verein/41',
                },
            },
            'positions': {
                'main_positions': ['IV', 'DM'],  # geändert (DM zusätzlich)
                'secondary_positions': [],
                'appearances': [],
            },
            'fmi': {
                'id': 1234567,
                'url': 'https://fminside.net/players/7-fm-26/1234567-sebastian-schonlau',
                'rating': 74,
                'potential': 74,
                'attrs': {'zweikampf': 14},
            },
            'warnings': [],
            'errors': [],
        }

    # ── Der Gesamtdurchlauf ──────────────────────────────────────────────────
    def test_full_pipeline_hsv_reference_case(self):
        # 1) Auftrag anlegen (wie über die Creator-Oberfläche).
        job = ClubPlayerImportJob.objects.create(
            ws_club=self.hsv,
            tm_club_id=HSV_TM_CLUB_ID,
            tm_season_id=HSV_TM_SEASON_ID,
            season_label='2025/26',
        )

        # 2) Lokaler Importer holt den nächsten offenen Auftrag.
        resp = self.client.get(reverse('importer_next_job'), **self.auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], job.id)
        self.assertEqual(resp.json()['tm_club_id'], HSV_TM_CLUB_ID)
        self.assertEqual(resp.json()['tm_season_id'], HSV_TM_SEASON_ID)

        # 3) Auftrag exklusiv übernehmen (Lease-Token).
        resp = self.client.post(
            reverse('importer_claim_job', args=[job.id]), **self.auth)
        self.assertEqual(resp.status_code, 200)
        lease_token = resp.json()['lease_token']
        self.assertTrue(lease_token)
        lease_header = {'HTTP_X_LEASE_TOKEN': lease_token}

        # 4) Kandidaten übertragen (Batch), wie der Importer es pro Kader tut.
        resp = self.client.post(
            reverse('importer_candidates', args=[job.id]),
            data=json.dumps({'candidates': [
                self._vuskovic_payload(),
                self._existing_player_payload(),
            ]}),
            content_type='application/json',
            **{**self.auth, **lease_header},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['created'], 2)
        self.assertEqual(body['errors'], [])

        # 5) Auftrag abschließen → wartet auf Kontrolle.
        resp = self.client.post(
            reverse('importer_complete', args=[job.id]),
            content_type='application/json',
            **{**self.auth, **lease_header},
        )
        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_REVIEW)
        self.assertEqual(job.lease_token, '')  # Lease wurde freigegeben.

        # 6) Kontrollaufbereitung (entspricht dem Öffnen der Detailansicht).
        refresh_job_candidates(job, reset_selection=True)

        vusko = job.candidates.get(tm_player_id=VUSKOVIC_TM_ID)
        existing_cand = job.candidates.get(tm_player_id=EXISTING_TM_ID)

        # Neuer Spieler korrekt erkannt, fehlendes CMTracker als Hinweis (nicht Fehler).
        self.assertEqual(vusko.status, PlayerImportCandidate.STATUS_NEW)
        self.assertEqual(vusko.validation_errors, [])
        self.assertTrue(vusko.selected_for_import)
        self.assertFalse(vusko.overwrite_existing)
        self.assertIsNone(vusko.normalized_data.get('sofifa_ratings'))
        self.assertEqual(vusko.normalized_data['height_cm'], 197)
        self.assertEqual(vusko.normalized_data['market_value'], 20000000)
        self.assertEqual(vusko.normalized_data['strong_foot'], 'R')

        # Vorhandener Spieler als „geändert" erkannt und zum Überschreiben markiert.
        self.assertEqual(
            existing_cand.status, PlayerImportCandidate.STATUS_EXISTING_CHANGED)
        self.assertEqual(existing_cand.existing_player_id, self.existing.id)
        self.assertTrue(existing_cand.selected_for_import)
        self.assertTrue(existing_cand.overwrite_existing)
        change_keys = {c['key'] for c in existing_cand.detected_changes['items']}
        self.assertIn('market_value', change_keys)
        self.assertIn('main_positions', change_keys)

        # 7) Verbindlicher Datenbankimport der ausgewählten Kandidaten.
        outcome = import_selected_candidates(job, user=None)
        stats = outcome['stats']
        self.assertEqual(stats['created'], 1)
        self.assertEqual(stats['updated'], 1)
        self.assertEqual(stats['failed'], 0)

        # 8a) Neuer Spieler Vušković ist angelegt.
        new_player = Player.objects.get(transfermarkt_id=VUSKOVIC_TM_ID)
        self.assertEqual(new_player.last_name, 'Vušković')
        self.assertEqual(new_player.club, self.hsv)
        self.assertEqual(new_player.height_cm, 197)
        self.assertEqual(new_player.main_position_1, 'IV')

        # 8b) Platzhalter-Leihgeber (Tottenham) wurde automatisch erzeugt.
        parent = new_player.loan_partner_club
        self.assertIsNotNone(parent)
        self.assertTrue(parent.is_import_placeholder)
        self.assertEqual(parent.transfermarkt_id, TOTTENHAM_TM_CLUB_ID)
        self.assertEqual(new_player.real_life_club, parent)

        # 8c) Fehlendes CMTracker: kein externer CMTracker-Eintrag, aber FMInside-Rating.
        sofifa_source = DataSource.objects.filter(
            code=DataSource.CODE_CMTRACKER).first()
        if sofifa_source:
            self.assertFalse(
                PlayerExternalId.objects.filter(
                    player=new_player, source=sofifa_source).exists())
        self.assertTrue(
            PlayerSourceRating.objects.filter(
                player=new_player, source=PlayerSourceRating.SOURCE_FM).exists())
        self.assertFalse(
            PlayerSourceRating.objects.filter(
                player=new_player, source=PlayerSourceRating.SOURCE_CMTRACKER).exists())

        # 8d) Vorhandener Spieler wurde überschrieben (kein Duplikat).
        self.assertEqual(
            Player.objects.filter(transfermarkt_id=EXISTING_TM_ID).count(), 1)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.market_value, Decimal('3500000'))
        self.assertEqual(self.existing.main_position_2, 'DM')

        # 8e) Kandidaten tragen den Endstatus „importiert".
        vusko.refresh_from_db()
        existing_cand.refresh_from_db()
        self.assertEqual(vusko.status, PlayerImportCandidate.STATUS_IMPORTED)
        self.assertEqual(existing_cand.status, PlayerImportCandidate.STATUS_IMPORTED)

    def test_unselected_existing_player_is_not_overwritten(self):
        """Ohne Auswahl/Überschreiben bleibt ein vorhandener Spieler unangetastet."""
        job = ClubPlayerImportJob.objects.create(
            ws_club=self.hsv, tm_club_id=HSV_TM_CLUB_ID,
            tm_season_id=HSV_TM_SEASON_ID, season_label='2025/26',
        )
        cand = PlayerImportCandidate.objects.create(
            job=job, tm_player_id=EXISTING_TM_ID,
            tm_raw={
                'first_name': 'Sebastian', 'last_name': 'Schonlau',
                'date_of_birth': '01.12.1994', 'market_value_eur': '9,00 Mio. €',
            },
            position_raw={'main_positions': ['IV']},
        )
        refresh_job_candidates(job, reset_selection=False)
        cand.refresh_from_db()
        cand.selected_for_import = False
        cand.save(update_fields=['selected_for_import'])

        outcome = import_selected_candidates(job, user=None)
        self.assertEqual(outcome['stats']['created'], 0)
        self.assertEqual(outcome['stats']['updated'], 0)

        self.existing.refresh_from_db()
        self.assertEqual(self.existing.market_value, Decimal('2000000'))
