"""Historical identity transitions run only against Django's isolated test DB."""
import copy
from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path

from django.db.models import Q
from django.test import TestCase, override_settings
from django.template.loader import render_to_string

from game import models as m
from game.club_import.historical_identity import historical_plan
from game.club_import.issue_lifecycle import lock_reasons
from game.club_import.package_preview import preview_package
from game.club_import.package_service import apply_package, identity
from game.club_import.package_validation import PackageError
from game.tests.package_identity_fixture import identity_package_fixture
from game.tests.test_package_lifecycle import fingerprint
from game.tests.test_package_security import archive


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class HistoricalIdentityTests(TestCase):
    def setUp(self):
        self.manifest, self.data = identity_package_fixture()
        self.data = copy.deepcopy(self.data)
        self.pdata = next(p for p in self.data["players"]
                          if p["squad"]["team"] == "first" and p["squad"]["status"] == "own"
                          and p["ids"]["fmi"]["value"] and p["ids"]["cmtracker"]["value"])
        self.pdata.update(market_values=[], transfers=[])
        self.data.update(players=[self.pdata], persons=[], records=[], titles=[], gaps=[])
        self.league = m.League.objects.create(
            name="2. Bundesliga", country="Deutschland", level=2, is_playable=False)
        self.person = m.HistoricCoach.objects.create(
            name="Historischer Belegname", person_kind="spieler",
            birth_date=date.fromisoformat(self.pdata["date_of_birth"]),
            notes="Diesen Quellbeleg erhalten.")
        self.tm = self.external("TM", self.pdata["ids"]["tm"]["value"])

    def external(self, code, value, **kwargs):
        ds = m.DataSource.objects.get_or_create(code=code, defaults={"name": code})[0]
        return m.PlayerExternalId.objects.create(
            person=self.person, source=ds, external_id=str(value), identity_kind="spieler",
            status="gefunden", source_url="https://example.org/original",
            match_evidence={"original": "archive"}, notes="Originalnotiz", **kwargs)

    def raw(self):
        return archive(self.manifest, self.data)

    def player(self):
        return m.Player.objects.get(transfermarkt_id=self.pdata["ids"]["tm"]["value"])

    def assert_complete(self):
        player = self.player()
        self.person.refresh_from_db()
        self.assertEqual(self.person.linked_player_id, player.pk)
        for provider, code, field in (
            ("tm", "TM", "transfermarkt_id"), ("fmi", "FM", "fm_inside_id"),
            ("cmtracker", "CMTRACKER", None),
        ):
            value = self.pdata["ids"][provider]["value"]
            if field:
                self.assertEqual(getattr(player, field), value)
            self.assertEqual(m.PlayerExternalId.objects.filter(
                Q(player=player) | Q(person=self.person),
                source__code=code, external_id=str(value), identity_kind="spieler").count(), 1)
        self.assertFalse(m.PlayerExternalId.objects.filter(player=player, person=self.person).exists())
        self.tm.refresh_from_db()
        self.assertEqual(self.tm.person_id, self.person.pk)
        self.assertIsNone(self.tm.player_id)
        self.assertEqual(self.tm.match_evidence, {"original": "archive"})
        self.assertEqual(self.tm.source_url, "https://example.org/original")
        self.assertEqual(self.tm.notes, "Originalnotiz")
        self.assertEqual(lock_reasons(player), [])
        return player

    def assert_rejected_without_writes(self, pattern="Historische Identität"):
        before = fingerprint()
        with self.assertRaisesRegex(PackageError, pattern):
            preview_package(self.raw(), self.league)
        self.assertEqual(before, fingerprint())
        with self.assertRaisesRegex(PackageError, pattern):
            apply_package(self.raw(), self.league)
        self.assertEqual(before, fingerprint())

    def test_tm_only_history_preview_is_read_only_and_apply_complete_replay_exact(self):
        before = fingerprint()
        preview = preview_package(self.raw(), self.league)
        self.assertEqual(before, fingerprint())
        link = preview["historical_links"][0]
        self.assertEqual(link["person_id"], self.person.pk)
        self.assertIsNone(link["player_id"])
        html = render_to_string("game/package_preview.html",
                                {"preview": preview, "league": self.league})
        self.assertIn("Historische Spieleridentitäten verknüpfen", html)
        self.assertIn(self.person.name, html)
        apply_package(self.raw(), self.league)
        player = self.assert_complete()
        with self.captureOnCommitCallbacks():
            self.assertEqual(identity(self.pdata["ids"], m.Player).pk, player.pk)
        before = fingerprint()
        self.assertTrue(apply_package(self.raw(), self.league)["unchanged"])
        self.assertEqual(before, fingerprint())

    def test_matching_known_fm_preserves_canonical_owner_and_evidence(self):
        fm = self.external("FM", self.pdata["ids"]["fmi"]["value"])
        self.person.fm_inside_id = str(self.pdata["ids"]["fmi"]["value"])
        self.person.save()
        apply_package(self.raw(), self.league)
        self.assert_complete()
        fm.refresh_from_db()
        self.assertEqual(fm.person_id, self.person.pk)
        self.assertIsNone(fm.player_id)
        self.assertEqual(fm.match_evidence, {"original": "archive"})

    def test_contradictory_fm_canonical_stops(self):
        self.external("FM", 999999991)
        self.assert_rejected_without_writes("FM-ID")

    def test_contradictory_fm_mirror_stops(self):
        self.person.fm_inside_id = "999999991"
        self.person.save()
        self.assert_rejected_without_writes("FM-ID")

    def test_contradictory_dob_stops(self):
        self.person.birth_date = date(1900, 1, 1)
        self.person.save()
        self.assert_rejected_without_writes("Geburtsdatum")

    def test_unknown_dob_is_not_a_conflict(self):
        self.person.birth_date = None
        self.person.save()
        apply_package(self.raw(), self.league)
        self.assert_complete()

    def test_other_historical_person_owning_fm_stops(self):
        other = m.HistoricCoach.objects.create(name="Andere Person", person_kind="spieler")
        fm = self.external("FM", self.pdata["ids"]["fmi"]["value"])
        fm.person = other
        fm.save()
        self.assert_rejected_without_writes("Mehrere")

    def test_source_id_owned_by_other_active_player_stops(self):
        other = m.Player.objects.create(
            first_name="Andere", last_name="Identität", age=20, fm_inside_id=self.pdata["ids"]["fmi"]["value"],
            transfermarkt_id=999999991)
        self.assert_rejected_without_writes("TM-ID")
        self.assertTrue(m.Player.objects.filter(pk=other.pk).exists())

    def test_protected_record_and_historical_person_fields_unchanged(self):
        club = m.Club.objects.create(
            name="Rekordverein", founded_year=1900, league=self.league, budget=0)
        record = m.ClubRecord.objects.create(
            club=club, record_key="top_scorer", source="SEED", value_numeric=42,
            value_display="42 Tore", holder_name="Originalname", holder_coach=self.person,
            source_note="Geschützter Rekordbeleg")
        person_before = m.HistoricCoach.objects.filter(pk=self.person.pk).values().get()
        record_before = m.ClubRecord.objects.filter(pk=record.pk).values().get()
        apply_package(self.raw(), self.league)
        self.assert_complete()
        person_after = m.HistoricCoach.objects.filter(pk=self.person.pk).values().get()
        person_before["linked_player_id"] = self.player().pk
        self.assertEqual(person_before, person_after)
        self.assertEqual(record_before, m.ClubRecord.objects.filter(pk=record.pk).values().get())

    def test_preview_guard_tracks_external_evidence_and_birth_date(self):
        initial = preview_package(self.raw(), self.league)["guard"]
        self.tm.notes = "Neue Belege"
        self.tm.save()
        changed = preview_package(self.raw(), self.league)["guard"]
        self.assertNotEqual(initial, changed)
        self.person.birth_date = None
        self.person.save()
        self.assertNotEqual(changed, preview_package(self.raw(), self.league)["guard"])

    def test_existing_link_is_reused_even_without_player_tm_mirror(self):
        active = m.Player.objects.create(first_name="Aktiver", last_name="Spieler", age=20)
        self.person.linked_player = active
        self.person.save()
        apply_package(self.raw(), self.league)
        self.assertEqual(self.assert_complete().pk, active.pk)
        self.assertEqual(m.Player.objects.count(), 1)

    def test_existing_link_birth_date_conflict_stops(self):
        active = m.Player.objects.create(
            first_name="Aktiver", last_name="Spieler", age=20, date_of_birth=date(1900, 1, 1))
        self.person.linked_player = active
        self.person.save()
        self.assert_rejected_without_writes("Geburtsdatum")

    def test_same_name_without_shared_id_does_not_link(self):
        self.tm.external_id = "999999991"
        self.tm.save()
        self.person.name = self.pdata["display_name"]
        self.person.save()
        self.assertEqual(historical_plan(self.data), [])
        apply_package(self.raw(), self.league)
        self.person.refresh_from_db()
        self.assertIsNone(self.person.linked_player_id)

    def test_package_local_person_conflict_stops_before_write(self):
        self.data["persons"] = [dict(ref="record-player", name=self.person.name,
            tm_type="spieler", tm_id=self.pdata["ids"]["tm"]["value"],
            fmi_id=999999991, date_of_birth=self.pdata["date_of_birth"])]
        self.assert_rejected_without_writes("source IDs disagree")

    def test_batch_dry_run_and_apply_use_historical_path(self):
        from scripts.import_additional_club_packages import import_batch
        before = fingerprint()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "package.zip"
            path.write_bytes(self.raw())
            report = import_batch([path], {}, apply=False)
            self.assertEqual(before, fingerprint())
            self.assertTrue(report["replay_unchanged"])
            self.assertEqual(report["packages"][0]["historical_links"][0]["person_id"], self.person.pk)
            import_batch([path], {}, apply=True)
        self.assert_complete()

    def test_changed_reupload_preserves_person_owned_ids_without_false_conflict(self):
        self.external("FM", self.pdata["ids"]["fmi"]["value"])
        apply_package(self.raw(), self.league)
        player_id = self.assert_complete().pk
        self.pdata["height_cm"] = (self.pdata["height_cm"] or 180) + 1
        preview = preview_package(self.raw(), self.league)
        self.assertEqual(preview["historical_links"][0]["player_id"], player_id)
        self.assertFalse(any("identity." in row.get("field", "")
                             for row in preview["effective"]["gaps"]))
        self.assertFalse(apply_package(self.raw(), self.league)["unchanged"])
        self.assertEqual(self.assert_complete().pk, player_id)
        self.assertEqual(m.Player.objects.count(), 1)
        self.assertFalse(m.ImportIssue.objects.filter(field__startswith="identity.").exists())

    def test_absent_package_fm_does_not_erase_known_historical_id(self):
        known_fm = self.pdata["ids"]["fmi"]["value"]
        fm = self.external("FM", known_fm)
        self.pdata["ids"]["fmi"] = dict(
            self.pdata["ids"]["fmi"], value=None, status="nicht_vorhanden")
        self.data["gaps"] = [dict(
            entity="player", ref=f"tm:{self.pdata['ids']['tm']['value']}",
            field="ids.fmi", severity="player_lock", note="FM-ID fehlt im Paket")]
        apply_package(self.raw(), self.league)
        self.assertEqual(self.player().fm_inside_id, known_fm)
        fm.refresh_from_db()
        self.assertEqual(fm.person_id, self.person.pk)
        self.assertEqual(fm.external_id, str(known_fm))

    def test_fm_only_history_still_requires_noncontradicting_tm(self):
        self.tm.external_id = "999999991"
        self.tm.save()
        self.external("FM", self.pdata["ids"]["fmi"]["value"])
        self.assert_rejected_without_writes("TM-ID")

    def test_conflicting_cmtracker_id_stops_as_well(self):
        self.external("CMTRACKER", 999999991)
        self.assert_rejected_without_writes("CMTRACKER-ID")

    def test_trainer_tm_namespace_does_not_capture_player(self):
        self.tm.identity_kind = "trainer"
        self.tm.save()
        self.person.person_kind = "trainer"
        self.person.save()
        self.assertEqual(historical_plan(self.data), [])
        apply_package(self.raw(), self.league)
        self.person.refresh_from_db()
        self.assertIsNone(self.person.linked_player_id)

    def test_duplicate_roster_fm_is_rejected_before_writes(self):
        other = copy.deepcopy(self.pdata)
        other["ids"]["tm"]["value"] += 1
        self.data["players"].append(other)
        self.assert_rejected_without_writes("Duplicate player source identity")
