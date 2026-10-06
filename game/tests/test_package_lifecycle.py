import hashlib
import json
from pathlib import Path
from collections import Counter
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from game import models as m
from game.club_import.package_service import apply_package
from game.club_import.issue_lifecycle import reconcile, plan, lock_reasons
from game.club_import.package_preview import preview_package
from game.strength_service import compute_strength_for_player

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "attached_assets/bvb_vereinspaket_2026-10-05_1_1791225377498.zip"
V2 = ROOT / "attached_assets/0_bvb_vereinspaket_2026-10-05_v2_1_1791282305881.zip"


def fingerprint():
    from django.apps import apps
    return {model._meta.db_table: hashlib.sha256(json.dumps(
        list(model.objects.order_by("pk").values()), sort_keys=True, default=str).encode()).hexdigest()
        for model in apps.get_app_config("game").get_models() if not model._meta.proxy}


def counts(baseline_clubs=()):
    return dict(players=m.Player.objects.count(), strength=m.PlayerStrengthProfile.objects.count(),
        locks=m.Player.objects.filter(import_lock=True).count(),
        source_archive=m.PlayerSourceRatingSnapshot.objects.count(),
        market_values=m.PlayerMarketValueSnapshot.objects.count(),
        transfers=m.PlayerTransferHistory.objects.count(), records=m.ClubRecord.objects.count(),
        titles=m.ClubTrophyEntry.objects.count(), issues=m.ImportIssue.objects.count(),
        open=m.ImportIssue.objects.filter(resolution_status="open").count(),
        package_closed=m.ImportIssue.objects.filter(resolution_status="package").count(),
        clubs=m.Club.objects.exclude(pk__in=baseline_clubs).count())


@override_settings(IMPORT_PACKAGE_MODE=True)
class PackageSequenceTests(TestCase):
    def test_v1_v2_v2(self):
        baseline_clubs = list(m.Club.objects.values_list("pk", flat=True))
        league = m.League.objects.create(name="Bundesliga", country="Deutschland", is_playable=True)
        apply_package(V1, league)
        first = counts(baseline_clubs)
        before = fingerprint()
        preview = preview_package(V2, league)
        self.assertEqual(before, fingerprint(), "Preview must not write any game row")
        self.assertEqual(preview["issue_balance"]["closed"], 28)
        self.assertEqual(len(preview["changes"]), 28)
        self.assertEqual(preview["new_strengths"], 14)
        apply_package(V2, league)
        second = counts(baseline_clubs)
        expected = dict(players=51, strength=49, locks=2, source_archive=132,
            market_values=637, transfers=322, records=24, titles=30,
            issues=156, open=128, package_closed=28, clubs=1)
        self.assertEqual(second, expected)
        samples = {}
        for name, target in {"Ethan Nwaneri": (145,181), "Samuele Inácio": (120,166),
                "Luca Reggiani": (116,152), "Luke Fahrenhorst": (90,160),
                "Bennedikt Wüstenhagen": (92,100)}.items():
            player = m.Player.objects.get(display_name=name)
            result = compute_strength_for_player(player)
            from game import strength_engine as se
            ratings = {r.source: r for r in player.source_ratings.all()}
            fm, cm = ratings.get("FM"), ratings.get("CMTRACKER")
            base = se.calculate_base_200(fm.rating if fm else None, cm.rating if cm else None)
            potential = se.calculate_potential_200(fm.potential if fm else None,
                                                 cm.potential if cm else None, base)
            actual = base, potential
            self.assertEqual(actual, target, name)
            samples[name] = actual
        before_replay = fingerprint()
        self.assertTrue(apply_package(V2, league)["unchanged"])
        self.assertEqual(before_replay, fingerprint())
        p = m.Player.objects.get(display_name="Ethan Nwaneri")
        external = p.external_ids.get(source__code="CMTRACKER")
        external.status = "nicht_gefunden"
        external.save()
        self.assertTrue(lock_reasons(p))
        external.status = "von_hand"
        external.save()
        m.PlayerSourceRating.objects.filter(player=p, source="CMTRACKER").delete()
        self.assertTrue(any("Rating fehlt" in r for r in lock_reasons(p)))
        external.status = "nicht_vorhanden"
        external.external_id = None
        external.save()
        self.assertEqual(lock_reasons(p), [])
        print("N46_EVIDENCE=" + json.dumps(dict(v1=first, v2=second, samples=samples,
            replay_unchanged=True, preview_read_only=True, n48_cases=True), ensure_ascii=False))


