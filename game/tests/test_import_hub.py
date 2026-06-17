"""Smoke-Tests für den geführten Import-Hub im Creator-Mode.

Sichert die Verdrahtung der Hub-Seite und der „Weiter zu Schritt X"-Navigation
gegen künftige Routen-Regressionen ab. Enthält außerdem einen End-to-End-Test,
der prüft, dass Defekte aus einer CSV nach dem echten Import in der done-Ansicht
korrekt als Fehler/Warnungen angezeigt werden.
"""
import csv
import io
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from game.models import Club, League


class ImportHubTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='hubuser', password='pw12345', is_staff=True,
        )
        self.client.force_login(self.user)

    def test_hub_requires_login(self):
        """Ohne Login leitet der Hub auf die Anmeldung um."""
        self.client.logout()
        resp = self.client.get(reverse('creator_import_hub'))
        self.assertEqual(resp.status_code, 302)

    def test_hub_lists_all_three_steps(self):
        """Die Hub-Seite verlinkt alle drei Import-Flows in der Reihenfolge."""
        resp = self.client.get(reverse('creator_import_hub'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn(reverse('creator_import_index'), html)
        self.assertIn(reverse('creator_fmid_csv_import'), html)
        self.assertIn(reverse('creator_sofifa_import'), html)

    def test_all_routes_resolve(self):
        """Alle im Hub-Ablauf genutzten Routen lösen sauber auf."""
        self.assertEqual(reverse('creator_import_hub'), '/creator/import/hub/')
        self.assertEqual(reverse('creator_import_index'), '/creator/import/')
        self.assertEqual(reverse('creator_fmid_csv_import'), '/creator/import/fmids/')
        self.assertEqual(reverse('creator_sofifa_import'), '/creator/import/sofifa/')


# ── CSV-Helfer ────────────────────────────────────────────────────────────────

_DEFECT_CSV_COLS = (
    'club_name,club_short_name,founded_year,club_city,country,latitude,'
    'longitude,fmi_club_id,tm_club_id,stadium_name,stadium_city,'
    'stadium_capacity,season_id,season_label,ws_club,real_club,'
    'loaned_from,squad_status,fm_unique_id,tm_player_id,tm_url,fmi_url,'
    'sofifa_id,sofifa_url,first_name,last_name,display_name,'
    'date_of_birth,height_cm,preferred_foot,primary_nationality,'
    'nationalities,tm_market_value_eur,hp_positions,np_positions,'
    'position_method,fmi_rating,fmi_potential'
).split(',')


def _build_defect_csv(club_name):
    """Baut eine Mini-CSV mit einem Spieler, der ``fmi_rating`` gesetzt hat,
    aber keine FMI-Attribute enthält.  Das löst ``rating_without_attrs``
    (LEVEL_ERROR) aus, ohne den Import zu blockieren."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_DEFECT_CSV_COLS)
    writer.writeheader()
    row = {c: '' for c in _DEFECT_CSV_COLS}
    row.update({
        'club_name': club_name, 'club_short_name': 'TFC',
        'founded_year': '2000', 'club_city': 'Teststadt',
        'country': 'Deutschland', 'latitude': '48.137', 'longitude': '11.576',
        'stadium_name': 'Teststadion', 'stadium_city': 'Teststadt',
        'stadium_capacity': '5000',
        'season_id': '2025', 'season_label': '2025/26',
        'ws_club': club_name,
        'squad_status': 'first_team', 'fm_unique_id': '42001',
        'tm_player_id': '55001',
        'first_name': 'Defekt', 'last_name': 'Spieler',
        'display_name': 'Defekt Spieler',
        'date_of_birth': '1995-06-01', 'height_cm': '182',
        'preferred_foot': 'rechts', 'primary_nationality': 'Germany',
        'nationalities': 'Germany', 'tm_market_value_eur': '500000',
        'hp_positions': 'ST',
        'fmi_rating': '60',   # rating gesetzt, aber keine fmi_* Attribute-Spalten
        'fmi_potential': '',  # kein Potential → allow_missing=True in parsed-Validator
    })
    writer.writerow(row)
    return buf.getvalue()


# ── End-to-End-Test: Defekte in der done-Ansicht ──────────────────────────────

class ClubCsvImportDefectsUITest(TestCase):
    """Prüft, dass Defekte einer CSV nach dem echten Import (dry_run=False) in
    der done-Ansicht als error_count > 0, Spielername in der Tabelle und
    nicht-blockierender Hinweis korrekt angezeigt werden."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='csvuser', password='pw12345', is_staff=True,
        )
        self.client.force_login(self.user)
        league = League.objects.create(name='Testliga', country='DE')
        self.club = Club.objects.create(
            name='Test FC', short_name='TFC', founded_year=2000,
            budget=Decimal('0'), league=league,
        )

    def _do_preview(self, url, csv_text):
        """Schritt 1: Dry-Run/Vorschau – speichert die CSV in der Session."""
        csv_file = SimpleUploadedFile(
            'defect.csv', csv_text.encode('utf-8'), content_type='text/csv',
        )
        return self.client.post(url, {
            'action': 'preview', 'mode': 'full', 'csv_file': csv_file,
        })

    def test_defects_visible_in_done_view(self):
        """done-Schritt: error_count > 0, Spielername in Tabelle, Nicht-blockierend-Hinweis."""
        url = reverse('creator_club_csv_import')
        csv_text = _build_defect_csv('Test FC')

        # Schritt 1: Preview – legt CSV-Text in der Session ab
        preview_resp = self._do_preview(url, csv_text)
        self.assertEqual(preview_resp.status_code, 200,
                         'Preview-Schritt muss HTTP 200 zurückgeben.')
        self.assertNotIn('upload_error', preview_resp.context or {},
                         'Preview darf keinen upload_error setzen.')

        # Schritt 2: Echter Import bestätigen
        resp = self.client.post(url, {'action': 'confirm', 'mode': 'full'})
        self.assertEqual(resp.status_code, 200)

        ctx = resp.context
        html = resp.content.decode('utf-8')

        # done-Schritt wurde gerendert
        self.assertEqual(ctx['step'], 'done',
                         'Nach dem Confirm muss step="done" im Kontext stehen.')

        # Mindestens ein LEVEL_ERROR muss vorliegen (rating_without_attrs)
        self.assertGreater(
            ctx['error_count'], 0,
            'Eine CSV mit fmi_rating ohne Attribute muss error_count > 0 liefern.',
        )

        # Spielername erscheint in der Fehler-Tabelle (als issue.ref)
        self.assertIn(
            'Defekt Spieler', html,
            'Der Spielername muss in der Defekt-Tabelle der done-Ansicht sichtbar sein.',
        )

        # Nicht-blockierender Hinweis muss gerendert werden
        self.assertIn(
            'Nicht-blockierend', html,
            'Der nicht-blockierende Hinweis muss bei error_count > 0 angezeigt werden.',
        )

        # Kein error_skipped_players ohne Checkbox
        self.assertEqual(
            ctx.get('error_skipped_players', []), [],
            'Ohne skip-Checkbox darf error_skipped_players leer sein.',
        )

    def test_skip_error_players_excludes_defect_from_import(self):
        """Mit skip_error_players=on werden fehlerhafte Spieler nicht importiert,
        tauchen aber in error_skipped_players auf; error_count bleibt > 0."""
        url = reverse('creator_club_csv_import')
        csv_text = _build_defect_csv('Test FC')

        # Schritt 1: Preview – legt CSV in der Session ab
        preview_resp = self._do_preview(url, csv_text)
        self.assertEqual(preview_resp.status_code, 200,
                         'Preview-Schritt muss HTTP 200 zurückgeben.')
        self.assertNotIn('upload_error', preview_resp.context or {},
                         'Preview darf keinen upload_error setzen.')

        # Schritt 2: Import mit aktivierter Skip-Checkbox
        resp = self.client.post(url, {
            'action': 'confirm',
            'mode': 'full',
            'skip_error_players': 'on',
        })
        self.assertEqual(resp.status_code, 200)

        ctx = resp.context
        html = resp.content.decode('utf-8')

        self.assertEqual(ctx['step'], 'done',
                         'Nach dem Confirm muss step="done" im Kontext stehen.')

        # Validierungsfehler bleiben sichtbar (error_count > 0)
        self.assertGreater(
            ctx['error_count'], 0,
            'error_count muss auch beim Überspringen > 0 bleiben (Validierung unberührt).',
        )

        # Spieler muss in error_skipped_players auftauchen
        self.assertIn(
            'Defekt Spieler', ctx.get('error_skipped_players', []),
            'Der übersprungene Spieler muss in error_skipped_players stehen.',
        )

        # Spieler muss in der übersprungenen-Liste im HTML erscheinen
        self.assertIn(
            'Übersprungene Spieler (Fehler', html,
            'Der Fehler-übersprungen-Abschnitt muss im HTML erscheinen.',
        )
        self.assertIn(
            'Defekt Spieler', html,
            'Der Spielername muss in der Fehler-übersprungen-Liste erscheinen.',
        )

        # Und der separate Counter (Fehler übersprungen) muss vorhanden sein
        self.assertIn(
            'Fehler übersprungen', html,
            'Der Zähler „Fehler übersprungen" muss im done-Schritt erscheinen.',
        )


# ── Persistenz: validation_issues am Job-Objekt ───────────────────────────────

class ValidationIssuesPersistenceTest(TestCase):
    """Prüft, dass validation_issues nach dem Import dauerhaft am Job stehen."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='persist_user', password='pw12345', is_staff=True,
        )
        self.client.force_login(self.user)
        league = League.objects.create(name='Persistenzliga', country='DE')
        self.club = Club.objects.create(
            name='Persist FC', short_name='PFC', founded_year=1999,
            budget=Decimal('0'), league=league,
        )

    def _run_import(self, club_name):
        url = reverse('creator_club_csv_import')
        csv_text = _build_defect_csv(club_name)
        csv_file = SimpleUploadedFile(
            'persist.csv', csv_text.encode('utf-8'), content_type='text/csv',
        )
        self.client.post(url, {'action': 'preview', 'mode': 'full', 'csv_file': csv_file})
        return self.client.post(url, {'action': 'confirm', 'mode': 'full'})

    def test_validation_issues_saved_on_job(self):
        """Nach dem Import muss validation_issues am Job-Objekt gesetzt sein."""
        from game.models import ClubPlayerImportJob
        self._run_import('Persist FC')
        job = ClubPlayerImportJob.objects.filter(ws_club=self.club).latest('created_at')
        self.assertIsInstance(job.validation_issues, list)
        self.assertGreater(
            len(job.validation_issues), 0,
            'Job muss nach Import mit Defekt-CSV mindestens ein Issue gespeichert haben.',
        )
        levels = {i['level'] for i in job.validation_issues}
        self.assertIn('error', levels, 'Mindestens ein LEVEL_ERROR muss im Job stehen.')

    def test_import_detail_shows_saved_issues(self):
        """creator_import_detail zeigt gespeicherte Issues für abgeschlossene Jobs."""
        from game.models import ClubPlayerImportJob
        self._run_import('Persist FC')
        job = ClubPlayerImportJob.objects.filter(ws_club=self.club).latest('created_at')

        resp = self.client.get(
            reverse('creator_import_detail', args=[job.pk])
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn(
            'Defekt Spieler', html,
            'import_detail muss Spielernamen aus gespeicherten Issues anzeigen.',
        )
        self.assertIn(
            'Nicht-blockierend', html,
            'import_detail muss den nicht-blockierenden Hinweis rendern.',
        )
