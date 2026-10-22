"""Reciprocal loans through the guarded batch helper, in the test DB only."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from game import models as m
from game.club_import.package_service import apply_package
from game.club_import.package_validation import PackageError, read_package
from game.economy.booking import book
from game.tests.test_package_security import V2, archive
from scripts.import_additional_club_packages import fingerprint, import_batch
from stadium_editor.models import StadiumDesign, StadiumGeometry


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class AdditionalClubPackageTests(TestCase):
    def setUp(self):
        self.manifest, self.data = read_package(V2)
        self.data["players"] = [deepcopy(next(
            p for p in self.data["players"]
            if p["squad"]["status"] == "own" and p["squad"]["team"] == "first"
            and p["ids"]["fmi"]["value"] and p["ids"]["cmtracker"]["value"]
        ))]
        self.data["players"][0].update(market_values=[], transfers=[])
        self.data.update(persons=[], records=[], titles=[], gaps=[])
        self.tm = self.data["players"][0]["ids"]["tm"]["value"]
        self.league = m.League.objects.create(
            name="2. Bundesliga", country="Deutschland", level=2, is_playable=False)
        self.first = m.League.objects.create(
            name="Bundesliga", country="Deutschland", level=1, is_playable=True)
        self.anchor = m.Club.objects.create(
            name="Protected first club", league=self.first, founded_year=1900,
            budget=123456, transfermarkt_id=999001)
        self.unrelated = m.Player.objects.create(
            first_name="Unrelated", last_name="Player", age=24, club=self.anchor)
        stadium = m.Stadium.objects.create(club=self.anchor, name="Protected ground")
        StadiumDesign.objects.create(stadium=stadium, design={"unchanged": True})
        StadiumGeometry.objects.create(stadium=stadium, geometry={"unchanged": True})
        m.LeagueSeasonState.objects.create(
            league=self.first, season="1", current_matchday=12)
        User.objects.create_user(username="protected-manager")
        book(self.anchor, "KORREKTUR_ADMIN", 123, saison="1")
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.paths = []
        self.sources = []
        for tm, name, status in (
                (1001, "Owner", "loaned_out"), (1002, "Borrower", "loaned_in")):
            manifest, data = deepcopy(self.manifest), deepcopy(self.data)
            manifest["club"].update(tm_id=tm, fmi_id=tm, name=name)
            data["club"]["name"] = name
            for provider in ("tm", "fmi", "cmtracker", "api_football"):
                data["club"]["ids"][provider]["value"] = tm
            data["players"][0]["squad"].update(
                status=status, shirt_number=21 if status == "loaned_in" else None,
                owner_club={"tm_id": 1001, "name": "Owner"},
                loan_club={"tm_id": 1002, "name": "Borrower"},
                loan_until="2027-06-30")
            self.sources.append((manifest, data))
            self.paths.append(Path(self.directory.name) / f"{name}.zip")
        self.write_packages()

    def write_packages(self):
        for path, (manifest, data) in zip(self.paths, self.sources):
            path.write_bytes(archive(manifest, data))

    def snapshot(self):
        return {model._meta.label: fingerprint(model.objects.all())
                for model in apps.get_models()
                if model._meta.app_label in ("game", "stadium_editor")}

    def check_import(self, reverse=False):
        paths = self.paths[::-1] if reverse else self.paths
        raw_sources = [path.read_bytes() for path in paths]
        player_count = m.Player.objects.count()
        protected = fingerprint(m.Club.objects.filter(pk=self.anchor.pk))
        unrelated = fingerprint(m.Player.objects.filter(pk=self.unrelated.pk))
        protected_models = (m.LeagueSeasonState, m.FinanceTransaction, m.ManagerProfile,
                            StadiumDesign, StadiumGeometry)
        protected_rows = {model: fingerprint(model.objects.all()) for model in protected_models}
        report = import_batch(paths, {}, apply=True)
        player = m.Player.objects.get(transfermarkt_id=self.tm)
        self.assertEqual(m.Player.objects.count(), player_count + 1)
        self.assertEqual(m.Player.objects.filter(transfermarkt_id=self.tm).count(), 1)
        self.assertEqual(player.club.transfermarkt_id, 1002)
        self.assertEqual(player.owner_club.transfermarkt_id, 1001)
        self.assertEqual(player.loan_club_id, player.club_id)
        self.assertEqual(player.loan_status, "loaned_in")
        self.assertEqual(str(player.loan_until), "2027-06-30")
        self.assertEqual(player.shirt_number, 21)
        self.assertEqual(protected, fingerprint(m.Club.objects.filter(pk=self.anchor.pk)))
        self.assertEqual(unrelated, fingerprint(m.Player.objects.filter(pk=self.unrelated.pk)))
        for model, before in protected_rows.items():
            self.assertEqual(before, fingerprint(model.objects.all()))
        self.league.refresh_from_db()
        self.assertFalse(self.league.is_playable)
        for item in report["packages"]:
            self.assertEqual(item["players"], 1)
            run = m.SourceImportRun.objects.get(pk=item["run"])
            source = next(data for manifest, data in self.sources
                          if manifest["club"]["tm_id"] == run.club.transfermarkt_id)
            self.assertEqual(run.package_data, source)
        self.assertEqual(raw_sources, [path.read_bytes() for path in paths])
        before_replay = self.snapshot()
        import_batch(paths, {}, apply=True)
        self.assertEqual(before_replay, self.snapshot())
        return player

    def test_owner_then_borrower_and_exact_repetition(self):
        self.check_import()

    def test_borrower_then_owner_and_exact_repetition(self):
        self.check_import(reverse=True)

    def test_missing_number_in_owner_package(self):
        del self.sources[0][1]["players"][0]["squad"]["shirt_number"]
        self.write_packages()
        self.check_import(reverse=True)

    def test_matching_known_numbers(self):
        self.sources[0][1]["players"][0]["squad"]["shirt_number"] = 21
        self.write_packages()
        self.check_import()

    def test_missing_optional_id_does_not_erase_other_package_knowledge(self):
        outgoing = self.sources[0][1]["players"][0]
        incoming = self.sources[1][1]["players"][0]
        incoming["ids"]["api_football"].update(value=12345678, status="gefunden")
        outgoing["ids"]["api_football"].update(value=None, status="nicht_gefunden")
        self.write_packages()
        player = self.check_import(reverse=True)
        self.assertEqual(player.api_football_id, 12345678)

    def test_conflicts_rejected_before_any_package_is_applied(self):
        original = deepcopy(self.sources)
        for conflict in ("borrower", "owner", "loan_until", "birth_date",
                         "fmi", "cmtracker", "number", "name", "own"):
            with self.subTest(conflict=conflict):
                self.sources = deepcopy(original)
                outgoing = self.sources[0][1]["players"][0]
                incoming = self.sources[1][1]["players"][0]
                if conflict == "borrower":
                    outgoing["squad"]["loan_club"]["tm_id"] = 1003
                elif conflict == "owner":
                    incoming["squad"]["owner_club"]["tm_id"] = 1003
                elif conflict == "loan_until":
                    outgoing["squad"]["loan_until"] = "2028-06-30"
                elif conflict == "birth_date":
                    outgoing["date_of_birth"] = "1990-01-01"
                elif conflict in ("fmi", "cmtracker"):
                    outgoing["ids"][conflict]["value"] += 1
                elif conflict == "number":
                    outgoing["squad"]["shirt_number"] = 9
                elif conflict == "name":
                    outgoing["last_name"] = "Other identity"
                else:
                    outgoing["squad"].update(status="own", loan_club=None, loan_until=None)
                self.write_packages()
                before = self.snapshot()
                for paths in (self.paths, self.paths[::-1]):
                    with patch("scripts.import_additional_club_packages.apply_package") as apply:
                        with self.assertRaises(PackageError):
                            import_batch(paths, {}, apply=True)
                        apply.assert_not_called()
                self.assertEqual(before, self.snapshot())

    def test_shared_provider_id_for_different_tm_players_is_rejected(self):
        self.sources[1][1]["players"][0]["ids"]["tm"]["value"] += 1
        self.write_packages()
        with self.assertRaisesRegex(PackageError, "Conflicting .* identity"):
            import_batch(self.paths, {}, apply=True)
        self.assertFalse(m.SourceImportRun.objects.exists())

    def test_duplicate_club_package_is_rejected(self):
        with self.assertRaisesRegex(PackageError, "Duplicate club"):
            import_batch([self.paths[0], self.paths[0]], {}, apply=True)

    def test_dry_run_rolls_back_every_row(self):
        before = self.snapshot()
        report = import_batch(self.paths, {}, apply=False)
        self.assertFalse(report["applied"])
        self.assertTrue(report["replay_unchanged"])
        self.assertEqual(before, self.snapshot())

    def test_later_failure_rolls_back_both_packages(self):
        before = self.snapshot()
        def fail_second(path, league):
            if path == self.paths[1]:
                raise PackageError("Injected second-package failure")
            return apply_package(path, league)
        with patch("scripts.import_additional_club_packages.apply_package",
                   side_effect=fail_second):
            with self.assertRaisesRegex(PackageError, "Injected"):
                import_batch(self.paths, {}, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_active_first_league_player_is_protected(self):
        self.unrelated.transfermarkt_id = self.tm
        self.unrelated.date_of_birth = self.data["players"][0]["date_of_birth"]
        self.unrelated.save()
        before = self.snapshot()
        with self.assertRaisesRegex(PackageError, "active first-league"):
            import_batch(self.paths, {}, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_started_second_league_is_not_imported(self):
        m.LeagueSeasonState.objects.create(
            league=self.league, season="1", current_matchday=2)
        before = self.snapshot()
        with self.assertRaisesRegex(PackageError, "already started"):
            import_batch(self.paths, {}, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_protected_changes_abort_the_whole_batch(self):
        before = self.snapshot()
        def mutate_protected(path, league):
            result = apply_package(path, league)
            m.Club.objects.filter(pk=self.anchor.pk).update(budget=0)
            return result
        with patch("scripts.import_additional_club_packages.apply_package",
                   side_effect=mutate_protected):
            with self.assertRaisesRegex(PackageError, "Protected club"):
                import_batch(self.paths, {}, apply=True)
        self.assertEqual(before, self.snapshot())
