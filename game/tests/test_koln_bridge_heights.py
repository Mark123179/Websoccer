"""No deck evidence must never turn the original DGM alarms green."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
import json
from pathlib import Path

from shapely.geometry import box

from scripts.koln_bridge_heights import UNRESOLVED, bridge_records, bridge_report, is_bridge
from scripts.check_koln_height_profiles import evaluate, profiles_for, renderer_samples, spaced, summarize
from game.tests.koln_ground_fixture import load_ground, replay_ground


class RealBridgeGroundTests(TestCase):
    def test_two_complete_real_profiles_keep_ground_alarms_and_unresolved_decks_separate(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Offline only")), \
                patch("requests.sessions.Session.request", side_effect=AssertionError("Offline only")):
            fixture, native = load_ground()
            actual = replay_ground(fixture, native)
        evidence = json.loads(Path("docs/stadium/koln-bridge-height-evidence.json").read_text())
        cases = [case for case in fixture["cases"]
                 if case["role"] == "complete_bridge_ground_profile"]
        profiles = [case["profile"] for case in cases]
        rows = [[], [], []]
        for case in cases:
            result = actual[case["id"]]
            for target, key in zip(rows, ("samples", "roadSlopes", "roadGradeChanges")):
                target.extend(result[key])
        report = bridge_report(profiles, *rows)
        self.assertEqual(report["unresolvedCount"], 2)
        self.assertEqual(report["deckHeightsApplied"], 0)
        for case, profile, declared in zip(cases, report["profiles"], evidence["criticalBridges"]):
            with self.subTest(osm=declared["osm"]):
                samples = actual[case["id"]]["samples"]
                registered = {**fixture["presentation"], "surroundings": {
                    "roads": [{"p": case["editorPoints"]}],
                    "groundElevation": case["groundElevation"]}}
                road = renderer_samples(registered, [])["roads"][0]
                self.assertEqual(spaced(road), case["profile"]["points"])
                self.assertEqual(case["sourceFeature"]["osm"], declared["osm"])
                self.assertTrue(is_bridge(case["sourceFeature"]["tags"]))
                self.assertEqual(profile["osm"], declared["osm"])
                self.assertEqual(profile["heightStatus"], UNRESOLVED)
                self.assertIsNone(profile["deckSource"])
                self.assertEqual(profile["deckValidation"], "not_evaluable_without_spatial_deck_evidence")
                self.assertEqual(samples[0]["xz"], declared["modelXZStart"])
                self.assertEqual(samples[-1]["xz"], declared["modelXZEnd"])
                self.assertEqual([min(r["nativeNHN"] for r in samples),
                                  max(r["nativeNHN"] for r in samples)], declared["nativeGroundRangeNHN"])
                if "worstGroundGradeErrorPP" in declared:
                    self.assertAlmostEqual(profile["worstGroundSlope"]["gradeErrorPP"],
                                           declared["worstGroundGradeErrorPP"], delta=1e-9)
                if "worstGroundGradeChangeErrorPP" in declared:
                    self.assertAlmostEqual(profile["worstGroundGradeChange"]["gradeChangeErrorPP"],
                                           declared["worstGroundGradeChangeErrorPP"], delta=1e-9)
        # Re-evaluate the actual same surfaces without the bridge label. The
        # additive declaration must not alter/filter a single ground result.
        baseline = deepcopy(fixture)
        for case in baseline["cases"]:
            case["profile"].pop("heightStatus", None)
        plain = replay_ground(baseline, native)
        for case in fixture["cases"]:
            for key, records in actual[case["id"]].items():
                self.assertEqual([{k: v for k, v in row.items() if k != "heightStatus"}
                                  for row in records], plain[case["id"]][key])


class BridgeHeightTests(TestCase):
    def test_source_tags_not_layer_or_neighbour_determine_bridge_status(self):
        for value in ("yes", "viaduct", "movable", "boardwalk"):
            self.assertTrue(is_bridge({"bridge": value}))
        for tags in ({}, {"bridge": "no"}, {"bridge": "0"}, {"bridge": "false"},
                     {"layer": "1"}, {"tunnel": "yes"}):
            self.assertFalse(is_bridge(tags))

    def test_declarations_bind_identity_index_and_original_geometry_without_deck(self):
        data = {"roads": [{"p": [[0, 0], [4, 0]]}, {"p": [[1, 2], [3, 4]]}]}
        evidence = {"features": {"roads": [
            {"osm": "way/5229974", "tags": {"name": "Aachener Straße", "bridge": "yes", "layer": "1"}},
            {"osm": "way/2", "tags": {"highway": "path", "layer": "1"}},
        ]}}
        before = deepcopy((data, evidence))
        rows = bridge_records(data, evidence)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["osm"], "way/5229974")
        self.assertEqual(rows[0]["status"], UNRESOLVED)
        self.assertIsNone(rows[0]["deckSource"])
        rows[0]["editorPoints"][0][0] = 42
        self.assertEqual((data, evidence), before)
        with self.assertRaisesRegex(ValueError, "identities"):
            bridge_records({"roads": []}, evidence)

    def test_separate_bridge_ground_report_preserves_every_control_and_failure(self):
        presentation = {"surroundings": {"groundElevation": {
            "origin": [-200, -200], "step": 20, "cols": 21, "rows": 21}}}
        evidence = {"features": {"roads": [{"osm": "way/362049118",
                     "tags": {"highway": "path", "bridge": "yes", "layer": "1"}}]}}
        # Three zones plus a native ridge BETWEEN 20 m display supports.
        profiles = profiles_for(presentation, [[[x, 0] for x in range(-10, 71, 2)]] , evidence)
        bridge = profiles[-1]
        bridge["points"] = [[x, 0] for x in range(-10, 71, 2)]
        native = lambda x, z: 100 + max(0, 4-abs(x-10))
        args = ([0]*41, native, 100, 0, box(-8, -8, 0, 8), box(-4, -2, -2, 2))
        actual = evaluate([bridge], *args)
        baseline_profile = {k: v for k, v in bridge.items() if k != "heightStatus"}
        baseline = evaluate([baseline_profile], *args)
        for rows, baseline_rows in zip(actual, baseline):
            self.assertEqual([{k: v for k, v in r.items() if k != "heightStatus"} for r in rows],
                             baseline_rows)
        report = summarize(*actual)
        self.assertFalse(report["ok"])
        self.assertEqual(report["violations"], summarize(*baseline)["violations"])
        separate = bridge_report([bridge], *actual)
        self.assertEqual(separate["deckHeightsApplied"], 0)
        self.assertEqual(separate["unresolvedCount"], 1)
        self.assertEqual(separate["profiles"][0]["groundSampleCount"], len(actual[0]))
        self.assertEqual(separate["profiles"][0]["worstGroundSlope"],
                         max(actual[1], key=lambda s: abs(s["gradeErrorPP"])))
