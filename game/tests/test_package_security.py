"""Upload security and N67/N68 contract, exclusively in Django's test database."""
import base64
import copy
import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from game import models as m
from game.club_import import package_views as views
from game.club_import.issue_lifecycle import candidates, lock_reasons, prospective_locks
from game.club_import.league_guard import ensure_ready
from game.club_import.package_preview import preview_package
from game.club_import.package_service import apply_package
from game.club_import.package_validation import PackageError, read_package
from game.strength_service import compute_strength_for_player

V2 = Path(__file__).resolve().parents[2] / "attached_assets/0_bvb_vereinspaket_2026-10-05_v2_1_1791282305881.zip"
MARKER = '<span data-package-marker="harmless">Paket & Text</span>'


def archive(manifest, data):
    manifest = copy.deepcopy(manifest)
    raw = json.dumps(data, ensure_ascii=False).encode()
    manifest["data_sha256"] = hashlib.sha256(raw).hexdigest()
    for section in ("players", "persons", "records", "titles"):
        manifest["counts"][section] = len(data[section])
    for severity in ("info", "player_lock", "blocking"):
        manifest["counts"]["gaps_" + severity] = sum(g["severity"] == severity for g in data["gaps"])
    for team, key in (("first", "first_team"), ("u21", "u21")):
        manifest["counts"][key] = sum(p["squad"]["team"] == team for p in data["players"])
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("data.json", raw)
    return stream.getvalue()


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class PackageSecurityTests(TestCase):
    def setUp(self):
        self.manifest, self.data = read_package(V2)
        self.data = copy.deepcopy(self.data)
        self.data["players"] = [next(p for p in self.data["players"]
            if p["squad"]["team"] == "first" and p["squad"]["status"] == "own"
            and p["ids"]["fmi"]["value"] and p["ids"]["cmtracker"]["value"])]
        self.transfer_template = copy.deepcopy(self.data["players"][0]["transfers"][0])
        self.record_template = copy.deepcopy(next(r for r in self.data["records"] if r["key"] == "biggest_win"))
        self.data["players"][0].update(market_values=[], transfers=[])
        self.data.update(persons=[], records=[], titles=[], gaps=[])
        self.league = m.League.objects.create(name="Security test", country="Deutschland", is_playable=True)
        self.user = get_user_model().objects.create_user("package-security", is_staff=True)
        self.factory = RequestFactory()
        self.client.force_login(self.user)

    def raw(self):
        return archive(self.manifest, self.data)

    def call(self, view, values, method="post", **kwargs):
        request = getattr(self.factory, method)("/", values)
        request.user = self.user
        request.session = {}
        return view(request, **kwargs)

    def preview(self, raw):
        return self.call(views.preview, {"league": self.league.pk,
            "package": SimpleUploadedFile("test.zip", raw, content_type="application/zip")})

    def confirm(self, raw, **extra):
        token = signing.dumps(dict(zip=base64.b64encode(raw).decode(),
            league=self.league.pk, user=self.user.pk, baseline="", guard="", **extra),
            salt="club-package-preview", compress=True)
        return self.call(views.confirm, {"token": token})

    def plain(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        response.content.decode("utf-8")

    def test_date_numeric_and_combined_errors_are_plain_on_both_endpoints(self):
        original_manifest, original_data = copy.deepcopy(self.manifest), copy.deepcopy(self.data)
        for case in ("date", "numeric", "combined"):
            with self.subTest(case=case):
                self.manifest, self.data = copy.deepcopy(original_manifest), copy.deepcopy(original_data)
                if case in ("date", "combined"):
                    self.manifest["collected_at"] = MARKER
                if case in ("numeric", "combined"):
                    self.data["stadium"]["stands"]["N"]["seating"]["value"] = MARKER
                if case == "combined":
                    self.data["club"]["name"] = MARKER
                    self.data["gaps"] = [dict(entity="club", ref="tm:16", field="motto",
                        severity="info", note=MARKER)]
                for response in (self.preview(self.raw()), self.confirm(self.raw())):
                    self.plain(response, 400)
                    if case != "numeric":
                        self.assertIn(MARKER, response.content.decode())
                self.assertFalse(m.SourceImportRun.objects.exists())
                self.assertFalse(m.Player.objects.exists())
                self.assertFalse(m.ImportIssue.objects.exists())

    def test_accepted_club_and_gap_text_stays_text_in_preview_and_worklist(self):
        self.data["club"]["name"] = MARKER
        self.data["gaps"] = [dict(entity="club", ref="tm:16", field="motto",
            severity="info", note=MARKER)]
        response = self.preview(self.raw())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, escape(MARKER))
        self.assertNotContains(response, MARKER)
        response = self.client.post(reverse("package_creator:preview"), {
            "league": self.league.pk, "package": SimpleUploadedFile("valid.zip", self.raw())})
        token = response.context["token"]
        response = self.client.post(reverse("package_creator:confirm"), {"token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(m.Club.objects.get(transfermarkt_id=16).name, MARKER)
        self.assertEqual(m.ImportIssue.objects.get(field="motto").note, MARKER)
        response = self.client.get(reverse("package_creator:hub"))
        self.assertContains(response, escape(MARKER))
        self.assertNotContains(response, MARKER)

    def test_role_mode_method_not_found_and_other_bad_requests_are_plain(self):
        self.plain(self.call(views.preview, {}, method="get"), 405)
        self.plain(self.call(views.preview, {}), 400)
        self.plain(self.call(views.preview, {"league": 999999,
            "package": SimpleUploadedFile("ok.zip", self.raw())}), 404)
        self.plain(self.call(views.league, {"name": "", "country": ""}), 400)
        self.plain(self.call(views.images, {}), 403)
        self.plain(self.call(views.confirm, {"token": MARKER}), 400)
        with override_settings(IMPORT_PACKAGE_MODE=False):
            self.plain(self.call(views.hub, {}, method="get"), 403)
        self.user.is_staff = False
        self.plain(self.call(views.hub, {}, method="get"), 403)

    def test_csrf_and_user_binding_still_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("package_creator:confirm"), {"token": "bad"}).status_code, 403)
        token = signing.dumps(dict(zip=base64.b64encode(self.raw()).decode(),
            league=self.league.pk, user=self.user.pk + 999),
            salt="club-package-preview")
        self.plain(self.call(views.confirm, {"token": token}), 403)
        self.assertFalse(m.SourceImportRun.objects.exists())

    def test_n68_fmi_only_professional_not_present_is_unlocked(self):
        player = self.data["players"][0]
        player["ids"]["cmtracker"].update(value=None, status="nicht_vorhanden",
            match="Nachweis: in geprüfter Liga-Datei nicht enthalten")
        player["ratings"]["cmtracker"] = None
        self.assertEqual(prospective_locks(player), [])
        preview = preview_package(self.raw(), self.league)
        self.assertEqual(sum(g["count"] for g in preview["data"]["gaps_by_severity"]
                             if g["severity"] == "player_lock"), 0)
        apply_package(self.raw(), self.league)
        saved = m.Player.objects.get(transfermarkt_id=player["ids"]["tm"]["value"])
        self.assertFalse(saved.import_lock)
        self.assertEqual(lock_reasons(saved), [])
        self.assertEqual(list(saved.source_ratings.values_list("source", flat=True)), ["FM"])
        expected = compute_strength_for_player(saved)
        self.assertTrue(expected["computable"])
        self.assertEqual(saved.strength_profile.base_strength, expected["base_strength"])
        ensure_ready(self.league)

    def test_n68_not_found_professional_without_lock_still_rejected(self):
        self.data["players"][0]["ids"]["cmtracker"].update(value=None, status="nicht_gefunden")
        self.data["players"][0]["ratings"]["cmtracker"] = None
        with self.assertRaisesMessage(PackageError, "Missing first-team CMTracker"):
            read_package(self.raw())
        self.assertFalse(m.Player.objects.exists())

    def test_n67_no_fmi_is_one_player_lock_not_league_lock(self):
        player = self.data["players"][0]
        player["ids"]["fmi"].update(value=None, status="nicht_gefunden")
        player["ratings"]["fminside"] = None
        self.data["gaps"] = [dict(entity="player", ref=f"tm:{player['ids']['tm']['value']}",
            field="ids.fmi", severity="player_lock", note="FMInside nicht gefunden")]
        preview = preview_package(self.raw(), self.league)
        self.assertEqual(sum(g["count"] for g in preview["data"]["gaps_by_severity"]
                             if g["severity"] == "player_lock"), 1)
        apply_package(self.raw(), self.league)
        saved = m.Player.objects.get(transfermarkt_id=player["ids"]["tm"]["value"])
        self.assertTrue(saved.import_lock)
        self.assertTrue(lock_reasons(saved))
        self.assertFalse(m.ImportIssue.objects.filter(severity="blocking").exists())
        ensure_ready(self.league)

    def test_new_gap_refs_visible_without_foreign_club_misattribution(self):
        tm = self.data["players"][0]["ids"]["tm"]["value"]
        refs = [("club", "u21:tm:999", "squad"), ("club", "u21:TOR", "squad"),
            ("club", "u21:ABW", "squad"), ("club", "u21:MIT", "squad"),
            ("club", "u21:ANG", "squad"), ("club", "u21:nr:99", "squad.shirt_number")]
        refs += [("player", f"tm:{tm}", f) for f in
                 ("first_name", "squad.loan_until", "market_values.club", "ids.fmi.match")]
        self.data["gaps"] = [dict(entity=e, ref=r, field=f, note="Nachtrag14 " + f,
                                severity="info") for e, r, f in refs]
        planned = candidates(self.data)
        self.assertTrue(all(not g.get("external_reference") for g in planned))
        response = self.preview(self.raw())
        for _, ref, field in refs:
            self.assertContains(response, field)
            self.assertContains(response, "Nachtrag14 " + field)
        self.assertEqual(preview_package(self.raw(), self.league)["data"]["gaps"], self.data["gaps"])
        apply_package(self.raw(), self.league)
        response = self.client.get(reverse("package_creator:hub"))
        for _, ref, field in refs:
            self.assertContains(response, ref)
            self.assertContains(response, field)
        self.assertEqual(m.ImportIssue.objects.count(), len(refs))

    def test_package_blocking_gap_rejected_before_writes(self):
        self.data["gaps"] = [dict(entity="club", ref="tm:16", field="ids.fmi",
                                severity="blocking", note="Not allowed in a package")]
        with self.assertRaisesMessage(PackageError, "blocking gaps"):
            apply_package(self.raw(), self.league)
        self.assertFalse(m.SourceImportRun.objects.exists())

    def test_package_records_and_transfer_names_are_escaped_in_actual_pages(self):
        fact = copy.deepcopy(self.transfer_template)
        fact["from"] = {"tm_id": None, "name": MARKER}
        fact["to"] = {"tm_id": 16, "name": MARKER}
        fact["fee_text"] = MARKER
        self.data["players"][0]["transfers"] = [fact]
        self.data["players"][0]["market_values"] = [
            {"date": "2026-10-05", "value_eur": 1000000,
             "club": {"tm_id": 16, "name": MARKER}}]
        record = copy.deepcopy(self.record_template)
        record.update(holder=None, value_display=MARKER, context=MARKER,
                      opponent={"tm_id": None, "name": MARKER})
        self.data["records"] = [record]
        apply_package(self.raw(), self.league)
        club = m.Club.objects.get(transfermarkt_id=16)
        player = m.Player.objects.get(transfermarkt_id=self.data["players"][0]["ids"]["tm"]["value"])
        response = self.client.get(reverse("management_halloffame"), {
            "club": club.pk, "raum": "club", "modus": "echt"})
        self.assertContains(response, escape(MARKER))
        self.assertNotContains(response, MARKER)
        response = self.client.get(reverse("player_detail", args=[player.pk]))
        self.assertContains(response, escape(MARKER))
        self.assertNotContains(response, MARKER)

    def test_reference_substring_collision_is_reported_not_silently_fixed(self):
        # Inspection-only scope: this deliberately documents the current deviation.
        # A future authorized fix should replace this expectation with isolation.
        self.data["gaps"] = [dict(entity="club", ref="u21:TOR", field="squad",
                                severity="info", note="Leerer Torwartplatz")]
        self.data["players"][0]["market_values"] = [
            {"date": "2026-10-05", "value_eur": 1000000,
             "club": {"tm_id": None, "name": "TOR"}}]
        planned = candidates(self.data)
        self.assertEqual(planned[0]["external_reference"]["name"], "TOR")
        apply_package(self.raw(), self.league)
        row = m.ImportIssue.objects.get(entity_ref="u21:TOR")
        self.assertEqual(row.external_reference["name"], "TOR")
        self.assertFalse(m.ImportIssue.objects.filter(entity="club_reference", entity_ref="TOR").exists())
