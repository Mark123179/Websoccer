from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import zipfile

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from game import models as m
from game.club_import.restart_export import (
    HandoffError, build_package, canonical, read_package, write_package, source_only_evidence,
)
from game.club_import.restart_schema import MODELS
from game.club_import.restart_verify import assert_isolated, replay


class RestartPackageTests(TestCase):
    def setUp(self):
        self.league = m.League.objects.create(
            name="Restart Test", country="Test", is_playable=False)
        self.club = m.Club.objects.create(
            transfermarkt_id=16, name="Test club", league=self.league,
            founded_year=1909, budget=123456)
        self.source = m.DataSource.objects.create(code="TM", name="Transfermarkt")
        self.run = m.SourceImportRun.objects.create(
            club=self.club, target_league=self.league, source="club_package",
            status="applied", data_sha256="a" * 64,
            manifest={"data_sha256": "a" * 64},
            package_data={"players": [{
                "ids": {"tm": {"value": 796297}, "fmi": {"value": 900}},
                "ratings": {"fminside": {"rating": 60, "potential": 80}},
            }]})
        self.player = m.Player.objects.create(
            club=self.club, owner_club=self.club, transfermarkt_id=796297,
            first_name="Jobe", last_name="Bellingham", age=21, fm_inside_id=901,
            main_position_1="ZM", main_position_2="DM", secondary_position_1="OM",
            import_lock=True, import_lock_reasons=["Quarantäne bleibt"], review_pool=True)
        m.PlayerSourceRating.objects.create(
            player=self.player, source="FM", rating=60, potential=None)
        m.PlayerStrengthProfile.objects.create(player=self.player, base_strength=110)
        m.PlayerMarketValueSnapshot.objects.create(
            player=self.player, source=self.source, value_eur=10000000,
            package=self.run, raw_payload={"source": "current"})
        m.PlayerSourceRatingSnapshot.objects.create(
            player=self.player, source=self.source, rating=60, potential=None,
            raw_payload={"identity_review": {"fm_id": 901, "tm_id": 796297}})
        # Identical source rows are a multiset, not silently deduplicated.
        for _ in range(2):
            m.PlayerTransferHistory.objects.create(
                player=self.player, from_club=self.club, to_club=self.club,
                package=self.run, fee_eur=None)
        m.PlayerTransferHistory.objects.update(
            created_at=datetime(2026, 10, 27, tzinfo=timezone.utc))
        person = m.HistoricCoach.objects.create(name="Historischer Beleg", person_kind="trainer")
        m.ClubRecord.objects.create(
            club=self.club, holder_coach=person, record_key="longest_unbeaten",
            source="SEED", value_numeric=None, value_display="",
            evidence_status="nicht_belegt", holder_name=person.name, package=self.run)
        m.ClubTrophy.objects.create(
            club=self.club, competition_name="Belegter Titel", count=3, origin="real")
        m.ClubTrophyEntry.objects.create(
            club=self.club, competition_name="Belegter Titel", origin="real",
            season="1995/96", package=self.run)

    def test_export_read_only_current_not_archive_and_no_private_columns(self):
        before = list(m.Player.objects.values())
        with CaptureQueriesContext(connection) as queries:
            package = build_package()
        writes = ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ", "CREATE ", "DROP ", "ALTER ")
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(writes) for q in queries))
        self.assertEqual(before, list(m.Player.objects.values()))
        row = package["tables"]["Player"][0]
        self.assertEqual(row["key"], "Player:tm:796297")
        self.assertEqual(row["values"]["fm_inside_id"], 901)
        self.assertEqual(package["tables"]["PlayerSourceRating"][0]["values"]["potential"], None)
        self.assertIn("FM.potential", package["current_vs_archive"][0]["changes"])
        self.assertIn("fm_inside_id", package["current_vs_archive"][0]["changes"])
        self.assertFalse(package["full_restart_ready"])
        self.assertEqual(package["switzerland"]["current_imported_clubs"], 0)
        for name, rows in package["tables"].items():
            for entry in rows:
                self.assertNotIn("id", entry["values"])
                self.assertNotIn("created_by", entry["values"])
                self.assertNotIn("managed_by", entry["values"])
                self.assertFalse(any("image" in field for field in entry["values"]))
        self.assertNotIn("budget", package["tables"]["Club"][0]["values"])

    def test_lossless_microseconds_even_below_a_millisecond(self):
        value = datetime(2026, 10, 27, 12, 0, 0, 3, tzinfo=timezone.utc)
        encoded = canonical(value)
        self.assertIn(".000003", encoded)
        self.assertEqual(canonical(datetime.fromisoformat(json.loads(encoded))), encoded)

    def test_archive_integrity_and_contract_tampering(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.zip"
            package = build_package()
            write_package(path, package)
            self.assertEqual(read_package(path), package)
            with self.assertRaises(FileExistsError):
                write_package(path, package)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("current-state.json", canonical(package))
                archive.writestr("SHA256SUMS", "invalid")
            with self.assertRaisesMessage(HandoffError, "Prüfsumme"):
                read_package(path)

    def test_opaque_json_cannot_smuggle_images_or_local_foreign_keys(self):
        for value in ({"player_id": self.player.pk}, {"image_url": "/private-image.png"},
                      {"access_token": "not-a-real-token"}):
            m.PlayerSourceRatingSnapshot.objects.update(raw_payload=value)
            with self.assertRaisesMessage(HandoffError, "Nicht freigegebene"):
                build_package()

    def test_orphaned_quarantine_selected_by_source_identity(self):
        m.Player.objects.filter(pk=self.player.pk).update(club=None, owner_club=None)
        package = build_package()
        self.assertEqual(len(package["tables"]["Player"]), 1)
        self.assertTrue(package["tables"]["Player"][0]["values"]["import_lock"])

    def test_missing_current_player_does_not_rebuild_from_old_package(self):
        self.player.delete()
        with self.assertRaisesMessage(HandoffError, "Archiv-Spieler fehlen"):
            build_package()

    def test_full_roundtrip_with_new_ids_nulls_duplicates_and_no_save_hooks(self):
        package = build_package()
        source_pk = self.player.pk
        self.clear_source_test_rows()
        self.assertFalse(any(model.objects.exists() for model in MODELS.values()))
        # The real CLI file/backend guard is tested separately. This patch only
        # allows the Django-created isolated in-memory test DB for this test.
        with patch("game.club_import.restart_verify.assert_isolated"), patch.object(
                m.Player, "save", side_effect=AssertionError("save hook called")):
            report = replay(package)
        self.assertTrue(report["all_tables_identical"])
        self.assertNotEqual(m.Player.objects.get(transfermarkt_id=796297).pk, source_pk)
        self.assertEqual(m.PlayerSourceRating.objects.get().potential, None)
        self.assertEqual(m.PlayerTransferHistory.objects.count(), 2)
        self.assertEqual(m.ClubRecord.objects.get().value_numeric, None)
        self.assertEqual(m.Club.objects.get().budget, 0)
        self.assertFalse(m.League.objects.get().is_playable)
        self.assertEqual(report["destination_accounts"], 0)

    def clear_source_test_rows(self):
        m.Club.objects.all().delete()
        m.Player.objects.all().delete()
        m.HistoricCoach.objects.all().delete()
        m.SourceImportRun.objects.all().delete()
        m.DataSource.objects.all().delete()
        m.League.objects.all().delete()

    def test_broken_reference_rolls_back_whole_isolated_replay(self):
        package = build_package()
        package["tables"]["Player"][0]["values"]["club"] = "Club:tm:missing"
        self.clear_source_test_rows()
        with patch("game.club_import.restart_verify.assert_isolated"):
            with self.assertRaisesMessage(HandoffError, "Nicht auflösbare Referenz"):
                replay(package)
        self.assertFalse(any(model.objects.exists() for model in MODELS.values()))

    def test_replay_guard_rejects_regular_settings_and_nonempty_targets(self):
        with self.assertRaisesMessage(HandoffError, "ausschließlich"):
            assert_isolated()
        from django.conf import settings
        with override_settings(LIVE_RESTART_VERIFY_ONLY=True), patch.dict(
                connection.settings_dict, {"NAME": str(
                    Path(settings.BASE_DIR) / "generated-artifacts/live-restart/test.sqlite3")}):
            with self.assertRaisesMessage(HandoffError, "bereits"):
                assert_isolated()
        with patch.object(connection, "vendor", "postgresql"):
            with self.assertRaisesMessage(HandoffError, "ausschließlich"):
                assert_isolated()

    def test_export_has_no_apply_reset_or_mode_switch(self):
        for option in ("apply", "reset", "import"):
            with self.assertRaises(TypeError):
                call_command("live_restart_package", output="unused.zip",
                             stdout=StringIO(), **{option: True})

    def test_legacy_owner_note_keeps_tm_identity_not_workspace_pk(self):
        original = {"preserved_owner": {"owner_club_id": 123,
                    "owner_club_tm_id": 16, "owner_club_original_name": "Dortmund"}}
        result = source_only_evidence(original)
        self.assertEqual(result["preserved_owner"]["owner_club_tm_id"], 16)
        self.assertNotIn("owner_club_id", result["preserved_owner"])
        self.assertEqual(original["preserved_owner"]["owner_club_id"], 123)
        with self.assertRaises(HandoffError):
            source_only_evidence({"preserved_owner": {"owner_club_id": 123}})

    def test_isolated_swiss_addition_cannot_overwrite_current_baseline(self):
        from game.club_import.restart_baseline import protect_baseline
        m.Player.objects.filter(pk=self.player.pk).update(
            club=None, loan_club_tm_id=527, loan_status="loaned_out",
            pool_status="unavailable", review_pool=False)
        package = build_package()
        self.clear_source_test_rows()
        with patch("game.club_import.restart_verify.assert_isolated"):
            replay(package)
        player = m.Player.objects.get(transfermarkt_id=796297)
        m.Player.objects.filter(pk=player.pk).update(fm_inside_id=999)
        m.PlayerSourceRating.objects.filter(player=player).update(potential=99)
        m.PlayerStrengthProfile.objects.filter(player=player).update(final_strength=1)
        swiss = m.Club.objects.create(
            name="Lausanne", transfermarkt_id=527, founded_year=1896, budget=0,
            league=m.League.objects.create(name="Super League", country="Schweiz", is_playable=False))
        with patch("game.club_import.restart_baseline.assert_isolated"):
            report = protect_baseline(package, [527])
        self.assertTrue(report["all_current_baseline_facts_preserved"])
        player.refresh_from_db()
        self.assertEqual(player.fm_inside_id, 901)
        self.assertEqual(player.club_id, swiss.pk)
        self.assertTrue(player.import_lock)
        self.assertIsNone(m.PlayerSourceRating.objects.get(player=player).potential)
        self.assertEqual(m.PlayerStrengthProfile.objects.get(player=player).final_strength, 110)
