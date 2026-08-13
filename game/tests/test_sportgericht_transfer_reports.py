"""Tests für Task #841: Transfermeldungen & Kaderlimit-Vermerke im Sportgericht.

Deckt ab:
1. TransferReport mit UNDER_REVIEW erscheint auf Manager-Sportgericht-Seite
2. POST sportgericht_report_action (close/dismiss) — NUR Staff; close→CONFIRMED,
   dismiss→DISMISSED, jeweils mit Log + Melder-Benachrichtigung
3. Manager (auch mit Verein) kann Meldungen NICHT abschließen (403)
4. SquadLimitNote mit SPORTGERICHT erscheint auf Manager-Sportgericht-Seite
5. POST sportgericht_squad_note_action — NUR Staff
6. Nur eigener Verein sieht seine SquadLimitNotes
7. Creator-Sportgericht zeigt beide Querys
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from game.models import Club, GameSeasonState, League, ManagerProfile, Player
from game.transfer_v2.models import (
    CreatorActionLog,
    SquadLimitNote,
    TransferRecord,
    TransferRecordPlayer,
    TransferReport,
)


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _mk_league():
    return League.objects.get_or_create(
        name='SG841-Testliga', country='Deutschland',
    )[0]


def _mk_club(name, budget='10000000'):
    return Club.objects.create(
        name=name, short_name=name[:3].upper(),
        founded_year=1900, budget=Decimal(budget),
        league=_mk_league(),
    )


def _mk_player(club, name='Test Spieler'):
    first, last = name.split(' ', 1)
    return Player.objects.create(
        club=club, first_name=first, last_name=last,
        age=25, position='Sturm', main_position_1='ST',
        nationalities='Deutschland',
    )


def _mk_manager(club, username):
    user = User.objects.create_user(username=username, password='pw')
    # ManagerProfile wird via Signal angelegt; wir holen es
    profile = ManagerProfile.objects.get(user=user)
    profile.name = username.title()
    profile.save()
    club.managed_by = profile
    club.save()
    return user


def _mk_staff(username):
    return User.objects.create_user(username=username, password='pw', is_staff=True)


def _mk_record(club_a, club_b, player):
    record = TransferRecord.objects.create(
        club_a=club_a, club_b=club_b,
        kind=TransferRecord.KIND_CASH,
        date=timezone.now().date(),
        cash_a=Decimal('1000000'),
    )
    TransferRecordPlayer.objects.create(
        record=record, player=player, side=TransferRecordPlayer.SIDE_A,
    )
    return record


# ── Tests ─────────────────────────────────────────────────────────────────────

class SportgerichtTransferReportViewTests(TestCase):
    """Sportgericht-Seite zeigt TransferReport mit UNDER_REVIEW."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club_a = _mk_club('FC Alpha')
        self.club_b = _mk_club('FC Beta')
        self.player = _mk_player(self.club_b)
        self.user = _mk_manager(self.club_a, 'manager_alpha')
        self.record = _mk_record(self.club_a, self.club_b, self.player)
        self.client = Client()
        self.client.login(username='manager_alpha', password='pw')

    def _mk_report(self, status=TransferReport.STATUS_UNDER_REVIEW):
        return TransferReport.objects.create(
            record=self.record,
            reporter_club=self.club_a,
            reason='Verdächtiger Transfer',
            status=status,
        )

    def test_under_review_report_appears_on_sportgericht_page(self):
        """UNDER_REVIEW-Report wird auf der Sportgericht-Seite angezeigt."""
        self._mk_report(TransferReport.STATUS_UNDER_REVIEW)
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('transfer_reports', resp.context)
        ids = [r.pk for r in resp.context['transfer_reports']]
        self.assertEqual(len(ids), 1)

    def test_open_report_not_on_sportgericht_page(self):
        """OPEN-Report erscheint NICHT auf der Sportgericht-Seite."""
        self._mk_report(TransferReport.STATUS_OPEN)
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(list(resp.context['transfer_reports'])), 0)

    def test_dismissed_report_not_on_sportgericht_page(self):
        """DISMISSED-Report erscheint NICHT auf der Sportgericht-Seite."""
        self._mk_report(TransferReport.STATUS_DISMISSED)
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(list(resp.context['transfer_reports'])), 0)

    def test_confirmed_report_not_on_sportgericht_page(self):
        """CONFIRMED-Report erscheint NICHT mehr in der offenen Liste."""
        self._mk_report(TransferReport.STATUS_CONFIRMED)
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(list(resp.context['transfer_reports'])), 0)

    def test_manager_does_not_see_action_buttons(self):
        """Nicht-Staff sieht keine Abschluss-Buttons, nur Hinweis."""
        self._mk_report(TransferReport.STATUS_UNDER_REVIEW)
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertNotContains(resp, 'sportgericht_report_action'.replace('_', '-'), status_code=200)
        self.assertContains(resp, 'Wird vom Sportgericht geprüft.')


