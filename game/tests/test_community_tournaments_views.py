"""HTTP contract tests for the community tournament desk.

These tests intentionally exercise the public view contract rather than the
tournament algorithm (the latter is covered by the friendlies service tests).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
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

    def _tournament(self, name, organizer=None, status=CommunityTournament.STATUS_OPEN,
                    squad_scope="pro"):
        return CommunityTournament.objects.create(
            organizer=organizer or self.club, name=name, format="pokal",
            field_size=4, status=status, squad_scope=squad_scope,
            schedule=self._schedule(2))

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
                                {"tab": "schedule", "squad": "youth"})
        self.assertContains(youth, "Die U21 hat noch keinen Kader — der Jugendspielbetrieb ist in Arbeit.")
        youth_tournaments = self.client.get(reverse("management_friendlies"),
                                             {"tab": "tournaments", "squad": "youth"})
        self.assertContains(youth_tournaments, "Turniere filtern")

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

    def test_tournament_status_filters_show_only_requested_lifecycle_group(self):
        self._tournament("Open Cup")
        self._tournament("Running Cup", status=CommunityTournament.STATUS_RUNNING)
        self._tournament("Completed Cup", status=CommunityTournament.STATUS_COMPLETED)

        for status, expected, hidden in (
            ("offen", "Open Cup", ("Running Cup", "Completed Cup")),
            ("laufend", "Running Cup", ("Open Cup", "Completed Cup")),
            ("abgeschlossen", "Completed Cup", ("Open Cup", "Running Cup")),
        ):
            with self.subTest(status=status):
                response = self.client.get(reverse("management_friendlies"), {
                    "tab": "tournaments", "tournament_status": status,
                })
                self.assertContains(response, expected)
                for name in hidden:
                    self.assertNotContains(response, name)

    def test_participation_filters_combine_with_status_filter(self):
        organized = self._tournament(
            "Organized Complete", status=CommunityTournament.STATUS_COMPLETED)
        joined = self._tournament(
            "Joined Complete", organizer=self.other,
            status=CommunityTournament.STATUS_COMPLETED)
        self._tournament(
            "Other Complete", organizer=self.other,
            status=CommunityTournament.STATUS_COMPLETED)
        CommunityTournamentEntry.objects.create(tournament=joined, club=self.club)
        CommunityTournamentEntry.objects.create(tournament=joined, club=self.other)

        organized_page = self.client.get(reverse("management_friendlies"), {
            "tab": "tournaments", "tournament_status": "abgeschlossen",
            "tournament_participation": "organized",
        })
        self.assertContains(organized_page, organized.name)
        self.assertNotContains(organized_page, joined.name)

        joined_page = self.client.get(reverse("management_friendlies"), {
            "tab": "tournaments", "tournament_status": "abgeschlossen",
            "tournament_participation": "joined",
        })
        self.assertContains(joined_page, joined.name)
        self.assertContains(joined_page, "2/4 Teams")
        self.assertNotContains(joined_page, organized.name)
        self.assertNotContains(joined_page, "Other Complete")

    def test_tournament_list_query_count_does_not_grow_per_card(self):
        first = self._tournament("First Cup")
        CommunityTournamentEntry.objects.create(
            tournament=first, club=self.club)

        self.client.get(
            reverse("management_friendlies"), {"tab": "tournaments"})
        with CaptureQueriesContext(connection) as one_card_queries:
            one_card_page = self.client.get(
                reverse("management_friendlies"), {"tab": "tournaments"})
        self.assertContains(one_card_page, "1/4 Teams")
        baseline_query_count = len(one_card_queries)

        for index in range(5):
            tournament = self._tournament(f"Additional Cup {index}")
            CommunityTournamentEntry.objects.create(
                tournament=tournament, club=self.other)

        with CaptureQueriesContext(connection) as many_card_queries:
            many_card_page = self.client.get(
                reverse("management_friendlies"), {"tab": "tournaments"})

        self.assertEqual(len(many_card_queries), baseline_query_count)
        self.assertContains(many_card_page, "1/4 Teams", count=6)

    def test_invalid_tournament_filters_fall_back_and_empty_message_matches_filter(self):
        self._tournament("Visible by fallback")
        fallback = self.client.get(reverse("management_friendlies"), {
            "tab": "tournaments", "tournament_status": "unknown",
            "tournament_participation": "strangers",
        })
        self.assertContains(fallback, "Visible by fallback")
        self.assertEqual(fallback.context["tournament_status"], "all")
        self.assertEqual(fallback.context["tournament_participation"], "all")

        empty = self.client.get(reverse("management_friendlies"), {
            "tab": "tournaments", "tournament_status": "laufend",
            "tournament_participation": "joined",
        })
        self.assertContains(
            empty,
            "Keine laufenden Community-Turniere, an denen dein Verein teilnimmt.")

    def test_filter_selection_survives_detail_and_squad_navigation(self):
        tournament = self._tournament(
            "Persistent Cup", organizer=self.other,
            status=CommunityTournament.STATUS_COMPLETED)
        youth_tournament = self._tournament(
            "Youth Persistent Cup", organizer=self.other,
            status=CommunityTournament.STATUS_COMPLETED, squad_scope="youth")
        CommunityTournamentEntry.objects.create(tournament=tournament, club=self.club)
        CommunityTournamentEntry.objects.create(tournament=youth_tournament, club=self.club)
        params = {
            "tab": "tournaments", "squad": "pro",
            "tournament_status": "abgeschlossen",
            "tournament_participation": "joined",
        }
        listing = self.client.get(reverse("management_friendlies"), params)
        detail_href = (
            f"?tab=tournaments&squad=pro&tournament={tournament.pk}"
            f"&tournament_status=abgeschlossen"
            "&amp;tournament_participation=joined")
        self.assertContains(listing, detail_href)

        detail = self.client.get(reverse("management_friendlies"), {
            **params, "tournament": tournament.pk,
        })
        self.assertContains(
            detail,
            "?tab=tournaments&squad=pro&tournament_status=abgeschlossen"
            "&amp;tournament_participation=joined")

        youth = self.client.get(reverse("management_friendlies"), {
            **params, "squad": "youth",
        })
        self.assertContains(youth, f"<h3>{youth_tournament.name}</h3>", html=True)
        self.assertNotContains(youth, f"<h3>{tournament.name}</h3>", html=True)
        self.assertContains(
            youth,
            "?tab=tournaments&squad=pro&tournament_status=abgeschlossen"
            "&amp;tournament_participation=joined")