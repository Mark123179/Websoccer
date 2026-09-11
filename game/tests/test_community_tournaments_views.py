"""HTTP contract tests for the community tournament desk.

These tests intentionally exercise the public view contract rather than the
tournament algorithm (the latter is covered by the friendlies service tests).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from game.models import (
    Club, CommunityTournament, CommunityTournamentApplication,
    CommunityTournamentEntry, League, ManagerProfile,
)


class CommunityTournamentViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tour-manager", password="password")
        self.profile = ManagerProfile.objects.get(user=self.user)
        self.profile.name = "Tour Manager"
        self.profile.save(update_fields=["name"])
        league = League.objects.create(name="Testliga", country="DE")
        self.club = Club.objects.create(name="Organizer FC", short_name="ORG",
                                        league=league, founded_year=1900, budget=0,
                                        managed_by=self.profile)
        self.other_user = get_user_model().objects.create_user(
            username="other-manager", password="password")
        other_profile = ManagerProfile.objects.get(user=self.other_user)
        other_profile.name = "Other Manager"
        other_profile.save(update_fields=["name"])
        self.other = Club.objects.create(name="Other FC", short_name="OTH",
                                         league=league, founded_year=1901, budget=0,
                                         managed_by=other_profile)
        self.ai = Club.objects.create(name="Computer FC", short_name="CPU",
                                      league=league, founded_year=1902, budget=0)
        self.client.login(username="tour-manager", password="password")

    def _schedule(self, count):
        start = timezone.now() + timedelta(days=2)
        return [(start + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M")
                for i in range(count)]

    def _create(self, **extra):
        data = {
            "action": "create", "name": "Test Cup", "format": "pokal",
            "field_size": "4", "access": "offen",
        }
        data.update({f"schedule_{i}": value
                     for i, value in enumerate(self._schedule(2))})
        data.update(extra)
        return self.client.post(reverse("tournament_action"), data,
                                HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_authenticated_list_has_cards_wizard_and_u21_empty_state(self):
        response = self.client.get(reverse("management_friendlies"),
                                    {"tab": "tournaments"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Neues Turnier erstellen")
        self.assertContains(response, "1 · Format")
        self.assertContains(response, "2 · Teilnehmer")
        self.assertContains(response, "3 · Spielplan")
        self.assertContains(response, "4 · Prämie")
        youth = self.client.get(reverse("management_friendlies"),
                                {"tab": "tournaments", "squad": "youth"})
        self.assertContains(youth, "Die U21 hat noch keinen Kader — der Jugendspielbetrieb ist in Arbeit.")

    def test_format_sizes_are_declared_in_wizard_contract(self):
        response = self.client.get(reverse("management_friendlies"),
                                    {"tab": "tournaments"})
        body = response.content.decode()
        for value in ("4", "6", "8", "10", "16"):
            self.assertIn(f'value="{value}"', body)
        self.assertIn("allowed=f==='liga'?[4,6,8,10,16]", body)
        self.assertIn("f==='pokal'?[4,8,16]", body)
        self.assertIn("f==='gruppen_ko'?(n===8?5:6)", body)

    def test_create_returns_json_and_cards_show_reward_amount(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        response = self._create(
            name="Reward Cup", payout_1="1250000")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        tournament = CommunityTournament.objects.get(name="Reward Cup")
        self.assertEqual(tournament.reward_plan["payouts"]["1"], "1250000")
        page = self.client.get(reverse("management_friendlies"),
                               {"tab": "tournaments"})
        self.assertContains(page, "1.250.000")

    def test_join_code_and_application_decision_roles(self):
        tournament = CommunityTournament.objects.create(
            organizer=self.club, name="Private", format="pokal",
            field_size=4, access="code", invitation_code="secret",
            status=CommunityTournament.STATUS_OPEN,
            schedule=self._schedule(2))
        bad = self.client.post(reverse("tournament_action"), {
            "action": "join", "tournament_id": tournament.pk, "code": "bad"})
        self.assertEqual(bad.status_code, 400)
        good = self.client.post(reverse("tournament_action"), {
            "action": "join", "tournament_id": tournament.pk, "code": "secret"})
        self.assertTrue(good.json()["ok"])
        application_t = CommunityTournament.objects.create(
            organizer=self.club, name="Applications", format="pokal",
            field_size=4, access="bewerbung",
            status=CommunityTournament.STATUS_OPEN,
            schedule=[
                (timezone.now() + timedelta(days=20 + i)).strftime(
                    "%Y-%m-%dT%H:%M")
                for i in range(2)
            ])
        applied = self.client.post(reverse("tournament_action"), {
            "action": "apply", "tournament_id": application_t.pk})
        self.assertTrue(applied.json()["ok"])
        app = CommunityTournamentApplication.objects.get(tournament=application_t)
        decided = self.client.post(reverse("tournament_action"), {
            "action": "accept_application", "application_id": app.pk})
        self.assertTrue(decided.json()["ok"])
        self.assertTrue(CommunityTournamentEntry.objects.filter(
            tournament=application_t, club=self.club).exists())

    def test_explicit_start_panel_and_ajax_selector(self):
        tournament = CommunityTournament.objects.create(
            organizer=self.club, name="Startable", format="pokal",
            field_size=4, status=CommunityTournament.STATUS_OPEN,
            schedule=self._schedule(2))
        page = self.client.get(reverse("management_friendlies"),
                               {"tab": "tournaments", "tournament": tournament.pk})
        self.assertContains(page, "Teilnehmerfeld auffüllen")
        self.assertContains(page, "Computer FC")
        self.assertContains(page, 'form[action*="/turnier/action/"]')

    def test_admin_reward_and_non_admin_read_only(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        response = self._create(payout_1="500")
        self.assertTrue(response.json()["ok"])
        self.client.logout()
        self.client.login(username="other-manager", password="password")
        page = self.client.get(reverse("management_friendlies"),
                               {"tab": "tournaments"})
        self.assertContains(page, "Prämien können nur gelesen werden")