class SportgerichtReportActionTests(TestCase):
    """POST sportgericht_report_action: nur Staff, korrekte Status-Übergänge."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club_a = _mk_club('FC Gamma')
        self.club_b = _mk_club('FC Delta')
        self.player = _mk_player(self.club_b)
        self.manager_user = _mk_manager(self.club_a, 'manager_gamma')
        self.staff_user = _mk_staff('staff_gamma')
        self.record = _mk_record(self.club_a, self.club_b, self.player)
        self.staff = Client()
        self.staff.login(username='staff_gamma', password='pw')

    def _mk_report(self):
        return TransferReport.objects.create(
            record=self.record,
            reporter_club=self.club_a,
            reason='Test',
            status=TransferReport.STATUS_UNDER_REVIEW,
        )

    @patch('game.transfer_v2.push.report_resolved')
    def test_close_action_sets_confirmed_and_notifies(self, mock_resolved):
        """action=close → CONFIRMED + resolved_at + Log + Melder-Push."""
        report = self._mk_report()
        resp = self.staff.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'close'},
        )
        self.assertRedirects(resp, reverse('management_sportgericht'))
        report.refresh_from_db()
        self.assertEqual(report.status, TransferReport.STATUS_CONFIRMED)
        self.assertIsNotNone(report.resolved_at)
        self.assertTrue(
            CreatorActionLog.objects.filter(
                action='sportgericht_report_close',
            ).exists()
        )
        mock_resolved.assert_called_once()

    @patch('game.transfer_v2.push.report_resolved')
    def test_dismiss_action_sets_dismissed_and_notifies(self, mock_resolved):
        """action=dismiss → DISMISSED + Melder-Push."""
        report = self._mk_report()
        self.staff.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'dismiss'},
        )
        report.refresh_from_db()
        self.assertEqual(report.status, TransferReport.STATUS_DISMISSED)
        mock_resolved.assert_called_once()

    def test_creator_redirect_target(self):
        """next=creator → Redirect zur Creator-Sportgericht-Seite."""
        report = self._mk_report()
        resp = self.staff.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'close', 'next': 'creator'},
        )
        self.assertRedirects(resp, reverse('creator_sportgericht'))

    def test_wrong_status_report_ignored(self):
        """Meldung mit Status OPEN kann nicht abgeschlossen werden."""
        report = TransferReport.objects.create(
            record=self.record,
            reporter_club=self.club_a,
            reason='Test',
            status=TransferReport.STATUS_OPEN,
        )
        self.staff.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'close'},
        )
        report.refresh_from_db()
        # Status unverändert
        self.assertEqual(report.status, TransferReport.STATUS_OPEN)

    def test_manager_with_club_gets_403(self):
        """Manager MIT Verein darf Meldungen NICHT abschließen (Cross-Club-Schutz)."""
        report = self._mk_report()
        c = Client()
        c.login(username='manager_gamma', password='pw')
        resp = c.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'close'},
        )
        self.assertEqual(resp.status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.status, TransferReport.STATUS_UNDER_REVIEW)

    def test_foreign_manager_gets_403(self):
        """Manager eines fremden Vereins darf ebenfalls nicht abschließen."""
        report = self._mk_report()
        _mk_manager(self.club_b, 'manager_delta')
        c = Client()
        c.login(username='manager_delta', password='pw')
        resp = c.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'dismiss'},
        )
        self.assertEqual(resp.status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.status, TransferReport.STATUS_UNDER_REVIEW)

    def test_no_club_manager_gets_403(self):
        """Nicht-Staff ohne Verein bekommt 403."""
        clubless_user = User.objects.create_user('clubless841', password='pw')
        c = Client()
        c.login(username='clubless841', password='pw')
        report = self._mk_report()
        resp = c.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'close'},
        )
        self.assertEqual(resp.status_code, 403)


class SportgerichtSquadLimitNoteViewTests(TestCase):
    """Sportgericht-Seite zeigt SquadLimitNote mit SPORTGERICHT-Status."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club = _mk_club('FC Epsilon')
        self.other_club = _mk_club('FC Zeta')
        self.player = _mk_player(self.club)
        self.user = _mk_manager(self.club, 'manager_epsilon')
        self.client = Client()
        self.client.login(username='manager_epsilon', password='pw')

    def test_sportgericht_note_appears_for_own_club(self):
        """SquadLimitNote mit SPORTGERICHT des eigenen Vereins wird angezeigt."""
        note = SquadLimitNote.objects.create(
            club=self.club,
            player=self.player,
            text='Kaderlimit überschritten',
            status=SquadLimitNote.STATUS_SPORTGERICHT,
        )
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('squad_limit_notes', resp.context)
        ids = [n.pk for n in resp.context['squad_limit_notes']]
        self.assertIn(note.pk, ids)

    def test_open_note_not_shown(self):
        """SquadLimitNote mit OPEN-Status erscheint nicht."""
        SquadLimitNote.objects.create(
            club=self.club,
            text='Nur offen',
            status=SquadLimitNote.STATUS_OPEN,
        )
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertEqual(len(list(resp.context['squad_limit_notes'])), 0)

    def test_other_club_note_not_visible_to_manager(self):
        """SquadLimitNote eines fremden Vereins ist nicht sichtbar."""
        SquadLimitNote.objects.create(
            club=self.other_club,
            text='Fremdverein',
            status=SquadLimitNote.STATUS_SPORTGERICHT,
        )
        resp = self.client.get(reverse('management_sportgericht'))
        self.assertEqual(len(list(resp.context['squad_limit_notes'])), 0)


