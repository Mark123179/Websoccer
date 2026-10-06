from pathlib import Path
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from game import models as m
from game.club_import.package_service import apply_package
from game.club_import.package_preview import preview_package
from game.club_import.package_validation import read_package, PackageError
from game.club_import.presentation import loan_line, ordered_transfers
from game.club_profile import build_club_profile_view_model
from game.tests.test_package_lifecycle import fingerprint

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "attached_assets/0_bvb_vereinspaket_2026-10-05_v2_1_1791282305881.zip"
V3 = ROOT / "attached_assets/bvb_vereinspaket_2026-10-05_v3_1791305507594.zip"


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class PackageDisplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.league = m.League.objects.create(name="Bundesliga", country="Deutschland", is_playable=True)
        apply_package(V2, cls.league)
        cls.club = m.Club.objects.get(transfermarkt_id=16)
        cls.user = get_user_model().objects.create_user("n12-creator", is_staff=True)

    def setUp(self):
        self.client.force_login(self.user)

    def hall(self, room="club", **extra):
        return self.client.get(reverse("management_halloffame"),
                               dict(club=self.club.pk, raum=room, modus="echt", **extra))

    def player(self, name):
        return m.Player.objects.get(display_name=name)

    def test_v3_preview_and_category_only_import_preserve_all_other_facts(self):
        before = fingerprint()
        preview = preview_package(V3, self.league)
        self.assertEqual(before, fingerprint())
        self.assertEqual(len(preview["title_changes"]), 6)
        self.assertEqual(preview["changes"], [])
        self.assertEqual(preview["new_strengths"], 0)
        self.assertEqual(preview["issue_balance"], dict(new=0, kept=128, closed=0, reopened=0))
        old_titles = dict(m.ClubTrophyEntry.objects.values_list("pk", "category"))
        apply_package(V3, self.league)
        after = fingerprint()
        changed = {table for table in before if before[table] != after[table]}
        self.assertEqual(changed, {"game_sourceimportrun", "game_clubtrophyentry", "game_clubtrophy"})
        self.assertEqual(m.ClubTrophyEntry.objects.count(), 30)
        self.assertEqual(m.ClubTrophyEntry.objects.filter(category="national_cup").count(), 5)
        self.assertEqual(m.ClubTrophyEntry.objects.filter(category="super_cup").count(), 6)
        self.assertEqual(sum(old_titles[row.pk] != row.category for row in m.ClubTrophyEntry.objects.all()), 6)
        again = fingerprint()
        self.assertTrue(apply_package(V3, self.league)["unchanged"])
        self.assertEqual(again, fingerprint())
        slots = {s["key"]: s for s in self.hall().context["club_slots"]}
        self.assertEqual([slots[k]["value"] for k in ("championships", "cup_wins", "international_titles")],
                         ["8", "5", "3"])
        self.assertFalse(m.ClubRecord.objects.filter(record_key="championships").exists())
        print("N12_V3_EVIDENCE=6 categories; 0 other facts; 156/128/28; v3 replay unchanged")

    def test_v2_counts_do_not_guess_supercups_from_competition_names(self):
        slots = {s["key"]: s for s in self.hall().context["club_slots"]}
        self.assertEqual([slots[k]["value"] for k in ("championships", "cup_wins", "international_titles")],
                         ["8", "11", "3"])

    def test_existing_simulated_titles_add_to_real_titles_without_double_count(self):
        m.ClubRecord.objects.create(club=self.club, source="SIM", record_key="championships",
                                   value_numeric=3, value_display="3")
        m.ClubTrophy.objects.create(club=self.club, origin="sim", category="championship",
                                   competition_name="Sim-Liga", count=3)
        slots = {s["key"]: s for s in self.hall().context["club_slots"]}
        self.assertEqual(slots["championships"]["value"], "11")
        response = self.client.get(reverse("management_halloffame"),
                                  dict(club=self.club.pk, raum="club", modus="neu"))
        self.assertEqual(next(s for s in response.context["club_slots"]
                              if s["key"] == "championships")["value"], "3")

    def test_preview_guard_detects_concurrent_title_change(self):
        before = preview_package(V3, self.league)
        row = m.ClubTrophyEntry.objects.filter(category="national_cup").first()
        row.category = "super_cup"
        row.save(update_fields=["category"])
        self.assertNotEqual(before["guard"], preview_package(V3, self.league)["guard"])

    def test_real_dates_seasons_coach_key_units_and_title_context(self):
        player_slots = {s["key"]: s for s in self.hall("player").context["player_slots"]}
        coach_slots = {s["key"]: s for s in self.hall("coach").context["coach_slots"]}
        self.assertEqual(player_slots["most_titles_player"]["value"], "8")
        self.assertEqual(player_slots["most_titles_player"]["context"], "")
        self.assertEqual(len(m.ClubRecord.objects.get(record_key="most_titles_player").context_line), 233)
        self.assertEqual(coach_slots["most_titles_coach"]["value"], "5")
        self.assertEqual(coach_slots["longest_win_streak_coach"]["value"], "11 Pflichtspielsiege in Folge")
        self.assertEqual(coach_slots["longest_win_streak_coach"]["season"], "2015/16")
        self.assertEqual(coach_slots["longest_tenure"]["period"], "01.07.2008 – 30.06.2015")
        self.assertEqual(player_slots["top_assists"]["unit"], "")
        self.assertEqual(player_slots["most_apps_field"]["unit"], "")
        club_slots = {s["key"]: s for s in self.hall().context["club_slots"]}
        self.assertEqual(club_slots["longest_win_streak"]["value"], "11 Pflichtspielsiege in Folge")
        self.assertEqual(club_slots["longest_win_streak"]["unit"], "")
        self.assertEqual(coach_slots["longest_win_streak_coach"]["unit"], "")
        self.assertEqual(club_slots["biggest_win"]["date"], "05.08.1978")
        self.assertEqual(club_slots["biggest_defeat"]["date"], "29.04.1978")
        self.assertEqual(club_slots["longest_unbeaten"]["season"], "2011/12 bis 2012/13")

    def test_youth_market_value_keeps_decimal_millions(self):
        from game.club_profile_highlights import compact_money
        self.assertEqual(compact_money(1500000), "1,5 Mio. €")
        self.assertEqual(compact_money(2000000), "2 Mio. €")
        self.assertEqual(compact_money(50000), "50 Tsd. €")
        with override_settings(IMPORT_PACKAGE_MODE=False):
            self.assertEqual(compact_money(1500000), "2 Mio. €")

    def test_home_search_transfer_crests_and_news_keep_pilot_prefix(self):
        from django.conf import settings
        from django.urls import get_script_prefix, set_script_prefix
        from unittest.mock import patch
        from game.views import reverse_club_detail
        other_club = m.Club.objects.create(
            name="Navigation source", short_name="NAV", league=self.league,
            founded_year=1900, budget=0)
        targets = list(m.Player.objects.filter(club=self.club).order_by(
            "-market_value", "-potential", "last_name", "first_name"
        ).values_list("pk", flat=True)[:3])
        m.Player.objects.filter(pk__in=targets).update(club=other_club)
        prefix = get_script_prefix()
        try:
            set_script_prefix("/import-pilot/")
            # Exercise the test database, never the running pilot proxy.
            middleware = [item for item in settings.MIDDLEWARE
                          if item != "import_pilot.proxy.PilotProxyMiddleware"]
            with override_settings(FORCE_SCRIPT_NAME="/import-pilot",
                                   MIDDLEWARE=middleware), patch(
                "game.views.current_manager_club", return_value=self.club
            ):
                response = self.client.get("/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'action="/import-pilot/clubs/"')
                self.assertContains(response, f'href="/import-pilot/clubs/{self.club.pk}/news/"')
                self.assertNotContains(response, f'href="/clubs/{self.club.pk}/news/"')
                rows = response.context["transfer_rows"]
                self.assertEqual(len(rows), 3)
                for row in rows:
                    for key in ("from_club_url", "to_club_url"):
                        self.assertTrue(row[key].startswith("/import-pilot/clubs/"))
                        self.assertContains(response, f'href="{row[key]}"')
                self.assertEqual(reverse_club_detail(self.club),
                                 f"/import-pilot/clubs/{self.club.pk}/")
            set_script_prefix("/")
            self.assertEqual(reverse_club_detail(self.club), f"/clubs/{self.club.pk}/")
        finally:
            set_script_prefix(prefix)

    def test_hall_navigation_and_request_form_keep_selected_club(self):
        response = self.hall()
        html = response.content.decode()
        import re
        for href in re.findall(r'href="([^"]*\\?raum=[^"]*)"', html):
            self.assertIn(f"club={self.club.pk}", href)
        self.assertContains(response, f'name="club" value="{self.club.pk}"')
        self.assertNotContains(response, "Player ·")
        self.assertNotContains(response, "national_cup")
        response = self.client.post(reverse("management_halloffame_correction_request"),
            dict(club=self.club.pk, room="coach", mode="echt"))
        self.assertIn(f"club={self.club.pk}", response.url)
        self.assertFalse(m.ClubRecordCorrectionRequest.objects.exists())

    def test_all_seven_loan_lines_and_ramaj_same_day_source_order(self):
        expected = {"Ethan Nwaneri": "01.09.2026", "Takato Yamamoto": "07.07.2026",
                    "Daniel Sumbu": "01.07.2026", "Diant Ramaj": "17.08.2026",
                    "Almugera Kabar": "14.08.2026", "Yan Couto": "06.08.2026",
                    "Elias Benkara": "28.08.2026"}
        for name, start in expected.items():
            text = loan_line(self.player(name))
            self.assertIn("seit " + start, text, name)
            self.assertIn("bis Ende Saison 1", text)
            self.assertNotIn("2027", text)
        ramaj = ordered_transfers(self.player("Diant Ramaj"))
        rows = [r for r in ramaj if r.transfer_date.isoformat() == "2025-02-03"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0].is_loan)
        self.assertFalse(rows[1].is_loan)
        response = self.client.get(reverse("player_detail", args=[self.player("Yan Couto").pk]))
        self.assertContains(response, "Leihgebühr: 5,00 Mio. €")
        self.assertContains(response, "Leih-Ende")
        self.assertContains(response, "verliehen an Como 1907")
        self.assertEqual(response.context["package_ws_club"], self.club)

    def test_professionals_are_team_based_youth_private_and_no_fake_metrics(self):
        profile = build_club_profile_view_model(self.club)
        self.assertEqual(profile["club"]["proPlayerCount"], 28)
        self.assertEqual(profile["club"]["averageProAgeLabel"], "24,4")
        ids = {p.pk for p in m.Player.objects.filter(club=self.club, squad_team="first")}
        self.assertTrue(all(int(row["playerId"]) in ids for row in profile["proHighlights"]))
        self.assertTrue(all(row["metricLabel"] == "–" for row in profile["proHighlights"]
                            if row["metricTone"] in ("grade", "pass_quote")))
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        response = self.client.get(reverse("club_detail", args=[self.club.pk]))
        self.assertContains(response, "1909")
        self.assertNotContains(response, "Zur Jugend")
        self.assertNotContains(response, "Ø Alter Jugend")
        self.assertNotContains(response, "Wertvollster Jugendspieler")
        self.assertNotContains(response, "Tertiär")

    def test_profile_german_money_and_start_points_without_club_name(self):
        response = self.client.get(reverse("player_detail", args=[self.player("Ethan Nwaneri").pk]))
        self.assertContains(response, "35.000.000")
        self.assertNotContains(response, "35,000,000")
        response = self.client.get(reverse("player_detail", args=[self.player("Jan-Mattis Wehrbein").pk]))
        self.assertContains(response, "Spielstartwert")
        self.assertNotContains(response, "Unbekannter Verein")
        self.assertContains(response, "50.000")
        self.assertEqual(m.PlayerMarketValueSnapshot.objects.filter(is_start_value=True).count(), 6)
