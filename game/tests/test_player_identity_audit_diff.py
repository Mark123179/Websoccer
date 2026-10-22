"""Saved, synthetic reports: these tests need neither a database nor packages."""
from copy import deepcopy
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from game.club_import.identity_audit_diff import (
    AuditFormatError, compare_reports, load_report, render_text,
)


def component(pk):
    value = str(1000 + pk)
    return dict(
        players=[dict(id=pk, first_name="Gleicher", last_name="Name",
                      club_id=9, date_of_birth="2000-01-01", transfermarkt_id=int(value))],
        people=[],
        evidence=[dict(owner_type="player", owner_id=pk, provider="TM",
                       value=value, origin="Player.transfermarkt_id")],
        canonical_rows=[], record_references=[],
        problems=[dict(code="missing_canonical", message="Anzeigetext",
                       player_id=pk, provider="TM", value=value)],
    )


def report(*components):
    return dict(schema_version=1, read_only=True, policy="Keine Änderungen",
                summary=dict(affected_components=len(components)), findings=list(components))


def merged(*components):
    result = {key: sum((deepcopy(c[key]) for c in components), [])
              for key in components[0]}
    result["people"].append(dict(id=10, name="Historisch", person_kind="spieler",
                                 birth_date=None, linked_player_id=components[0]["players"][0]["id"]))
    # A historical ID matching the second player's mirror connects the owners.
    result["evidence"].append(dict(owner_type="person", owner_id=10, provider="TM",
                                   value=components[1]["evidence"][0]["value"],
                                   origin="PlayerExternalId", external_row_id=500))
    result["canonical_rows"].append(dict(
        id=500, player_id=None, person_id=10, source__code="TM",
        external_id=components[1]["evidence"][0]["value"], identity_kind="spieler"))
    result["problems"].append(dict(code="split_identity", message="Mehrere Spieler"))
    return result


