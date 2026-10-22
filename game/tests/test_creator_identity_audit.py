import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from game import models as m
from game.club_import.identity_audit import audit_player_identities
from game.club_import.identity_audit_display import club_identity_audit_context
from game.tests.test_package_lifecycle import fingerprint
from game.views_creator import creator_club_edit


class CreatorIdentityAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user("identity-creator", is_staff=True)
        cls.user = get_user_model().objects.create_user("identity-manager")
        league = m.League.objects.create(name="Identitäts-Prüfliga", country="Deutschland")
        cls.clubs = [
            m.Club.objects.create(name=name, founded_year=1900, budget=0, league=league)
            for name in ("Aktueller Verein", "Fremdverein", "Rekordverein", "Ohne Befund")
        ]
        cls.first = m.Player.objects.create(
            first_name="Erste", last_name="Identität", age=25, club=cls.clubs[0],
            transfermarkt_id=1140001, date_of_birth=date(2000, 1, 1))
        cls.second = m.Player.objects.create(
            first_name="Fremde", last_name="Identität", age=25, club=cls.clubs[1],
            fm_inside_id=1140002, transfermarkt_id=1140003)
        cls.person = m.HistoricCoach.objects.create(
            name="Rekordperson", person_kind="spieler", linked_player=cls.first,
            birth_date=date(1999, 1, 1))
        for code, value in (("TM", "1140001"), ("FM", "1140002")):
            source, _ = m.DataSource.objects.get_or_create(code=code, defaults={"name": code})
            m.PlayerExternalId.objects.create(
                person=cls.person, source=source, external_id=value, identity_kind="spieler",
                source_url="https://example.org/original", profile_url="https://example.org/profile",
                match_evidence={"note": "<script>alert('source')</script>"})
        cls.record = m.ClubRecord.objects.create(
            club=cls.clubs[2], record_key="most_appearances", source="SEED",
            value_numeric=200, value_display="200 Einsätze", holder_name=cls.person.name,
            holder_coach=cls.person, source_note="Archivbeleg", context_line="Rekordkontext")
        cls.report = audit_player_identities()

    def url(self, club=None):
        return reverse("creator_club_edit", args=[(club or self.clubs[0]).pk]) + "?tab=identitaeten"

    def save_snapshot(self, report=None):
        return m.PlayerIdentityAuditSnapshot.objects.create(
            generated_at=timezone.now(), report=report or self.report)

    def view(self, club=None, query=None):
        club = club or self.clubs[0]
        request = RequestFactory().get(self.url(club), query or {})
        request.user = self.staff
        return creator_club_edit(request, club.pk)

    def test_access_requires_active_staff_and_rejects_mutating_methods(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url()), "Identitätsbefunde")
        self.assertEqual(self.client.post(self.url(), {"repair": "1"}).status_code, 405)
        self.staff.is_active = False
        self.staff.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_absent_snapshot_is_explicit_and_does_not_scan_or_write(self):
        before = fingerprint()
        with patch("game.club_import.identity_audit.audit_player_identities",
                   side_effect=AssertionError("No scans in a GET")):
            with CaptureQueriesContext(connection) as queries:
                response = self.view()
        self.assertContains(response, "Noch kein gespeicherter Prüfbericht")
        self.assertContains(response, "audit_player_identities --save")
        self.assertNotContains(response, "keine relevanten Befunde")
        after = fingerprint()
        self.assertEqual([key for key in before if before[key] != after[key]], [])
        self.assertEqual([q["sql"] for q in queries
                          if not q["sql"].lstrip().upper().startswith("SELECT")], [])
        self.assertFalse(m.ClubPublicProfile.objects.filter(club=self.clubs[0]).exists())

    def test_each_club_keeps_entire_component_and_all_foreign_evidence(self):
        self.save_snapshot()
        for club in self.clubs[:3]:
            with self.subTest(club=club.name):
                context = club_identity_audit_context(club.pk, None)
                self.assertEqual(context["identity_page"].paginator.count, 1)
                finding = context["identity_page"][0]
                for field in ("players", "people", "problems", "evidence",
                              "canonical_rows", "record_references"):
                    self.assertEqual(finding[field], self.report["findings"][0][field])
                codes = {problem["code"] for problem in finding["problems"]}
                self.assertTrue({"split_identity", "conflicting_ids",
                                 "conflicting_birth_dates"} <= codes)
                response = self.view(club)
                for text in ("Fremde", "Rekordperson", "Archivbeleg", "200 Einsätze",
                             "https://example.org/original", "https://example.org/profile",
                             "1140003", "Prüfstand:", "keine Live-Prüfung"):
                    self.assertContains(response, text)
                self.assertNotContains(response, "<script>alert('source')</script>")
                self.assertContains(response, "&lt;script&gt;")

    def test_saved_gets_are_select_only_and_never_import_or_scan(self):
        self.save_snapshot()
        before = fingerprint()
        with patch("game.club_import.identity_audit.audit_player_identities",
                   side_effect=AssertionError("No scans")), patch(
                       "game.club_import.package_service.apply_package",
                       side_effect=AssertionError("No imports")):
            with CaptureQueriesContext(connection) as queries:
                for _ in range(2):
                    self.assertEqual(self.view().status_code, 200)
        self.assertEqual([q["sql"] for q in queries
                          if not q["sql"].lstrip().upper().startswith("SELECT")], [])
        self.assertEqual(fingerprint(), before)
        self.assertEqual(m.PlayerIdentityAuditSnapshot.objects.count(), 1)

    def test_snapshot_not_live_and_no_findings_state_is_distinct(self):
        self.save_snapshot()
        self.first.club = self.clubs[3]
        self.first.save(update_fields=["club"])
        self.assertContains(self.view(self.clubs[0]), "Erste")
        self.assertContains(self.view(self.clubs[3]), "keine relevanten Befunde")

    def test_owner_and_loan_clubs_also_select_complete_findings(self):
        self.first.owner_club = self.clubs[3]
        self.first.loan_club = self.clubs[2]
        self.first.save(update_fields=["owner_club", "loan_club"])
        self.save_snapshot(audit_player_identities())
        context = club_identity_audit_context(self.clubs[3].pk, 1)
        self.assertEqual(context["identity_page"].paginator.count, 1)
        self.assertEqual(len(context["identity_page"][0]["players"]), 2)

    def test_pagination_is_by_complete_finding_and_handles_invalid_pages(self):
        report = dict(self.report, findings=self.report["findings"] * 21)
        self.save_snapshot(report)
        for page_number, expected_page, expected_length in (("invalid", 1, 20), ("999", 2, 1)):
            page = club_identity_audit_context(self.clubs[0].pk, page_number)["identity_page"]
            self.assertEqual(page.number, expected_page)
            self.assertEqual(len(page), expected_length)
            self.assertEqual(len(page[0]["players"]), 2)
        self.assertContains(self.view(query={"tab": "identitaeten", "page": "2"}), "Seite 2 von 2")

    def test_explicit_save_replaces_only_report_and_keeps_json_output(self):
        before = fingerprint()
        stdout = StringIO()
        call_command("audit_player_identities", save=True, format="json", stdout=stdout)
        snapshot = m.PlayerIdentityAuditSnapshot.objects.get(pk=1)
        self.assertEqual(snapshot.report, json.loads(stdout.getvalue()))
        after = fingerprint()
        snapshot_table = m.PlayerIdentityAuditSnapshot._meta.db_table
        self.assertEqual({k: v for k, v in before.items() if k != snapshot_table},
                         {k: v for k, v in after.items() if k != snapshot_table})
        call_command("audit_player_identities", save=True, stdout=StringIO())
        self.assertEqual(m.PlayerIdentityAuditSnapshot.objects.count(), 1)
        with patch("game.management.commands.audit_player_identities.audit_player_identities",
                   side_effect=RuntimeError("scan failed")):
            with self.assertRaises(RuntimeError):
                call_command("audit_player_identities", save=True, stdout=StringIO())
        self.assertEqual(m.PlayerIdentityAuditSnapshot.objects.get(pk=1).report, snapshot.report)