@override_settings(IMPORT_PACKAGE_MODE=True)
class IssueMatchingTests(TestCase):
    def setUp(self):
        self.league = m.League.objects.create(name="Test", country="Deutschland")
        self.club = m.Club.objects.create(name="Club", founded_year=1909, league=self.league, budget=0)
        self.run = m.SourceImportRun.objects.create(source="club_package", club=self.club)

    def row(self, note):
        return dict(entity="club", ref="u21", field="squad", note=note, severity="info")

    def test_multiple_text_change_and_transitions(self):
        reconcile(self.run, [self.row("A"), self.row("B")])
        a = m.ImportIssue.objects.get(note="A")
        self.assertTrue(a.subkey)
        reconcile(self.run, [self.row("A"), self.row("C")])
        self.assertEqual(m.ImportIssue.objects.get(note="B").resolution_status, "package")
        self.assertEqual(m.ImportIssue.objects.get(note="A").pk, a.pk)
        reconcile(self.run, [self.row("A")])
        self.assertEqual(m.ImportIssue.objects.get(note="A").pk, a.pk)
        self.assertEqual(m.ImportIssue.objects.get(note="A").subkey, "")
        reconcile(self.run, [self.row("A"), self.row("B")])
        self.assertEqual(m.ImportIssue.objects.get(note="A").pk, a.pk)
        self.assertEqual(m.ImportIssue.objects.get(note="B").resolution_status, "open")

    def test_switch_to_different_single_text_preserves_closed_history(self):
        reconcile(self.run, [self.row("A")])
        reconcile(self.run, [self.row("B"), self.row("C")])
        reconcile(self.run, [self.row("D")])
        self.assertEqual(m.ImportIssue.objects.filter(resolution_status="open").count(), 1)
        self.assertEqual(m.ImportIssue.objects.get(note="D").subkey, "")
        self.assertEqual(m.ImportIssue.objects.count(), 4)

    def test_manual_missing_equal_and_conflicting_values(self):
        from game.club_import.package_preview import preserved_manual, clear_superseded_manual
        self.club.transfermarkt_id = 16
        self.club.save(update_fields=["transfermarkt_id"])
        row = m.ImportIssue.objects.create(club=self.club, package=self.run,
            entity="player", entity_ref="tm:12", field="ids.fmi", note="Missing",
            manual_value=42, resolution_status="resolved", severity="info")
        data = dict(club={}, stadium={}, records=[], players=[
            dict(ids=dict(tm=dict(value=12), fmi=dict(value=None, status="nicht_gefunden")),
                 display_name="Player", market_values=[], transfers=[])])
        effective, changes = preserved_manual(data, self.club)
        self.assertEqual(effective["players"][0]["ids"]["fmi"], dict(value=42, status="von_hand"))
        self.assertEqual(changes, [])
        self.assertIsNone(data["players"][0]["ids"]["fmi"]["value"])
        for incoming in (42, 43):
            data["players"][0]["ids"]["fmi"] = dict(value=incoming, status="gefunden")
            effective, changes = preserved_manual(data, self.club)
            self.assertEqual(effective["players"][0]["ids"]["fmi"]["status"], "gefunden")
            self.assertEqual(len(changes), int(incoming != 42))
        clear_superseded_manual(data, self.club)
        row.refresh_from_db()
        self.assertIsNone(row.manual_value)

    def test_image_lifecycle_and_transparent_missing_badge(self):
        from game.club_import.static_assets import EMPTY_PNG
        from PIL import Image
        from io import BytesIO
        self.assertEqual(Image.open(BytesIO(EMPTY_PNG)).getpixel((0, 0)), (0, 0, 0, 0))
        reconcile(self.run, [dict(entity="player", ref="tm:1", field="image", note="Missing", severity="info")], field="image")
        row = m.ImportIssue.objects.get(field="image")
        reconcile(self.run, [], field="image")
        row.refresh_from_db()
        self.assertEqual(row.resolution_status, "package")
        reconcile(self.run, [dict(entity="player", ref="tm:1", field="image", note="Missing", severity="info")], field="image")
        row.refresh_from_db()
        self.assertEqual(row.resolution_status, "open")

    def test_identity_conflict_never_reidentifies_existing_player(self):
        from game.club_import.package_validation import read_package
        _, data = read_package(V1)
        incoming = next(p for p in data["players"] if p["ids"]["fmi"]["value"] is not None)
        other = m.Player.objects.create(first_name="Existing", last_name="Identity", age=20,
            potential=60, club=self.club, owner_club=self.club, transfermarkt_id=999999,
            fm_inside_id=incoming["ids"]["fmi"]["value"])
        apply_package(V1, self.league)
        other.refresh_from_db()
        self.assertEqual(other.transfermarkt_id, 999999)
        self.assertFalse(m.Player.objects.filter(transfermarkt_id=incoming["ids"]["tm"]["value"]).exists())
        self.assertTrue(m.ImportIssue.objects.filter(entity="player",
            entity_ref=f"tm:{incoming['ids']['tm']['value']}", field="identity.fmi",
            severity="player_lock", resolution_status="open").exists())

    def test_creator_bulk_start_guard_redirects_without_writes(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        user = get_user_model().objects.create_user("guard-creator", is_staff=True)
        self.client.force_login(user)
        reconcile(self.run, [dict(entity="club", ref="club", field="stadium",
                                 severity="blocking", note="Required value missing")])
        before = m.SeasonFixture.objects.count()
        response = self.client.post(reverse("creator_league_spielplan_generate",
            args=[self.league.pk]), dict(season="1", confirm_reset="1"))
        self.assertRedirects(response, reverse("creator_league_edit", args=[self.league.pk]),
                             fetch_redirect_response=False)
        self.assertEqual(m.SeasonFixture.objects.count(), before)
        from django.contrib import admin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        request = RequestFactory().post("/admin/league/start/", dict(season="1"))
        request.user, request.session = user, self.client.session
        request._messages = FallbackStorage(request)
        response = admin.site._registry[m.League].schedule_view(request, self.league.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(m.SeasonFixture.objects.count(), before)

    def test_t4_public_squad_hides_youth_and_reads_real_stadium(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        user = get_user_model().objects.create_user("t4-reader")
        self.client.force_login(user)
        m.Stadium.objects.create(club=self.club, name="SOURCE STADIUM",
                                 real_capacity_national=81365)
        response = self.client.get(reverse("club_detail", args=[self.club.pk]))
        self.assertContains(response, "SOURCE STADIUM")
        self.assertContains(response, "81.365")
        m.Player.objects.create(first_name="HIDDEN YOUTH", last_name="ONLY", age=18,
                                potential=60, club=self.club, squad_team="u21")
        response = self.client.get(reverse("club_professional_squad", args=[self.club.pk]))
        self.assertNotContains(response, "U21 · Creator-Prüfung")
        self.assertNotContains(response, "HIDDEN YOUTH")
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        m.ClubTrophyEntry.objects.create(club=self.club, origin="real", source_row_key="test",
            competition_name="SOURCE CUP", season="2025/26", category="cup")
        response = self.client.get(reverse("management_halloffame"),
                                    dict(club=self.club.pk, modus="echt", raum="club"))
        self.assertContains(response, "SOURCE CUP")
        response = self.client.get(reverse("management_halloffame"), dict(club="invalid"))
        self.assertEqual(response.status_code, 404)

    def test_manual_lock_label_and_open_balance_follow_actual_data(self):
        from game.club_import.package_validation import read_package
        from game.club_import.issue_lifecycle import candidates
        _, data = read_package(V2)
        player = next(p for p in data["players"] if p["ids"]["fmi"]["status"] == "nicht_gefunden")
        player["ids"]["fmi"] = dict(value=129876, status="von_hand")
        rows = candidates(data, self.club)
        ref = f"tm:{player['ids']['tm']['value']}"
        gap = next(r for r in rows if r["entity"] == "player" and r["ref"] == ref and r["field"] == "ids.fmi")
        self.assertEqual(gap["severity"], "player_lock")
        player["ratings"]["fminside"] = dict(rating=90, potential=90, raw={})
        rows = candidates(data, self.club)
        gap = next(r for r in rows if r["entity"] == "player" and r["ref"] == ref and r["field"] == "ids.fmi")
        self.assertEqual(gap["severity"], "info")
        reconcile(self.run, [self.row("Manual acknowledgement")])
        row = m.ImportIssue.objects.get(note="Manual acknowledgement")
        row.resolution_status = "resolved"
        row.save()
        self.assertEqual(plan(self.club, [self.row("Manual acknowledgement")])[2]["kept"], 0)

    def test_manual_reference_correction_preserves_history_rows(self):
        from copy import deepcopy
        from game.club_import.package_service import real_histories
        from game.club_import.package_preview import preserved_manual
        from django.utils import timezone
        player = m.Player.objects.create(first_name="History", last_name="Test", age=20,
            potential=60, club=self.club, owner_club=self.club, transfermarkt_id=17)
        pdata = dict(ids=dict(tm=dict(value=17)), market_value_eur=10000, transfers=[],
            market_values=[dict(date="2020-01-01", value_eur=10000,
                                club=dict(name="External Club", tm_id=None))])
        envelope = dict(players=[pdata], club={}, stadium={}, records=[], gaps=[])
        self.run.package_data = envelope
        self.run.collected_at = timezone.now()
        self.run.save()
        real_histories(player, pdata, self.run)
        row = m.ImportIssue.objects.get(entity="club_reference")
        row.manual_value, row.resolution_status = 42, "resolved"
        row.save()
        effective, changes = preserved_manual(envelope, self.club)
        self.assertEqual(changes, [])
        real_histories(player, effective["players"][0], self.run)
        self.assertEqual(m.PlayerMarketValueSnapshot.objects.filter(player=player).count(), 1)
        self.assertEqual(m.PlayerMarketValueSnapshot.objects.get(player=player).club_tm_id, 42)
        supplied = deepcopy(envelope)
        supplied["players"][0]["market_values"][0]["club"]["tm_id"] = 43
        effective, changes = preserved_manual(supplied, self.club)
        self.assertEqual(changes[0]["old"], 42)
        self.assertEqual(changes[0]["new"], 43)
        run = m.SourceImportRun.objects.create(source="club_package", club=self.club,
            package_data=supplied, collected_at=timezone.now())
        real_histories(player, effective["players"][0], run)
        self.assertEqual(m.PlayerMarketValueSnapshot.objects.filter(player=player).count(), 1)
        self.assertEqual(m.PlayerMarketValueSnapshot.objects.get(player=player).club_tm_id, 43)
        self.assertEqual(m.Club.objects.filter(transfermarkt_id__in=[42, 43]).count(), 0)

    def test_all_start_guards_and_csrf(self):
        from django.core.exceptions import ValidationError
        from django.test import Client
        from game.season_service import get_season_state, simulate_matchday
        m.ImportIssue.objects.create(club=self.club, package=self.run, entity="club",
            entity_ref="tm:16", field="identity", note="Blocking", severity="blocking")
        for fn in (lambda: get_season_state(self.league, "1"),
                   lambda: simulate_matchday(self.league, "1", 1),
                   lambda: m.LeagueSeasonState.objects.create(league=self.league, season="1"),
                   lambda: m.SeasonFixture.objects.create(league=self.league, home_club=self.club,
                                                         away_club=self.club, matchday=1, season="1")):
            with self.assertRaises(ValidationError):
                fn()
        user = get_user_model().objects.create_user(username="csrf-test", is_staff=True)
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.post(reverse("package_creator:league"), dict(name="New", country="DE")).status_code, 403)

    def test_signed_preview_and_changed_state_rejected(self):
        user = get_user_model().objects.create_user(username="guard-test", is_staff=True)
        self.client.force_login(user)
        with V2.open("rb") as handle:
            response = self.client.post(reverse("package_creator:preview"), dict(package=handle, league=self.league.pk))
        self.assertEqual(response.status_code, 200)
        token = response.context["token"]
        self.assertContains(response, "Neu berechnete Spielerstärken")
        before = fingerprint()
        self.assertEqual(self.client.post(reverse("package_creator:confirm"), dict(token=token + "x")).status_code, 400)
        self.assertEqual(before, fingerprint())
        self.league.is_playable = not self.league.is_playable
        self.league.save()
        changed = fingerprint()
        self.assertEqual(self.client.post(reverse("package_creator:confirm"), dict(token=token)).status_code, 400)
        self.assertEqual(changed, fingerprint())

    def test_simple_text_changes_preserve_manual_status(self):
        reconcile(self.run, [self.row("A")])
        row = m.ImportIssue.objects.get()
        row.resolution_status = "resolved"
        row.manual_value = 17
        row.save()
        reconcile(self.run, [self.row("New wording")])
        row.refresh_from_db()
        self.assertEqual(row.note, "New wording")
        self.assertEqual(row.resolution_status, "resolved")
        self.assertEqual(m.ImportIssue.objects.count(), 1)

    def test_creator_boundary_and_cancel(self):
        user = get_user_model().objects.create_user(username="package-test", password="test-only")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("package_creator:hub")).status_code, 403)
        user.is_staff = True
        user.save()
        self.assertEqual(self.client.get(reverse("package_creator:hub")).status_code, 200)
        before = fingerprint()
        with V2.open("rb") as handle:
            response = self.client.post(reverse("package_creator:preview"), dict(package=handle, league=self.league.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(before, fingerprint())
        self.assertEqual(self.client.post(reverse("package_creator:issue", args=[999]), dict(action="resolve")).status_code, 404)