class PlayerIdentityAuditDiffTests(TestCase):
    def test_reordering_every_list_changes_nothing(self):
        first = report(merged(component(1), component(2)), component(3))
        first["findings"][0]["problems"].append(dict(
            code="conflicting_ids", provider="TM", values=["1001", "1002"]))
        second = deepcopy(first)

        def reverse_lists(value):
            if isinstance(value, list):
                value.reverse()
                for child in value:
                    reverse_lists(child)
            elif isinstance(value, dict):
                for child in value.values():
                    reverse_lists(child)

        reverse_lists(second)
        result = compare_reports(first, second)
        self.assertEqual(result["summary"], dict(
            added=0, unchanged=5, removed=0, assignment_changes=0))
        self.assertEqual(result, compare_reports(second, first))

    def test_display_metadata_does_not_define_identity(self):
        first = report(component(1))
        second = deepcopy(first)
        second["findings"][0]["players"][0].update(first_name="Anders", club_id=99)
        second["findings"][0]["problems"][0]["message"] = "Neuer Text"
        second["findings"][0]["evidence"][0]["source_url"] = "https://example.test/new"
        result = compare_reports(first, second)
        self.assertEqual(result["summary"], dict(
            added=0, unchanged=1, removed=0, assignment_changes=0))

    def test_added_unchanged_removed_have_concrete_evidence(self):
        result = compare_reports(report(component(1), component(2)),
                                 report(component(2), component(3)))
        self.assertEqual(result["summary"], dict(
            added=1, unchanged=1, removed=1, assignment_changes=0))
        for status, owner in (("added", 3), ("unchanged", 2), ("removed", 1)):
            entry = result["findings"][status][0]
            self.assertEqual(entry["problem"]["player_id"], owner)
            self.assertEqual(entry["problem"]["provider"], "TM")
            self.assertEqual(entry["problem"]["value"], str(1000 + owner))
            self.assertTrue(entry["before_components"] or entry["after_components"])

    def test_merge_preserves_owner_specific_problems(self):
        first, second = component(1), component(2)
        result = compare_reports(report(first, second), report(merged(first, second)))
        self.assertEqual(result["summary"], dict(
            added=1, unchanged=2, removed=0, assignment_changes=1))
        change = result["assignment_changes"][0]
        self.assertEqual(change["kind"], "merged")
        self.assertEqual(len(change["before_components"]), 2)
        self.assertEqual(len(change["after_components"]), 1)
        self.assertIn(("owner", "player", 1), change["shared_evidence"])
        self.assertIn(("source_id", "TM", "1002"), change["shared_evidence"])

    def test_split_does_not_claim_all_problems_are_new(self):
        first, second = component(1), component(2)
        result = compare_reports(report(merged(first, second)), report(second, first))
        self.assertEqual(result["summary"], dict(
            added=0, unchanged=2, removed=1, assignment_changes=1))
        self.assertEqual(result["assignment_changes"][0]["kind"], "split")
        self.assertEqual(result["findings"]["removed"][0]["problem"]["code"], "split_identity")

    def test_many_to_many_reassignment_is_explicit(self):
        first = report(merged(component(1), component(2)),
                       merged(component(3), component(4)))
        # Give the second bridge a distinct historic owner.
        for snapshot in first["findings"][1]["people"]:
            snapshot["id"] = 20
        first["findings"][1]["evidence"][-1]["owner_id"] = 20
        first["findings"][1]["canonical_rows"][-1]["person_id"] = 20
        second = report(merged(component(1), component(3)),
                        merged(component(2), component(4)))
        second["findings"][1]["people"][0]["id"] = 20
        second["findings"][1]["evidence"][-1]["owner_id"] = 20
        second["findings"][1]["canonical_rows"][-1]["person_id"] = 20
        result = compare_reports(first, second)
        self.assertEqual(len(result["assignment_changes"]), 1)
        self.assertEqual(result["assignment_changes"][0]["kind"], "reconfigured")
        self.assertEqual(result["summary"]["unchanged"], 4)

    def test_disappearing_conflict_while_component_and_gap_remain(self):
        first = report(merged(component(1), component(2)))
        first["findings"][0]["problems"].append(dict(
            code="conflicting_birth_dates", values=["1999-01-01", "2000-01-01"]))
        first["findings"][0]["people"][0]["birth_date"] = "1999-01-01"
        second = deepcopy(first)
        second["findings"][0]["people"][0]["birth_date"] = None
        second["findings"][0]["problems"].pop()
        result = compare_reports(first, second)
        self.assertEqual(result["summary"], dict(
            added=0, unchanged=3, removed=1, assignment_changes=0))
        self.assertEqual(result["findings"]["removed"][0]["problem"]["code"],
                         "conflicting_birth_dates")
        self.assertIn("kein Reparaturnachweis", result["policy"])

    def test_id_conflict_disappears_and_other_findings_survive(self):
        first = report(merged(component(1), component(2)))
        first["findings"][0]["problems"].append(dict(
            code="conflicting_ids", provider="TM", values=["1001", "1002"]))
        second = report(component(1))
        result = compare_reports(first, second)
        self.assertIn("conflicting_ids", {
            e["problem"]["code"] for e in result["findings"]["removed"]})
        self.assertEqual(result["summary"]["unchanged"], 1)
        self.assertEqual(result["assignment_changes"][0]["kind"], "changed")

    def test_same_problem_code_on_different_owner_is_not_unchanged(self):
        result = compare_reports(report(component(1)), report(component(2)))
        self.assertEqual(result["summary"]["unchanged"], 0)
        self.assertEqual(result["summary"]["added"], 1)
        self.assertEqual(result["summary"]["removed"], 1)

    def test_same_source_id_reassigned_to_new_owner_is_traceable(self):
        first, second = component(1), component(2)
        second["evidence"][0]["value"] = "1001"
        second["problems"][0]["value"] = "1001"
        result = compare_reports(report(first), report(second))
        self.assertEqual(result["assignment_changes"][0]["kind"], "changed")
        self.assertEqual(result["summary"]["unchanged"], 0)

    def test_source_namespace_and_owner_type_are_not_conflated(self):
        first, second = component(1), component(2)
        second["evidence"][0].update(provider="FM", value="1001")
        self.assertEqual(compare_reports(report(first), report(second))["assignment_changes"], [])
        second["players"] = []
        second["people"] = [dict(id=1, linked_player_id=None, birth_date=None)]
        second["evidence"][0].update(owner_type="person", owner_id=1)
        self.assertEqual(compare_reports(report(first), report(second))["assignment_changes"], [])

    def test_duplicate_codes_keep_independent_provider_and_value(self):
        first = report(component(1))
        first["findings"][0]["problems"].append(dict(
            code="missing_canonical", player_id=1, provider="FM", value="2001"))
        second = deepcopy(first)
        second["findings"][0]["problems"][-1]["value"] = "2002"
        result = compare_reports(first, second)
        self.assertEqual(result["summary"]["unchanged"], 1)
        self.assertEqual(result["summary"]["added"], 1)
        self.assertEqual(result["summary"]["removed"], 1)

    def test_empty_and_fully_disappeared_reports(self):
        self.assertEqual(compare_reports(report(), report())["summary"], dict(
            added=0, unchanged=0, removed=0, assignment_changes=0))
        result = compare_reports(report(component(1)), report())
        self.assertEqual(result["summary"]["removed"], 1)
        # A healthy component is not exported. Never infer deletion/merge from absence.
        self.assertEqual(result["assignment_changes"], [])

    def test_recreated_canonical_row_uses_owner_source_and_id_not_row_order(self):
        first = report(component(1))
        first["findings"][0]["canonical_rows"] = [dict(
            id=50, player_id=1, person_id=None, identity_kind="trainer",
            source__code="TM", external_id="777")]
        first["findings"][0]["problems"] = [dict(
            code="wrong_kind", external_row_id=50, identity_kind="trainer")]
        second = deepcopy(first)
        second["findings"][0]["canonical_rows"][0].update(id=60, source_url="changed")
        second["findings"][0]["problems"][0]["external_row_id"] = 60
        result = compare_reports(first, second)
        self.assertEqual(result["summary"]["unchanged"], 1)
        self.assertEqual(result["assignment_changes"], [])

    def test_reports_are_not_mutated(self):
        first, second = report(component(1)), report(component(2))
        saved = deepcopy((first, second))
        compare_reports(first, second)
        self.assertEqual((first, second), saved)

    def test_incompatible_or_missing_schema_versions_are_rejected_on_either_side(self):
        for version in (None, 0, 2, "1", True):
            invalid = dict(report(), schema_version=version)
            for first, second in ((invalid, report()), (report(), invalid)):
                with self.subTest(version=version), self.assertRaisesRegex(
                        AuditFormatError, "schema_version.*erwartet wird 1"):
                    compare_reports(first, second)

    def test_malformed_findings_fail_explicitly(self):
        cases = [[], dict(report(), findings={}), dict(report(), read_only=False)]
        for field in ("players", "people", "problems", "evidence", "canonical_rows"):
            broken = report(component(1))
            del broken["findings"][0][field]
            cases.append(broken)
        broken = report(component(1))
        broken["findings"][0]["problems"] = [dict(code="conflicting_ids")]
        cases.append(broken)
        for broken in cases:
            with self.subTest(broken=broken), self.assertRaises(AuditFormatError):
                compare_reports(broken, report())

    def test_file_errors_and_non_json_are_readable(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            with self.assertRaisesRegex(AuditFormatError, "nicht gelesen"):
                load_report(path)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(AuditFormatError, "nicht gelesen"):
                load_report(path)

    def test_cli_without_django_settings_database_or_site_packages(self):
        with TemporaryDirectory() as directory:
            before, after = (Path(directory) / name for name in ("before.json", "after.json"))
            before.write_text(json.dumps(report(component(1))), encoding="utf-8")
            after.write_text(json.dumps(report()), encoding="utf-8")
            original = (before.read_bytes(), after.read_bytes())
            env = {k: v for k, v in os.environ.items()
                   if k not in ("DJANGO_SETTINGS_MODULE", "DATABASE_URL")}
            args = [sys.executable, "-S", "-m", "game.club_import.identity_audit_diff",
                    str(before), str(after)]
            process = subprocess.run(args + ["--format", "json"], env=env,
                                     capture_output=True, text=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)["summary"]["removed"], 1)
            text = subprocess.run(args, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(text.returncode, 0, text.stderr)
            self.assertIn("Nicht mehr vorhanden: 1", text.stdout)
            self.assertIn("1001", text.stdout)
            self.assertEqual(original, (before.read_bytes(), after.read_bytes()))
            after.write_text(json.dumps(dict(report(), schema_version=2)), encoding="utf-8")
            bad = subprocess.run(args, env=env, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("schema_version", bad.stderr)
            self.assertNotIn("Traceback", bad.stderr)

    def test_management_command_and_text_use_same_comparison(self):
        from django.core.management.base import CommandError
        from game.management.commands.compare_player_identity_audits import Command

        before, after = report(component(1)), report(component(2))
        expected = compare_reports(before, after)
        with patch("game.management.commands.compare_player_identity_audits.load_report",
                   side_effect=[before, after]):
            output = StringIO()
            Command(stdout=output).handle(before="old.json", after="new.json", format="json")
        self.assertEqual(json.loads(output.getvalue()),
                         json.loads(json.dumps(expected)))
        text = render_text(expected)
        self.assertIn("Neu hinzugekommen: 1", text)
        self.assertIn("Nicht mehr vorhanden: 1", text)
        with patch("game.management.commands.compare_player_identity_audits.load_report",
                   side_effect=AuditFormatError("Schema passt nicht")):
            with self.assertRaisesRegex(CommandError, "Schema passt nicht"):
                Command(stdout=StringIO()).handle(before="old", after="new", format="text")
