"""Creator endpoint regressions for canonical historical source ownership."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from game import models as m
from game.club_import.package_service import source
from game.tests.test_package_lifecycle import fingerprint


@override_settings(IMPORT_PACKAGE_MODE=True, IMPORT_PACKAGE_IMAGE_CHECK_ENABLED=False)
class ManualHistoricalIdentityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="creator", is_staff=True)
        self.client.force_login(self.user)
        league = m.League.objects.create(name="Testliga", country="Deutschland")
        self.club = m.Club.objects.create(
            name="Testverein", founded_year=1900, league=league, budget=0)
        self.player = m.Player.objects.create(
            first_name="Aktiver", last_name="Spieler", age=25, transfermarkt_id=123)
        self.person = m.HistoricCoach.objects.create(
            name="Originalname", person_kind="spieler", linked_player=self.player,
            notes="Historischen Quellbeleg bewahren.")
        self.run = m.SourceImportRun.objects.create(source="club_package", club=self.club)
        self.issue = m.ImportIssue.objects.create(
            club=self.club, package=self.run, entity="player", entity_ref="tm:123",
            field="ids.fmi", severity="info", note="ID ergänzen")
        self.url = reverse("package_creator:issue", args=[self.issue.pk])
        self.record = m.ClubRecord.objects.create(
            club=self.club, record_key="top_scorer", source="SEED",
            holder_coach=self.person, holder_name="Originalname",
            value_numeric=42, value_display="42 Tore", source_note="Originalbeleg")
        # Ensure fingerprint comparisons include an already-existing session.
        self.client.get(reverse("package_creator:hub"))

    def external(self, value=None, code="FM", **kwargs):
        return m.PlayerExternalId.objects.create(
            person=self.person, source=source(code), identity_kind="spieler",
            external_id=str(value) if value is not None else None,
            status="gefunden" if value else "nicht_gefunden",
            checked_at=date(2020, 1, 1), source_url="https://example.org/original",
            profile_url="https://example.org/profile", notes="Originalnotiz",
            match_evidence={"original": "archive"}, **kwargs)

    def post(self, value=456):
        return self.client.post(self.url, {"action": "value", "value": str(value)})

    def assert_rejected(self, text, value=456):
        before = fingerprint()
        response = self.post(value)
        self.assertEqual(response.status_code, 400)
        self.assertIn(text, response.content.decode())
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertEqual(before, fingerprint(), "Conflict must leave all game data untouched")

    def test_add_to_historical_placeholder_preserves_owner_evidence_and_records(self):
        row = self.external()
        before = m.PlayerExternalId.objects.filter(pk=row.pk).values().get()
        person_before = m.HistoricCoach.objects.values().get(pk=self.person.pk)
        record_before = m.ClubRecord.objects.values().get(pk=self.record.pk)
        self.assertEqual(self.post().status_code, 302)
        after = m.PlayerExternalId.objects.filter(pk=row.pk).values().get()
        for field in ("external_id", "status", "checked_at", "updated_at"):
            before.pop(field)
            after.pop(field)
        self.assertEqual(before, after)
        row.refresh_from_db()
        self.assertEqual((row.external_id, row.status), ("456", "von_hand"))
        self.assertEqual(row.checked_at, date.today())
        self.assertIsNone(row.player_id)
        self.assertEqual(row.person_id, self.person.pk)
        self.assertFalse(m.PlayerExternalId.objects.filter(player=self.player).exists())
        self.player.refresh_from_db()
        self.assertEqual(self.player.fm_inside_id, 456)
        self.assertEqual(person_before, m.HistoricCoach.objects.values().get(pk=self.person.pk))
        self.assertEqual(record_before, m.ClubRecord.objects.values().get(pk=self.record.pk))
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.manual_value, 456)
        self.assertEqual(self.issue.resolution_status, "resolved")

    def test_existing_id_keeps_all_evidence_and_repeated_post_is_unchanged(self):
        row = self.external(456)
        before = m.PlayerExternalId.objects.values().get(pk=row.pk)
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(before, m.PlayerExternalId.objects.values().get(pk=row.pk))
        snapshot = fingerprint()
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(snapshot, fingerprint())

    def test_historical_id_wins_over_empty_active_placeholder(self):
        historical = self.external(456)
        active = m.PlayerExternalId.objects.create(
            player=self.player, source=historical.source, external_id=None)
        self.assertEqual(self.post().status_code, 302)
        active.refresh_from_db()
        self.assertIsNone(active.external_id)
        self.assertEqual(m.PlayerExternalId.objects.filter(external_id="456").count(), 1)

    def test_new_source_without_placeholder_creates_single_active_owner(self):
        self.external(123, code="TM")
        self.assertEqual(self.post().status_code, 302)
        row = m.PlayerExternalId.objects.get(source__code="FM")
        self.assertEqual(row.player_id, self.player.pk)
        self.assertIsNone(row.person_id)
        self.assertEqual(row.status, "von_hand")

    def test_canonical_tm_resolves_linked_active_player_without_mirror(self):
        self.external(123, code="TM")
        self.external(456)
        self.player.transfermarkt_id = None
        self.player.save(update_fields=["transfermarkt_id"])
        self.assertEqual(self.post().status_code, 302)
        self.player.refresh_from_db()
        self.assertEqual(self.player.fm_inside_id, 456)
        self.assertFalse(m.ClubExternalId.objects.exists())

    def test_conflicting_historical_id_is_rejected(self):
        self.external(789)
        self.assert_rejected("Widersprüchliche FM-ID")

    def test_conflicting_active_canonical_id_is_rejected(self):
        self.external(456)
        m.PlayerExternalId.objects.create(
            player=self.player, source=source("FM"), external_id="789")
        self.assert_rejected("Widersprüchliche FM-ID")

    def test_conflicting_active_mirror_is_rejected(self):
        self.external(456)
        self.player.fm_inside_id = 789
        self.player.save(update_fields=["fm_inside_id"])
        self.assert_rejected("Widersprüchliche FM-ID")

    def test_conflicting_historical_mirror_is_rejected(self):
        self.external()
        self.person.fm_inside_id = "789"
        self.person.save(update_fields=["fm_inside_id"])
        self.assert_rejected("Widersprüchliche FM-ID")

    def test_id_owned_by_unlinked_historical_identity_is_rejected(self):
        row = self.external(456)
        row.person = m.HistoricCoach.objects.create(name="Andere", person_kind="spieler")
        row.save()
        self.assert_rejected("anderen Identität")

    def test_id_owned_by_other_active_player_is_rejected(self):
        other = m.Player.objects.create(first_name="Andere", last_name="Person", age=20)
        m.PlayerExternalId.objects.create(
            player=other, source=source("FM"), external_id="456")
        self.assert_rejected("anderen Identität")

    def test_other_active_mirror_without_canonical_row_is_rejected(self):
        m.Player.objects.create(first_name="Andere", last_name="Person", age=20,
                                fm_inside_id=456)
        self.assert_rejected("Spiegel-ID")

    def test_other_historical_mirror_without_canonical_row_is_rejected(self):
        m.HistoricCoach.objects.create(name="Andere", person_kind="spieler", fm_inside_id="456")
        self.assert_rejected("anderen Rekordperson")

    def test_trainer_namespace_does_not_block_same_player_source_id(self):
        other = m.HistoricCoach.objects.create(name="Trainer", person_kind="trainer")
        m.PlayerExternalId.objects.create(
            person=other, source=source("TM"), identity_kind="trainer", external_id="123")
        self.issue.field = "ids.tm"
        self.issue.save()
        self.assertEqual(self.post(123).status_code, 302)
        self.assertEqual(m.PlayerExternalId.objects.filter(external_id="123").count(), 2)

    def test_cmtracker_has_no_player_mirror_but_still_preserves_canonical_owner(self):
        row = self.external(456, code="CMTRACKER")
        self.issue.field = "ids.cmtracker"
        self.issue.save()
        before = m.PlayerExternalId.objects.values().get(pk=row.pk)
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(before, m.PlayerExternalId.objects.values().get(pk=row.pk))

    def test_unknown_player_does_not_write_club_id(self):
        self.issue.entity_ref = "tm:999"
        self.issue.save()
        self.assert_rejected("Spieler wurde nicht gefunden")

    def test_conflicting_tm_owner_and_active_mirror_abort_before_source_addition(self):
        other = m.Player.objects.create(first_name="Andere", last_name="Person", age=20)
        self.person.linked_player = other
        self.person.save(update_fields=["linked_player"])
        self.external(123, code="TM")
        self.assert_rejected("widersprüchlichen aktiven Identitäten")

    def test_multiple_linked_historical_people_are_rejected(self):
        m.HistoricCoach.objects.create(
            name="Mehrdeutig", person_kind="spieler", linked_player=self.player)
        self.assert_rejected("nicht eindeutig")

    def test_matching_api_football_id_preserves_history_and_populates_mirror(self):
        row = self.external(456, code="API_FOOTBALL")
        self.issue.field = "ids.api_football"
        self.issue.save()
        before = m.PlayerExternalId.objects.values().get(pk=row.pk)
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(before, m.PlayerExternalId.objects.values().get(pk=row.pk))
        self.player.refresh_from_db()
        self.assertEqual(self.player.api_football_id, 456)
