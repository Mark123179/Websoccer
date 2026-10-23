from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from game import models as m
from game.club_import.package_service import apply_package, persons_and_facts


@override_settings(IMPORT_PACKAGE_MODE=True)
class PackageFactCorrectionsTests(TestCase):
    def setUp(self):
        self.league = m.League.objects.create(
            name="Fact correction test", country="England", is_playable=False)
        self.club = m.Club.objects.create(
            name="Fact test club", short_name="FTC", founded_year=1900,
            budget=0, league=self.league)
        self.old = {
            "club": {}, "stadium": {}, "players": [], "gaps": [], "titles": [],
            "persons": [{"ref": "p10", "name": "Previous coach", "tm_id": 23534,
                         "tm_type": "trainer", "nationality": "England"}],
            "records": [{"key": "longest_win_streak_coach", "value_numeric": 8,
                         "holder": {"person_ref": "p10"}, "season": "1999/00",
                         "basis": "all_competitive", "status": "belegt"}],
        }
        self.manifest = {
            "club": {"tm_id": 931}, "data_sha256": "b" * 64,
            "format": "club_package", "format_version": 1,
            "titles_through_season": "2025/26", "source_versions": {},
            "position_window": {},
        }
        self.run = m.SourceImportRun.objects.create(
            source="club_package", club=self.club, target_league=self.league,
            package_data=self.old, manifest=self.manifest, data_sha256="a" * 64,
            status="applied", applied_at=timezone.now(), titles_through_season="2025/26",
        )
        # The package lookup uses the TM identity, without changing the club itself.
        m.Club.objects.filter(pk=self.club.pk).update(transfermarkt_id=931)
        persons_and_facts(self.old, self.club, self.run, False)

    def test_only_historical_facts_change_and_replay_is_noop(self):
        data = deepcopy(self.old)
        data["persons"][0].update(name="Bedford Jezzard", tm_id=23530)
        data["records"][0]["season"] = "1962/63"
        before = m.Club.objects.filter(pk=self.club.pk).values().get()
        old_holder = m.ClubRecord.objects.get(club=self.club).holder_coach_id
        with patch("game.club_import.package_service.read_package",
                   return_value=(self.manifest, data)), \
             patch("game.club_import.package_service.initialize_player") as initialize, \
             patch("game.club_import.package_service.project_ratings") as ratings:
            result = apply_package(b"test-fixture", self.league)
            self.assertFalse(result["unchanged"])
            initialize.assert_not_called()
            ratings.assert_not_called()
            record = m.ClubRecord.objects.get(club=self.club)
            self.assertEqual(record.holder_name, "Bedford Jezzard")
            self.assertEqual(record.season, "1962/63")
            self.assertNotEqual(record.holder_coach_id, old_holder)
            self.assertTrue(m.HistoricCoach.objects.filter(pk=old_holder).exists())
            self.assertEqual(m.Club.objects.filter(pk=self.club.pk).values().get(), before)
            records_before = list(m.ClubRecord.objects.values())
            runs_before = m.SourceImportRun.objects.count()
            self.assertTrue(apply_package(b"test-fixture", self.league)["unchanged"])
            self.assertEqual(list(m.ClubRecord.objects.values()), records_before)
            self.assertEqual(m.SourceImportRun.objects.count(), runs_before)