class SportgerichtSquadNoteActionTests(TestCase):
    """POST sportgericht_squad_note_action: nur Staff."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club = _mk_club('FC Eta')
        self.other_club = _mk_club('FC Theta')
        self.manager_user = _mk_manager(self.club, 'manager_eta')
        self.staff_user = _mk_staff('staff_eta')
        self.staff = Client()
        self.staff.login(username='staff_eta', password='pw')

    def _mk_note(self, club=None):
        return SquadLimitNote.objects.create(
            club=club or self.club,
            text='Kaderüberschreitung',
            status=SquadLimitNote.STATUS_SPORTGERICHT,
        )

    def test_staff_close_note_sets_open(self):
        """Staff-POST → Status wird zu OPEN + Log-Eintrag."""
        note = self._mk_note()
        resp = self.staff.post(
            reverse('sportgericht_squad_note_action'),
            {'note_id': note.pk},
        )
        self.assertRedirects(resp, reverse('management_sportgericht'))
        note.refresh_from_db()
        self.assertEqual(note.status, SquadLimitNote.STATUS_OPEN)
        self.assertTrue(
            CreatorActionLog.objects.filter(
                action='sportgericht_squad_note_close',
            ).exists()
        )

    def test_manager_cannot_close_own_note(self):
        """Auch der eigene Manager darf den Vermerk nicht selbst schließen."""
        note = self._mk_note()
        c = Client()
        c.login(username='manager_eta', password='pw')
        resp = c.post(
            reverse('sportgericht_squad_note_action'),
            {'note_id': note.pk},
        )
        self.assertEqual(resp.status_code, 403)
        note.refresh_from_db()
        self.assertEqual(note.status, SquadLimitNote.STATUS_SPORTGERICHT)

    def test_no_club_manager_gets_403(self):
        """Nicht-Staff ohne Verein bekommt 403."""
        clubless_user = User.objects.create_user('clubless841b', password='pw')
        c = Client()
        c.login(username='clubless841b', password='pw')
        note = self._mk_note()
        resp = c.post(
            reverse('sportgericht_squad_note_action'),
            {'note_id': note.pk},
        )
        self.assertEqual(resp.status_code, 403)


class CreatorSportgerichtTransferReportsTests(TestCase):
    """Creator-Sportgericht zeigt UNDER_REVIEW-Reports und SPORTGERICHT-Notes."""

    def setUp(self):
        GameSeasonState.objects.create(current_season=0)
        self.club_a = _mk_club('FC Iota')
        self.club_b = _mk_club('FC Kappa')
        self.player = _mk_player(self.club_b)
        self.staff_user = _mk_staff('staff841')
        self.client = Client()
        self.client.login(username='staff841', password='pw')
        self.record = _mk_record(self.club_a, self.club_b, self.player)

    def test_creator_sportgericht_shows_under_review_report(self):
        TransferReport.objects.create(
            record=self.record,
            reporter_club=self.club_a,
            reason='Prüfen',
            status=TransferReport.STATUS_UNDER_REVIEW,
        )
        resp = self.client.get(reverse('creator_sportgericht'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('transfer_reports', resp.context)
        self.assertEqual(len(list(resp.context['transfer_reports'])), 1)

    def test_creator_sportgericht_shows_sportgericht_notes(self):
        SquadLimitNote.objects.create(
            club=self.club_a,
            text='Überschreitung',
            status=SquadLimitNote.STATUS_SPORTGERICHT,
        )
        resp = self.client.get(reverse('creator_sportgericht'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('squad_limit_notes_sg', resp.context)
        self.assertEqual(len(list(resp.context['squad_limit_notes_sg'])), 1)

    @patch('game.transfer_v2.push.report_resolved')
    def test_creator_can_close_report(self, mock_resolved):
        """Creator (Staff) schließt Meldung über den gemeinsamen Endpoint ab."""
        report = TransferReport.objects.create(
            record=self.record,
            reporter_club=self.club_a,
            reason='Test',
            status=TransferReport.STATUS_UNDER_REVIEW,
        )
        resp = self.client.post(
            reverse('sportgericht_report_action'),
            {'report_id': report.pk, 'action': 'close', 'next': 'creator'},
        )
        self.assertRedirects(resp, reverse('creator_sportgericht'))
        report.refresh_from_db()
        self.assertEqual(report.status, TransferReport.STATUS_CONFIRMED)
        mock_resolved.assert_called_once()
