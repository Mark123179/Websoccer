"""Reciprocal loans through the guarded batch helper, in the test DB only."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from game import models as m
from game.club_import.package_preview import preview_package
from game.club_import.package_service import apply_package
from game.club_import.package_validation import PackageError
from game.economy.booking import book
from game.tests.test_package_security import archive
from game.tests.package_identity_fixture import identity_package_fixture
from scripts.import_additional_club_packages import fingerprint, import_batch
from stadium_editor.models import StadiumDesign, StadiumGeometry


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class AdditionalClubPackageTests(TestCase):
    def setUp(self):
        self.manifest, self.data = identity_package_fixture()
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

    def foreign_league(self):
        return m.League.objects.create(
            name="Premier League", country="England", level=1,
            max_teams=20, is_playable=False)

    def prepare_live_foreign_loan(self):
        # The borrower was imported previously; its competition is now live.
        apply_package(self.paths[1], self.league)
        player = m.Player.objects.get(transfermarkt_id=self.tm)
        m.Club.objects.filter(pk=player.club_id).update(league=self.first)
        m.Player.objects.filter(pk=player.pk).update(
            age=35, shirt_number=99, salary_per_match=777)
        m.PlayerTransferHistory.objects.create(
            player=player, origin="real", source_row_key="protected-live-loan",
            transfer_date="2026-01-01", from_tm_id=1001, from_original_name="Owner",
            to_tm_id=1002, to_club=player.club, to_original_name="Borrower",
            is_loan=True, fee_text="Protected source evidence")
        self.sources[0][1]["club"]["country"] = "England"
        self.write_packages()
        return player

    def login_creator(self):
        user = User.objects.create_user(username="loan-preview-creator", is_staff=True)
        self.client.force_login(user)
        # Warm up global login rewards/activity and calendar weather before
        # measuring the package preview, rather than hiding those writes.
        self.assertEqual(self.client.get(reverse("package_creator:hub")).status_code, 200)

    def render_owner_preview(self, league):
        return self.client.post(reverse("package_creator:preview"), {
            "league": league.pk,
            "package": SimpleUploadedFile("owner.zip", self.paths[0].read_bytes()),
        })

    def test_live_loan_preview_is_read_only_and_matches_confirmed_projection(self):
        league = self.foreign_league()
        player = self.prepare_live_foreign_loan()
        self.login_creator()
        before = self.snapshot()
        preview = preview_package(self.paths[0], league)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(len(preview["protected_live_loans"]), 1)
        loan = preview["protected_live_loans"][0]
        self.assertEqual(
            (loan["player_id"], loan["owner"], loan["owner_tm"],
             loan["borrower"], loan["borrower_tm"], str(loan["loan_until"]), loan["omitted"]),
            (player.pk, "Owner", 1001, "Borrower", 1002, "2027-06-30", False))
        self.assertEqual(preview["players_to_review"], [])
        self.assertEqual(preview["changes"], [])
        self.assertEqual(preview["new_strengths"], 0)
        response = self.render_owner_preview(league)
        for text in ("Geschützte aktive Leihspieler", player.full_name,
                     "Owner (TM 1001)", "Borrower (TM 1002)", "30.06.2027",
                     "Spielerwerte, IDs, Stärke und Historien bleiben unverändert",
                     "Originalpaket als Quellenbeleg", "Nur belegte offene Vereinsreferenzen"):
            self.assertContains(response, text)
        self.assertNotContains(response, "Wird beim Import berechnet")
        self.assertEqual(before, self.snapshot())
        original = m.Player.objects.filter(pk=player.pk).values().get()
        result = self.client.post(reverse("package_creator:confirm"),
                                  {"token": response.context["token"]})
        self.assertEqual(result.status_code, 302)
        player.refresh_from_db()
        self.assertEqual(
            dict(original, owner_club_id=player.owner_club_id,
                 loan_partner_club_id=player.owner_club_id),
            m.Player.objects.filter(pk=player.pk).values().get())
        run = m.SourceImportRun.objects.get(club=player.owner_club, status="applied")
        self.assertEqual(run.package_data, self.sources[0][1])

    def test_live_loan_reupload_does_not_offer_static_changes_or_new_strength(self):
        league = self.foreign_league()
        player = self.prepare_live_foreign_loan()
        source_player = self.sources[0][1]["players"][0]
        ratings = deepcopy(source_player["ratings"])
        for block in source_player["ratings"].values():
            if block:
                block["potential"] = None
        self.write_packages()
        apply_package(self.paths[0], league)
        source_player["ratings"] = ratings
        source_player["display_name"] = "<em>Statischer Paketname</em>"
        for block in source_player["ratings"].values():
            if block and block.get("rating") is not None:
                block["rating"] = 1
                block["potential"] = 100
        self.write_packages()
        self.login_creator()
        before = self.snapshot()
        response = self.render_owner_preview(league)
        preview = response.context["preview"]
        self.assertEqual(preview["changes"], [])
        self.assertEqual(preview["new_strengths"], 0)
        self.assertEqual(preview["new_strength_players"], [])
        self.assertEqual(preview["data"]["players"][0], source_player)
        self.assertEqual(preview["protected_live_loans"][0]["name"], player.full_name)
        self.assertContains(response, "Abweichende statische Paketwerte werden nicht übernommen")
        self.assertContains(response, "&lt;em&gt;Statischer Paketname&lt;/em&gt;")
        self.assertNotContains(response, "<em>Statischer Paketname</em>")
        self.assertNotContains(response, "Geänderte Werte vor Übernahme")
        self.assertNotContains(response, "Wird beim Import berechnet")
        self.assertEqual(before, self.snapshot())
        original = m.Player.objects.filter(pk=player.pk).values().get()
        apply_package(self.paths[0], league)
        self.assertEqual(original, m.Player.objects.filter(pk=player.pk).values().get())
        player.refresh_from_db()
        self.assertEqual(m.SourceImportRun.objects.filter(club=player.owner_club)
                         .latest("pk").package_data, self.sources[0][1])

    def test_live_loan_preview_guard_tracks_player_before_owner_exists(self):
        league = self.foreign_league()
        player = self.prepare_live_foreign_loan()
        self.login_creator()
        response = self.render_owner_preview(league)
        guard = response.context["preview"]["guard"]
        m.Player.objects.filter(pk=player.pk).update(shirt_number=98)
        before = self.snapshot()
        self.assertNotEqual(guard, preview_package(self.paths[0], league)["guard"])
        result = self.client.post(reverse("package_creator:confirm"),
                                  {"token": response.context["token"]})
        self.assertContains(result, "Datenstand geändert", status_code=400)
        self.assertEqual(before, self.snapshot())

    def test_live_loan_preview_blocks_conflicting_loan_facts_without_writes(self):
        league = self.foreign_league()
        self.prepare_live_foreign_loan()
        self.login_creator()
        original = deepcopy(self.sources[0][1]["players"][0])
        variants = [
            {"date_of_birth": "2000-01-01"},
            {"squad": dict(original["squad"], loan_until="2028-06-30")},
            {"squad": dict(original["squad"], owner_club={"tm_id": 999, "name": "Other"})},
            {"squad": dict(original["squad"], loan_club={"tm_id": 999, "name": "Other"})},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                self.sources[0][1]["players"][0] = dict(deepcopy(original), **changes)
                self.write_packages()
                before = self.snapshot()
                with self.assertRaises(PackageError):
                    preview_package(self.paths[0], league)
                response = self.render_owner_preview(league)
                self.assertEqual(response.status_code, 400)
                self.assertNotContains(response, "Paket jetzt übernehmen", status_code=400)
                self.assertEqual(before, self.snapshot())

    def test_explicit_foreign_target_keeps_german_leagues_unchanged(self):
        league = self.foreign_league()
        for _, data in self.sources:
            data["club"]["country"] = "England"
        self.write_packages()
        before = fingerprint(m.League.objects.all())
        report = import_batch(self.paths, {}, apply=True, target_league_id=league.pk)
        self.assertEqual(report["league_id"], league.pk)
        self.assertEqual(report["league_name"], "Premier League")
        self.assertEqual(m.Club.objects.filter(league=league).count(), 2)
        self.assertEqual(m.Club.objects.filter(league=self.league).count(), 0)
        self.assertEqual(before, fingerprint(m.League.objects.all()))

    def test_explicit_playable_target_is_rejected_without_writes(self):
        before = self.snapshot()
        with self.assertRaises(PackageError):
            import_batch(self.paths, {}, apply=True, target_league_id=self.first.pk)
        self.assertEqual(before, self.snapshot())

    def test_wrong_country_target_is_rejected_without_writes(self):
        league = self.foreign_league()
        before = self.snapshot()
        with self.assertRaises(PackageError):
            import_batch(self.paths, {}, apply=True, target_league_id=league.pk)
        self.assertEqual(before, self.snapshot())

    def test_live_foreign_loan_preserves_player_ratings_history_and_replay(self):
        league = self.foreign_league()
        player = self.prepare_live_foreign_loan()
        original = m.Player.objects.filter(pk=player.pk).values().get()
        before = self.snapshot()
        report = import_batch(
            self.paths[:1], {}, apply=False, target_league_id=league.pk)
        self.assertFalse(report["applied"])
        self.assertEqual(before, self.snapshot())
        report = import_batch(
            self.paths[:1], {}, apply=True, target_league_id=league.pk)
        player.refresh_from_db()
        self.assertEqual(report["preserved_live_loans"], [self.tm])
        expected = dict(original, owner_club_id=player.owner_club_id,
                        loan_partner_club_id=player.owner_club_id)
        self.assertEqual(expected, m.Player.objects.filter(pk=player.pk).values().get())
        self.assertEqual(player.owner_club.league_id, league.pk)
        self.assertEqual(player.club.league_id, self.first.pk)
        self.assertEqual(player.shirt_number, 99)
        self.assertTrue(report["replay_unchanged"])
        self.assertTrue(report["protected_state_unchanged"])
        self.assertEqual(m.SourceImportRun.objects.get(pk=report["packages"][0]["run"]).package_data,
                         self.sources[0][1])

    def test_conflicting_live_loan_blocks_helper_and_direct_import_without_writes(self):
        league = self.foreign_league()
        player = self.prepare_live_foreign_loan()
        m.Player.objects.filter(pk=player.pk).update(loan_until="2028-06-30")
        before = self.snapshot()
        for run in (
            lambda: import_batch(self.paths[:1], {}, apply=True, target_league_id=league.pk),
            lambda: apply_package(self.paths[0], league),
        ):
            with self.assertRaises(PackageError):
                run()
            self.assertEqual(before, self.snapshot())

    def test_direct_import_identity_conflict_never_invalidates_live_player_ids(self):
        league = self.foreign_league()
        self.prepare_live_foreign_loan()
        foreign_id = 99999001
        m.Player.objects.create(
            first_name="Other", last_name="Identity", age=20, fm_inside_id=foreign_id)
        self.sources[0][1]["players"][0]["ids"]["fmi"]["value"] = foreign_id
        self.write_packages()
        self.login_creator()
        before = self.snapshot()
        with self.assertRaises(PackageError):
            preview_package(self.paths[0], league)
        self.assertEqual(self.render_owner_preview(league).status_code, 400)
        self.assertEqual(before, self.snapshot())
        with self.assertRaises(PackageError):
            apply_package(self.paths[0], league)
        self.assertEqual(before, self.snapshot())

    def test_owner_reupload_cannot_remove_omitted_loanee_from_live_squad(self):
        league = self.foreign_league()
        player = self.prepare_live_foreign_loan()
        apply_package(self.paths[0], league)
        before = m.Player.objects.filter(pk=player.pk).values().get()
        replacement = deepcopy(self.sources[0][1]["players"][0])
        replacement.update(first_name="Another", last_name="Player", display_name="Another Player")
        for entry in replacement["ids"].values():
            if entry["value"] is not None:
                entry["value"] += 9000000
        replacement["squad"].update(status="own", loan_club=None, loan_until=None)
        self.sources[0][1]["players"] = [replacement]
        self.write_packages()
        self.login_creator()
        database_before = self.snapshot()
        response = self.render_owner_preview(league)
        preview = response.context["preview"]
        self.assertEqual(len(preview["protected_live_loans"]), 1)
        self.assertTrue(preview["protected_live_loans"][0]["omitted"])
        self.assertEqual(preview["protected_live_loans"][0]["source_json"], "")
        self.assertNotIn(player.display_name, preview["players_to_review"])
        self.assertContains(response, player.full_name)
        self.assertContains(response, "Fehlt im Stammvereinspaket; aktiver Kader bleibt erhalten")
        self.assertNotContains(response, "Fehlt im Paket; vorhandene Daten bleiben im Prüfpool erhalten")
        self.assertEqual(database_before, self.snapshot())
        apply_package(self.paths[0], league)
        self.assertEqual(before, m.Player.objects.filter(pk=player.pk).values().get())

    def test_borrower_then_owner_and_exact_repetition(self):
        self.check_import(reverse=True)

    def check_historical_loan(self, reverse):
        person = m.HistoricCoach.objects.create(
            name="Historischer Quellname", person_kind="spieler",
            birth_date=self.data["players"][0]["date_of_birth"])
        source = m.DataSource.objects.get_or_create(code="TM", defaults={"name": "TM"})[0]
        external = m.PlayerExternalId.objects.create(
            person=person, source=source, external_id=str(self.tm),
            identity_kind="spieler", status="gefunden",
            source_url="https://example.org/original", match_evidence={"original": True})
        external_before = m.PlayerExternalId.objects.filter(pk=external.pk).values().get()
        record = m.ClubRecord.objects.create(
            club=self.anchor, record_key="top_scorer", source="SEED",
            value_numeric=42, value_display="42", holder_name=person.name,
            holder_coach=person, source_note="Geschützter Originalbeleg")
        record_before = m.ClubRecord.objects.filter(pk=record.pk).values().get()
        paths = self.paths[::-1] if reverse else self.paths
        before = self.snapshot()
        self.assertFalse(import_batch(paths, {}, apply=False)["applied"])
        self.assertEqual(before, self.snapshot())
        player = self.check_import(reverse=reverse)
        person.refresh_from_db()
        self.assertEqual(person.linked_player_id, player.pk)
        self.assertEqual(external_before, m.PlayerExternalId.objects.filter(pk=external.pk).values().get())
        self.assertEqual(record_before, m.ClubRecord.objects.filter(pk=record.pk).values().get())
        self.assertFalse(m.PlayerExternalId.objects.filter(
            player=player, source=source, external_id=str(self.tm)).exists())
        self.assertEqual(player.fm_inside_id, self.data["players"][0]["ids"]["fmi"]["value"])

    def test_historical_tm_owner_then_borrower_and_exact_repetition(self):
        self.check_historical_loan(reverse=False)

    def test_historical_tm_borrower_then_owner_and_exact_repetition(self):
        self.check_historical_loan(reverse=True)

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
