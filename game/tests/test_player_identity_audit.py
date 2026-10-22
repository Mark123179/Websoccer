"""Inventory audits must not exercise write-and-rollback import dry runs."""
import json
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from game import models as m
from game.club_import.identity_audit import audit_player_identities
from game.tests.test_package_lifecycle import fingerprint


class PlayerIdentityAuditTests(TestCase):
    def player(self, **kwargs):
        return m.Player.objects.create(first_name="Aktiv", last_name="Spieler", age=25, **kwargs)

    def person(self, **kwargs):
        return m.HistoricCoach.objects.create(name="Rekordperson", person_kind="spieler", **kwargs)

    def external(self, owner, code, value, **kwargs):
        source, _ = m.DataSource.objects.get_or_create(code=code, defaults={"name": code})
        key = "player" if isinstance(owner, m.Player) else "person"
        return m.PlayerExternalId.objects.create(
            **{key: owner}, source=source, external_id=value, identity_kind="spieler",
            source_url="https://example.org/original", match_evidence={"original": True},
            **kwargs)

    def codes(self, report=None):
        return {p["code"] for f in (report or audit_player_identities())["findings"]
                for p in f["problems"]}

    def test_healthy_person_owned_ids_satisfy_active_mirrors(self):
        before_count = m.Player.objects.count()
        player = self.player(transfermarkt_id=1136001, fm_inside_id=1136002)
        person = self.person(linked_player=player, fm_inside_id="1136002")
        self.external(person, "TM", "1136001")
        self.external(person, "FM", "1136002")
        self.external(person, "CMTRACKER", "1136003")
        report = audit_player_identities()
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["summary"]["players_scanned"], before_count + 1)

    def test_healthy_active_owned_id_also_satisfies_linked_historical_mirror(self):
        player = self.player(fm_inside_id=1136001)
        self.person(linked_player=player, fm_inside_id="1136001")
        self.external(player, "FM", "1136001")
        self.assertEqual(audit_player_identities()["findings"], [])

    def test_unlinked_shared_id_has_concrete_evidence_and_keeps_record(self):
        player = self.player(transfermarkt_id=1136001)
        person = self.person()
        external = self.external(person, "TM", "1136001")
        league = m.League.objects.create(name="Prüfliga", country="Deutschland")
        club = m.Club.objects.create(
            name="Historischer Verein", founded_year=1900, budget=0, league=league)
        record = m.ClubRecord.objects.create(
            club=club, record_key="most_appearances", source="SEED",
            value_numeric=200, value_display="200", holder_name=person.name,
            holder_coach=person)
        before = fingerprint()
        with CaptureQueriesContext(connection) as queries:
            report = audit_player_identities()
        self.assertEqual(len(queries), 4)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        self.assertEqual(fingerprint(), before)
        finding = report["findings"][0]
        self.assertIn("unlinked_person", self.codes(report))
        self.assertIn("missing_canonical", self.codes(report))
        self.assertEqual(finding["players"][0]["id"], player.pk)
        self.assertEqual(finding["canonical_rows"][0]["id"], external.pk)
        self.assertEqual(finding["canonical_rows"][0]["source_url"], "https://example.org/original")
        self.assertEqual(finding["record_references"][0]["id"], record.pk)
        person.refresh_from_db()
        self.assertIsNone(person.linked_player_id)
        record.refresh_from_db()
        self.assertEqual(record.holder_coach_id, person.pk)

    def test_split_identity_across_active_owners(self):
        first = self.player(transfermarkt_id=1136001)
        second = self.player(fm_inside_id=1136002)
        person = self.person(linked_player=first)
        self.external(person, "TM", "1136001")
        self.external(person, "FM", "1136002")
        self.external(second, "CMTRACKER", "1136003")
        report = audit_player_identities()
        self.assertIn("split_identity", self.codes(report))
        self.assertEqual({p["id"] for p in report["findings"][0]["players"]},
                         {first.pk, second.pk})

    def test_canonical_active_owner_differs_from_mirror_owner(self):
        first = self.player(transfermarkt_id=1136001)
        second = self.player()
        self.external(second, "TM", "1136001")
        self.assertIn("split_identity", self.codes())

    def test_linked_known_conflicts_and_missing_values_are_distinct(self):
        player = self.player(transfermarkt_id=1136001, date_of_birth=date(1999, 1, 1))
        person = self.person(linked_player=player, birth_date=date(1998, 1, 1))
        self.external(person, "TM", "1136002")
        self.assertIn("conflicting_ids", self.codes())
        self.assertIn("conflicting_birth_dates", self.codes())
        person.birth_date = None
        person.save(update_fields=["birth_date"])
        self.assertNotIn("conflicting_birth_dates", self.codes())

    def test_multiple_people_linked_to_one_player(self):
        player = self.player()
        self.person(linked_player=player)
        self.person(linked_player=player)
        self.assertIn("multiple_people", self.codes())

    def test_missing_active_mirror_and_historical_canonical_evidence(self):
        player = self.player()
        self.external(player, "API_FOOTBALL", "1136001")
        self.person(fm_inside_id="1136002")
        report = audit_player_identities()
        self.assertEqual(self.codes(report), {"missing_mirror", "missing_canonical"})
        self.assertNotIn("conflicting_ids", self.codes(report))

    def test_historical_only_person_is_not_automatically_an_orphan(self):
        person = self.person()
        self.external(person, "TM", "1136001")
        report = audit_player_identities()
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["summary"]["historical_only_components"], 1)

    def test_names_birth_dates_and_empty_ids_do_not_connect_people(self):
        self.player(date_of_birth=date(1999, 1, 1))
        person = self.person(birth_date=date(1999, 1, 1))
        person.name = "Aktiv Spieler"
        person.save()
        self.external(person, "TM", None)
        self.external(person, "FM", "")
        self.assertEqual(audit_player_identities()["findings"], [])

    def test_trainer_namespace_does_not_match_player_tm(self):
        player = self.player(transfermarkt_id=1136001)
        self.external(player, "TM", "1136001")
        trainer = m.HistoricCoach.objects.create(name="Trainer", person_kind="trainer")
        source = m.DataSource.objects.get(code="TM")
        m.PlayerExternalId.objects.create(
            person=trainer, source=source, external_id="1136001", identity_kind="trainer")
        self.assertEqual(audit_player_identities()["findings"], [])

    def test_wrong_person_kind_keeps_evidence(self):
        trainer = m.HistoricCoach.objects.create(name="Trainer", person_kind="trainer")
        row = self.external(trainer, "TM", "1136001")
        report = audit_player_identities()
        self.assertIn("wrong_kind", self.codes(report))
        self.assertEqual(report["findings"][0]["canonical_rows"][0]["id"], row.pk)

    def test_command_is_deterministic_read_only_and_never_calls_imports(self):
        self.player(transfermarkt_id=1136001)
        before = fingerprint()
        with patch("game.club_import.package_service.apply_package", side_effect=AssertionError(
            "An audit must never import packages"
        )), patch("game.club_import.historical_identity.historical_plan", side_effect=AssertionError(
            "An audit does not require a package"
        )):
            first, second, text = StringIO(), StringIO(), StringIO()
            call_command("audit_player_identities", format="json", stdout=first)
            call_command("audit_player_identities", format="json", stdout=second)
            call_command("audit_player_identities", stdout=text)
        self.assertEqual(first.getvalue(), second.getvalue())
        self.assertTrue(json.loads(first.getvalue())["read_only"])
        self.assertIn("1136001", text.getvalue())
        self.assertIn("rein lesender Prüfbericht", text.getvalue())
        self.assertEqual(fingerprint(), before)

    def test_saved_audit_comparison_tracks_manual_correction_without_queries(self):
        from game.club_import.identity_audit_diff import compare_reports

        player = self.player(transfermarkt_id=1136001, date_of_birth=date(1999, 1, 1))
        person = self.person(linked_player=player, birth_date=date(1998, 1, 1))
        row = self.external(person, "TM", "1136002")
        before = json.loads(json.dumps(audit_player_identities()))
        row.external_id = "1136001"
        row.save(update_fields=["external_id"])
        person.birth_date = None
        person.save(update_fields=["birth_date"])
        after = json.loads(json.dumps(audit_player_identities()))
        saved = fingerprint()
        with CaptureQueriesContext(connection) as queries:
            comparison = compare_reports(before, after)
        self.assertEqual(len(queries), 0)
        self.assertEqual(fingerprint(), saved)
        self.assertEqual(comparison["summary"]["added"], 0)
        self.assertEqual(comparison["summary"]["removed"], 3)
        self.assertEqual(
            {p["problem"]["code"] for p in comparison["findings"]["removed"]},
            {"conflicting_ids", "conflicting_birth_dates", "missing_canonical"},
        )
