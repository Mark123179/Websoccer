from io import StringIO
import json

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from game import models as m
from game.club_import.live_restart_inventory import build_inventory
from game.club_import.package_validation import digest


class LiveRestartInventoryTests(TestCase):
    def setUp(self):
        league = m.League.objects.create(name="Inventory Test", country="Test")
        self.club = m.Club.objects.create(
            name="Inventory Club", league=league, transfermarkt_id=987654321,
            founded_year=1900, budget=0)
        self.payload = {"club": {"name": self.club.name}, "players": []}
        checksum = digest(self.payload)
        self.run = m.SourceImportRun.objects.create(
            source="club_package", status="applied", club=self.club,
            package_data=self.payload, data_sha256=checksum,
            manifest={"data_sha256": checksum})

    def test_inventory_is_read_only_and_never_authorizes_reset(self):
        before = list(m.SourceImportRun.objects.values())
        with CaptureQueriesContext(connection) as captured:
            report = build_inventory()
        writes = ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ", "DROP ", "ALTER ", "CREATE ")
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(writes) for q in captured))
        self.assertEqual(before, list(m.SourceImportRun.objects.values()))
        self.assertFalse(report["ready_for_reset"])
        club = next(c for c in report["clubs"] if c["tm_id"] == self.club.transfermarkt_id)
        self.assertTrue(club["source_metadata_consistent"])
        self.assertEqual(club["stored_package_canonical_sha256"], digest(self.payload))
        self.assertNotIn("id", club)
        self.assertNotIn("created_by", json.dumps(report))

    def test_corrupt_archive_is_explicitly_reported(self):
        self.run.data_sha256 = "incorrect"
        self.run.save(update_fields=["data_sha256"])
        report = build_inventory()
        self.assertTrue(any("987654321" in problem for problem in report["source_problems"]))
        self.assertFalse(next(c for c in report["clubs"]
                              if c["tm_id"] == self.club.transfermarkt_id)["source_metadata_consistent"])

    def test_command_emits_json_without_an_execution_mode(self):
        out = StringIO()
        call_command("live_restart_inventory", stdout=out)
        self.assertTrue(json.loads(out.getvalue())["read_only"])
        with self.assertRaises(TypeError):
            call_command("live_restart_inventory", apply=True, stdout=StringIO())
