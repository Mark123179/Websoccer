"""Import eines im WS noch nicht existierenden Vereins (Verein + Kader).

Deckt das Anlegen eines Importauftrags für einen brandneuen WS-Verein ab:

    * neuer Verein wird als echter Verein in der gewählten Liga angelegt,
    * ein vorhandener Platzhalterverein (gleiche TM-ID) wird hochgestuft
      statt dupliziert,
    * ein bereits vorhandener echter Verein wird abgelehnt,
    * die Auftrags-Erstellung über die Creator-Oberfläche wählt den Modus
      korrekt aus (bestehend / neu).
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from game.models import Club, ClubPlayerImportJob, League
from game.club_import.import_service import create_or_promote_target_club

NEW_TM_CLUB_ID = 41
NEW_CLUB_NAME = 'Hamburger SV'


class CreateOrPromoteTargetClubTests(TestCase):
    """Direkte Tests der Helferfunktion."""

    def setUp(self):
        self.league = League.objects.create(name='2. Bundesliga', country='DE')

    def test_creates_real_club_in_chosen_league(self):
        club, status = create_or_promote_target_club(
            tm_club_id=NEW_TM_CLUB_ID, name=NEW_CLUB_NAME, league=self.league)
        self.assertEqual(status, 'created')
        self.assertFalse(club.is_import_placeholder)
        self.assertEqual(club.league, self.league)
        self.assertEqual(club.transfermarkt_id, NEW_TM_CLUB_ID)
        self.assertEqual(club.name, NEW_CLUB_NAME)

    def test_promotes_existing_placeholder_without_duplicate(self):
        placeholder_league = League.objects.create(
            name='Platzhalter (Import)', country='Unbekannt')
        placeholder = Club.objects.create(
            name='HSV', short_name='HSV', founded_year=0,
            budget=Decimal('0'), league=placeholder_league,
            transfermarkt_id=NEW_TM_CLUB_ID, is_import_placeholder=True,
        )

        club, status = create_or_promote_target_club(
            tm_club_id=NEW_TM_CLUB_ID, name=NEW_CLUB_NAME, league=self.league)

        self.assertEqual(status, 'promoted')
        self.assertEqual(club.pk, placeholder.pk)
        self.assertFalse(club.is_import_placeholder)
        self.assertEqual(club.league, self.league)
        self.assertEqual(club.name, NEW_CLUB_NAME)
        self.assertEqual(
            Club.objects.filter(transfermarkt_id=NEW_TM_CLUB_ID).count(), 1)

    def test_rejects_existing_real_club(self):
        real = Club.objects.create(
            name=NEW_CLUB_NAME, short_name='HSV', founded_year=1887,
            budget=Decimal('25000000'), league=self.league,
            transfermarkt_id=NEW_TM_CLUB_ID, is_import_placeholder=False,
        )
        club, status = create_or_promote_target_club(
            tm_club_id=NEW_TM_CLUB_ID, name=NEW_CLUB_NAME, league=self.league)
        self.assertEqual(status, 'exists')
        self.assertEqual(club.pk, real.pk)
        self.assertEqual(
            Club.objects.filter(transfermarkt_id=NEW_TM_CLUB_ID).count(), 1)

    def test_dedup_by_name_when_no_tm_id_match(self):
        existing = Club.objects.create(
            name=NEW_CLUB_NAME, short_name='HSV', founded_year=1887,
            budget=Decimal('1000000'), league=self.league,
            is_import_placeholder=False,
        )
        club, status = create_or_promote_target_club(
            tm_club_id=999999, name='hamburger sv', league=self.league)
        self.assertEqual(status, 'exists')
        self.assertEqual(club.pk, existing.pk)

    def test_name_match_with_conflicting_tm_id_is_rejected(self):
        # Platzhalter trägt eine ANDERE, gesetzte TM-ID als die eingegebene →
        # darf nicht still hochgestuft werden (Identitätskonflikt).
        placeholder = Club.objects.create(
            name=NEW_CLUB_NAME, short_name='HSV', founded_year=0,
            budget=Decimal('0'), league=self.league,
            transfermarkt_id=555, is_import_placeholder=True,
        )
        club, status = create_or_promote_target_club(
            tm_club_id=NEW_TM_CLUB_ID, name=NEW_CLUB_NAME, league=self.league)
        self.assertEqual(status, 'conflict')
        self.assertEqual(club.pk, placeholder.pk)
        placeholder.refresh_from_db()
        self.assertTrue(placeholder.is_import_placeholder)
        self.assertEqual(placeholder.transfermarkt_id, 555)

    def test_integrity_error_on_create_is_recovered_not_raised(self):
        # Simuliert ein Wettrennen: Die erste Auflösung findet nichts, der
        # create() schlägt mit IntegrityError fehl (paralleler Insert), und erst
        # bei der Wiederauflösung existiert die Zeile. Der Helfer muss dann
        # deterministisch 'exists'/'promoted' zurückgeben statt 500/Duplikat.
        orig_filter = Club.objects.filter
        orig_all = Club.objects.all
        state = {'create_called': False, 'row': None}

        def _make_row():
            club = Club(
                name=NEW_CLUB_NAME, short_name='HSV', founded_year=1887,
                budget=Decimal('0'), league=self.league,
                transfermarkt_id=NEW_TM_CLUB_ID, is_import_placeholder=False,
            )
            club.save()
            return club

        def filter_side(*args, **kwargs):
            # Erst nach dem fehlgeschlagenen create() ist die Zeile sichtbar.
            if state['create_called']:
                if state['row'] is None:
                    state['row'] = _make_row()
                return orig_filter(*args, **kwargs)
            return orig_filter(pk=-1)

        def all_side(*args, **kwargs):
            if state['create_called']:
                return orig_all(*args, **kwargs)
            return orig_filter(pk=-1)

        def create_side(*args, **kwargs):
            state['create_called'] = True
            raise IntegrityError('duplicate key value violates unique constraint')

        with mock.patch.object(Club.objects, 'filter', side_effect=filter_side), \
                mock.patch.object(Club.objects, 'all', side_effect=all_side), \
                mock.patch.object(Club.objects, 'create', side_effect=create_side):
            club, status = create_or_promote_target_club(
                tm_club_id=NEW_TM_CLUB_ID, name=NEW_CLUB_NAME, league=self.league)

        self.assertEqual(status, 'exists')
        self.assertEqual(club.transfermarkt_id, NEW_TM_CLUB_ID)
        self.assertEqual(
            Club.objects.filter(transfermarkt_id=NEW_TM_CLUB_ID).count(), 1)


class CreatorImportCreateNewClubTests(TestCase):
    """Auftrags-Erstellung über die Creator-Oberfläche im Neu-Modus."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='creator', password='pw12345', is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)
        self.league = League.objects.create(name='Bundesliga', country='DE')

    def test_create_new_club_job(self):
        resp = self.client.post(reverse('creator_import_create'), data={
            'import_mode': 'new',
            'club_name': NEW_CLUB_NAME,
            'league': self.league.pk,
            'tm_club_id': NEW_TM_CLUB_ID,
        })
        self.assertEqual(resp.status_code, 302)

        club = Club.objects.get(transfermarkt_id=NEW_TM_CLUB_ID)
        self.assertEqual(club.name, NEW_CLUB_NAME)
        self.assertFalse(club.is_import_placeholder)
        self.assertEqual(club.league, self.league)

        job = ClubPlayerImportJob.objects.get(ws_club=club)
        self.assertEqual(job.tm_club_id, NEW_TM_CLUB_ID)
        self.assertEqual(job.status, ClubPlayerImportJob.STATUS_PENDING)

    def test_new_club_requires_name_and_league(self):
        resp = self.client.post(reverse('creator_import_create'), data={
            'import_mode': 'new',
            'club_name': '',
            'league': self.league.pk,
            'tm_club_id': NEW_TM_CLUB_ID,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ClubPlayerImportJob.objects.exists())
        self.assertFalse(
            Club.objects.filter(transfermarkt_id=NEW_TM_CLUB_ID).exists())

    def test_existing_real_club_rejected_in_new_mode(self):
        Club.objects.create(
            name=NEW_CLUB_NAME, short_name='HSV', founded_year=1887,
            budget=Decimal('25000000'), league=self.league,
            transfermarkt_id=NEW_TM_CLUB_ID, is_import_placeholder=False,
        )
        resp = self.client.post(reverse('creator_import_create'), data={
            'import_mode': 'new',
            'club_name': NEW_CLUB_NAME,
            'league': self.league.pk,
            'tm_club_id': NEW_TM_CLUB_ID,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ClubPlayerImportJob.objects.exists())

    def test_existing_mode_still_works(self):
        club = Club.objects.create(
            name='Bestandsverein', short_name='BV', founded_year=1900,
            budget=Decimal('5000000'), league=self.league,
        )
        resp = self.client.post(reverse('creator_import_create'), data={
            'import_mode': 'existing',
            'ws_club': club.pk,
            'tm_club_id': 27,
        })
        self.assertEqual(resp.status_code, 302)
        job = ClubPlayerImportJob.objects.get(ws_club=club)
        self.assertEqual(job.tm_club_id, 27)
