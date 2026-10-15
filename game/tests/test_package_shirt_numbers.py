"""Shirt-number retention, using only Django's isolated test database."""
from copy import deepcopy

from django.test import TestCase, override_settings

from game import models as m
from game.club_import.package_service import apply_package, source
from game.club_import.package_validation import read_package
from game.tests.test_package_security import V2, archive
from game.transfer_v2.models import Loan
from game.transfer_v2.services import end_loan


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class PackageShirtNumberTests(TestCase):
    def setUp(self):
        self.manifest, self.data = read_package(V2)
        self.data["players"] = [deepcopy(next(
            p for p in self.data["players"]
            if p["squad"]["team"] == "first" and p["squad"]["status"] == "own"
            and p["ids"]["fmi"]["value"] and p["ids"]["cmtracker"]["value"]
        ))]
        self.data["players"][0].update(market_values=[], transfers=[])
        self.data.update(persons=[], records=[], titles=[], gaps=[])
        self.tm_id = self.data["players"][0]["ids"]["tm"]["value"]
        self.league = m.League.objects.create(
            name="Number retention", country="Deutschland", is_playable=True)
        self.owner = m.Club.objects.create(
            name="Owner", league=self.league, founded_year=1900, budget=0,
            transfermarkt_id=1001, fm_inside_id=1001)
        self.borrower = m.Club.objects.create(
            name="Borrower", league=self.league, founded_year=1900, budget=0,
            transfermarkt_id=1002, fm_inside_id=1002)
        for club in (self.owner, self.borrower):
            m.ClubExternalId.objects.create(
                club=club, source=source("TM"),
                external_id=str(club.transfermarkt_id), status="gefunden")

    def package(self, club, status, number, *, omit_number=False):
        manifest, data = deepcopy(self.manifest), deepcopy(self.data)
        manifest["club"].update(
            tm_id=club.transfermarkt_id, fmi_id=club.fm_inside_id, name=club.name)
        data["club"]["name"] = club.name
        for provider, value in (
            ("tm", club.transfermarkt_id), ("fmi", club.fm_inside_id),
            ("cmtracker", club.transfermarkt_id),
        ):
            data["club"]["ids"][provider]["value"] = value
        squad = data["players"][0]["squad"]
        squad.update(
            status=status, shirt_number=number,
            owner_club=dict(tm_id=self.owner.transfermarkt_id, name=self.owner.name),
            loan_club=(dict(tm_id=self.borrower.transfermarkt_id, name=self.borrower.name)
                       if status != "own" else None),
            loan_until="2027-06-30" if status != "own" else None,
        )
        if omit_number:
            del squad["shirt_number"]
        return archive(manifest, data)

    def player(self):
        return m.Player.objects.get(transfermarkt_id=self.tm_id)

    def check_borrower_then_owner(self, number):
        apply_package(self.package(self.borrower, "loaned_in", number), self.league)
        player_pk = self.player().pk
        owner_package = self.package(self.owner, "loaned_out", None)
        apply_package(owner_package, self.league)
        player = self.player()
        self.assertEqual(player.pk, player_pk)
        self.assertEqual(player.shirt_number, number)
        self.assertEqual(player.club_id, self.borrower.pk)
        self.assertEqual(player.owner_club_id, self.owner.pk)
        self.assertTrue(apply_package(owner_package, self.league)["unchanged"])
        self.assertEqual(self.player().shirt_number, number)

    def test_ibrahimovic_number_21_survives_owner_package(self):
        self.check_borrower_then_owner(21)

    def test_futkeu_number_9_survives_owner_package(self):
        self.check_borrower_then_owner(9)

    def test_dinkci_number_18_survives_owner_package(self):
        self.check_borrower_then_owner(18)

    def test_atubolu_number_1_survives_owner_package(self):
        self.check_borrower_then_owner(1)

    def test_owner_then_borrower_sets_number_on_same_player(self):
        apply_package(self.package(self.owner, "loaned_out", None), self.league)
        player_pk = self.player().pk
        self.assertIsNone(self.player().shirt_number)
        apply_package(self.package(self.borrower, "loaned_in", 21), self.league)
        self.assertEqual(self.player().pk, player_pk)
        self.assertEqual(self.player().shirt_number, 21)

    def test_own_package_preserves_number_for_null_empty_or_missing_value(self):
        apply_package(self.package(self.owner, "own", 21), self.league)
        for number, omitted in ((None, False), ("", False), (None, True)):
            with self.subTest(number=number, omitted=omitted):
                apply_package(self.package(
                    self.owner, "own", number, omit_number=omitted), self.league)
                self.assertEqual(self.player().shirt_number, 21)

    def test_supplied_number_still_updates_existing_player(self):
        apply_package(self.package(self.owner, "own", 21), self.league)
        apply_package(self.package(self.owner, "own", 25), self.league)
        self.assertEqual(self.player().shirt_number, 25)

    def test_new_player_without_number_remains_unnumbered(self):
        apply_package(self.package(self.owner, "own", None), self.league)
        self.assertIsNone(self.player().shirt_number)

    def test_return_and_subsequent_owner_package_preserve_number(self):
        apply_package(self.package(self.borrower, "loaned_in", 21), self.league)
        loan = Loan.objects.create(
            player=self.player(), owner_club=self.owner, loan_club=self.borrower,
            fee=0, until="SE")
        # A teammate already wearing 21 must not trigger automatic reassignment.
        m.Player.objects.create(
            first_name="Other", last_name="Player", age=20, club=self.owner,
            shirt_number=21)
        end_loan(loan)
        end_loan(loan)  # Returning twice is idempotent.
        player = self.player()
        self.assertEqual(player.club_id, self.owner.pk)
        self.assertEqual(player.shirt_number, 21)
        loan.refresh_from_db()
        self.assertIsNotNone(loan.ended_at)
        apply_package(self.package(self.owner, "own", None), self.league)
        self.assertEqual(self.player().club_id, self.owner.pk)
        self.assertEqual(self.player().shirt_number, 21)
