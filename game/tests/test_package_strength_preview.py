"""Synthetic packages: announced first strengths must match the real import."""
from copy import deepcopy

from django.apps import apps
from django.db import transaction
from django.test import TestCase, override_settings

from game import models as m
from game.club_import.package_preview import preview_package
from game.club_import.package_service import apply_package
from game.strength_service import compute_strength_for_player
from game.tests.package_identity_fixture import identity_package_fixture
from game.tests.test_package_security import archive


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class PackageStrengthPreviewTests(TestCase):
    def setUp(self):
        self.manifest, self.data = identity_package_fixture()
        self.league = m.League.objects.create(
            name="Importliga", country="Deutschland", is_playable=False)

    def snapshot(self):
        return {
            model._meta.label: list(model.objects.order_by("pk").values())
            for model in apps.get_models()
            if model._meta.app_label in ("game", "stadium_editor") and not model._meta.proxy
        }

    def preview(self, data, expected_names):
        raw = archive(self.manifest, data)
        before = self.snapshot()
        preview = preview_package(raw, self.league)
        self.assertEqual(preview["new_strengths"], len(expected_names))
        self.assertEqual(preview["new_strength_players"], expected_names)
        self.assertEqual(self.snapshot(), before, "Preview must not write any rows")
        return raw

    def assert_projected_strength(self, pdata, *, computable=True):
        player = m.Player.objects.get(transfermarkt_id=pdata["ids"]["tm"]["value"])
        result = compute_strength_for_player(player)
        self.assertEqual(result["computable"], computable)
        profiles = m.PlayerStrengthProfile.objects.filter(player=player)
        self.assertEqual(profiles.exists(), computable)
        if computable:
            self.assertEqual(profiles.get().base_strength, result["base_strength"])
        return player

    def test_first_import_announces_and_projects_strength(self):
        pdata = self.data["players"][0]
        raw = self.preview(self.data, [pdata["display_name"]])
        self.assertFalse(m.Player.objects.filter(
            transfermarkt_id=pdata["ids"]["tm"]["value"]).exists())
        apply_package(raw, self.league)
        self.assert_projected_strength(pdata)
        raw = self.preview(self.data, [])
        before = self.snapshot()
        self.assertTrue(apply_package(raw, self.league)["unchanged"])
        self.assertEqual(self.snapshot(), before)

    def test_either_complete_source_is_sufficient(self):
        for provider in ("fminside", "cmtracker"):
            with self.subTest(provider=provider), transaction.atomic():
                data = deepcopy(self.data)
                for other in data["players"][0]["ratings"]:
                    if other != provider:
                        data["players"][0]["ratings"][other] = None
                pdata = data["players"][0]
                raw = self.preview(data, [pdata["display_name"]])
                apply_package(raw, self.league)
                self.assert_projected_strength(pdata)
                transaction.set_rollback(True)

    def test_incomplete_sources_do_not_announce_or_project_strength(self):
        cases = (
            {"fminside": None, "cmtracker": None},
            {"fminside": {}, "cmtracker": {}},
            {"fminside": {"rating": 81, "potential": None}, "cmtracker": None},
            {"fminside": None, "cmtracker": {"rating": None, "potential": 89}},
            {"fminside": {"rating": 81, "potential": None},
             "cmtracker": {"rating": None, "potential": 89}},
        )
        for ratings in cases:
            with self.subTest(ratings=ratings), transaction.atomic():
                data = deepcopy(self.data)
                data["players"][0]["ratings"] = ratings
                raw = self.preview(data, [])
                apply_package(raw, self.league)
                self.assert_projected_strength(data["players"][0], computable=False)
                transaction.set_rollback(True)

    def test_reupload_announces_new_player_but_not_existing_strength(self):
        profiles_before = m.PlayerStrengthProfile.objects.count()
        apply_package(archive(self.manifest, self.data), self.league)
        old = self.assert_projected_strength(self.data["players"][0])
        data = deepcopy(self.data)
        new = deepcopy(data["players"][0])
        new.update(first_name="Neuer", display_name="Neuer Torwart")
        new["ids"]["tm"]["value"] = 257815
        new["ids"]["fmi"]["value"] = 98040384
        new["ids"]["cmtracker"]["value"] = 235074
        new["squad"]["shirt_number"] = 2
        data["players"].append(new)
        raw = self.preview(data, [new["display_name"]])
        apply_package(raw, self.league)
        self.assert_projected_strength(new)
        self.assert_projected_strength(data["players"][0])
        self.assertEqual(m.PlayerStrengthProfile.objects.count(), profiles_before + 2)
        self.assertEqual(m.Player.objects.get(pk=old.pk).display_name, old.display_name)

    def test_reupload_announces_first_potential_for_existing_player(self):
        data = deepcopy(self.data)
        for block in data["players"][0]["ratings"].values():
            block["potential"] = None
        apply_package(self.preview(data, []), self.league)
        self.assert_projected_strength(data["players"][0], computable=False)
        pdata = self.data["players"][0]
        apply_package(self.preview(self.data, [pdata["display_name"]]), self.league)
        self.assert_projected_strength(pdata)

    def test_reupload_completes_previously_discarded_potential_only_source(self):
        for provider in ("fminside", "cmtracker"):
            with self.subTest(provider=provider), transaction.atomic():
                data = deepcopy(self.data)
                for other, block in data["players"][0]["ratings"].items():
                    if other == provider:
                        block["rating"] = None
                    else:
                        block["potential"] = None
                apply_package(self.preview(data, []), self.league)
                player = self.assert_projected_strength(data["players"][0], computable=False)
                self.assertFalse(player.source_ratings.exclude(potential=None).exists())
                pdata = self.data["players"][0]
                apply_package(self.preview(self.data, [pdata["display_name"]]), self.league)
                self.assert_projected_strength(pdata)
                self.preview(self.data, [])
                transaction.set_rollback(True)

    def test_reupload_after_start_neither_announces_nor_initializes_strengths(self):
        data = deepcopy(self.data)
        for block in data["players"][0]["ratings"].values():
            block["potential"] = None
        apply_package(self.preview(data, []), self.league)
        player = self.assert_projected_strength(data["players"][0], computable=False)
        m.LeagueSeasonState.objects.create(
            league=self.league, season="1", current_matchday=2)
        incoming = deepcopy(self.data)
        new = deepcopy(incoming["players"][0])
        new.update(first_name="Neuer", display_name="Neuer Torwart")
        new["ids"]["tm"]["value"] = 257815
        new["ids"]["fmi"]["value"] = 98040384
        new["ids"]["cmtracker"]["value"] = 235074
        new["squad"]["shirt_number"] = 2
        incoming["players"].append(new)
        protected_models = (
            m.PlayerStrengthProfile, m.PlayerSourceRating, m.PlayerSourceRatingSnapshot)
        before = {model: list(model.objects.order_by("pk").values())
                  for model in protected_models}
        apply_package(self.preview(incoming, []), self.league)
        self.assertFalse(m.Player.objects.filter(
            transfermarkt_id=new["ids"]["tm"]["value"]).exists())
        self.assertEqual(m.Player.objects.get(pk=player.pk).pk, player.pk)
        self.assert_projected_strength(data["players"][0], computable=False)
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows)

    def test_active_loanee_is_preserved_on_first_owner_import_and_reupload(self):
        # Resolve owner references before taking the protected-player snapshot.
        owner = m.Club.objects.create(
            name="Testverein", founded_year=1900, league=self.league,
            transfermarkt_id=16, budget=0)
        tm_source, _ = m.DataSource.objects.get_or_create(code="TM", defaults={"name": "TM"})
        m.ClubExternalId.objects.create(club=owner, source=tm_source, external_id="16")
        borrower_manifest, borrower_data = identity_package_fixture()
        borrower_manifest["club"].update(tm_id=1002, fmi_id=1002, name="Leihverein")
        borrower_data["club"].update(name="Leihverein")
        for provider in borrower_data["club"]["ids"]:
            borrower_data["club"]["ids"][provider]["value"] = 1002
        borrower_data["players"][0]["squad"].update(
            status="loaned_in", loan_club={"tm_id": 1002, "name": "Leihverein"},
            loan_until="2027-06-30")
        apply_package(archive(borrower_manifest, borrower_data), self.league)
        player = self.assert_projected_strength(borrower_data["players"][0])
        live_league = m.League.objects.create(
            name="Aktive Liga", country="Deutschland", is_playable=True)
        m.Club.objects.filter(pk=player.club_id).update(league=live_league)
        data = deepcopy(self.data)
        data["players"][0]["squad"].update(
            status="loaned_out", loan_club={"tm_id": 1002, "name": "Leihverein"},
            loan_until="2027-06-30")
        protected_models = (
            m.Player, m.PlayerStrengthProfile, m.PlayerSourceRating,
            m.PlayerSourceRatingSnapshot, m.PlayerExternalId, m.PlayerClubHistory,
            m.PlayerTransferHistory,
        )
        before = {model: list(model.objects.order_by("pk").values())
                  for model in protected_models}
        for potential in (None, 100):
            with self.subTest(potential=potential):
                for block in data["players"][0]["ratings"].values():
                    block.update(rating=1, potential=potential)
                raw = self.preview(data, [])
                apply_package(raw, self.league)
                for model, rows in before.items():
                    self.assertEqual(list(model.objects.order_by("pk").values()), rows)
                self.assert_projected_strength(borrower_data["players"][0])
