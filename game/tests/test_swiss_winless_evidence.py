from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection, transaction
from django.test import TestCase

from game import models as m
from game.club_import.swiss_winless_20261027 import RECORDS


apply_evidence = import_module(
    "game.migrations.0193_swiss_winless_evidence"
).apply_evidence


class SwissWinlessMigrationTests(TestCase):
    def setUp(self):
        self.league = m.League.objects.create(
            name="Swiss evidence test", country="Schweiz", is_playable=False,
        )
        self.clubs = {
            tm: m.Club.objects.create(
                name=f"Evidence {tm}", transfermarkt_id=tm, league=self.league,
                founded_year=1900, budget=123456,
            )
            for tm in (434, 321, 260)
        }
        self.rows = {}
        for tm, club in self.clubs.items():
            self.rows[tm] = m.ClubRecord.objects.create(
                club=club, record_key="longest_winless", source="SEED",
                value_numeric=None, value_display="", holder_name="",
                evidence_status="nicht_belegt", basis="all_competitive",
                context_line="Open record",
            )

    def apply(self):
        apply_evidence(apps, SimpleNamespace(connection=connection))

    def test_only_two_records_change_and_replay_is_noop(self):
        clubs = list(m.Club.objects.order_by("pk").values())
        others = list(m.ClubRecord.objects.exclude(
            pk__in=[self.rows[434].pk, self.rows[321].pk],
        ).values())
        self.apply()
        for tm, fact in RECORDS.items():
            row = m.ClubRecord.objects.get(pk=self.rows[tm].pk)
            self.assertEqual(row.value_numeric, 16)
            self.assertEqual(str(row.period_from), fact["period_from"])
            self.assertEqual(str(row.period_to), fact["period_to"])
            self.assertEqual(row.evidence, fact["sources"])
            self.assertEqual(row.evidence_status, "belegt")
        after = list(m.ClubRecord.objects.order_by("pk").values())
        self.apply()
        self.assertEqual(after, list(m.ClubRecord.objects.order_by("pk").values()))
        self.assertEqual(clubs, list(m.Club.objects.order_by("pk").values()))
        self.assertEqual(others, list(m.ClubRecord.objects.exclude(
            pk__in=[self.rows[434].pk, self.rows[321].pk],
        ).values()))

    def test_conflicting_record_rolls_back_both(self):
        m.ClubRecord.objects.filter(pk=self.rows[321].pk).update(
            value_numeric=99, evidence_status="belegt",
        )
        before = list(m.ClubRecord.objects.order_by("pk").values())
        with self.assertRaisesMessage(RuntimeError, "differs from the approved"):
            with transaction.atomic():
                self.apply()
        self.assertEqual(before, list(m.ClubRecord.objects.order_by("pk").values()))

    def test_empty_workspace_does_not_create_records_or_clubs(self):
        m.ClubRecord.objects.all().delete()
        before = list(m.Club.objects.order_by("pk").values())
        self.apply()
        self.assertFalse(m.ClubRecord.objects.exists())
        self.assertEqual(before, list(m.Club.objects.order_by("pk").values()))

    def test_corrected_record_is_not_overwritten(self):
        row = self.rows[434]
        row.value_numeric = 16
        row.evidence_status = "belegt"
        row.context_line = "Subsequent manual source clarification"
        row.save()
        before = m.ClubRecord.objects.filter(pk=row.pk).values().get()
        self.apply()
        self.assertEqual(before, m.ClubRecord.objects.filter(pk=row.pk).values().get())

    def test_only_matching_open_information_notice_is_resolved(self):
        run = m.SourceImportRun.objects.create(
            source="club_package", club=self.clubs[434],
        )
        common = dict(
            club=self.clubs[434], package=run, entity="record",
            entity_ref="longest_winless", field="records.longest_winless",
            severity="info", resolution_status="open",
        )
        notice = m.ImportIssue.objects.create(
            **common, note="Rekordserie offen: Ersatzwert ohne alte Intertoto-Spiele",
        )
        other = m.ImportIssue.objects.create(
            **common, subkey="unrelated", note="Unrelated historical question",
        )
        self.apply()
        notice.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(notice.resolution_status, "resolved")
        self.assertIsNotNone(notice.resolved_at)
        self.assertEqual(other.resolution_status, "open")
