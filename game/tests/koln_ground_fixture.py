"""Hashed, read-only real DGM witnesses shared by the offline regressions."""
import hashlib
import json
from pathlib import Path

from shapely.geometry import Polygon

from scripts.check_koln_height_profiles import evaluate, renderer_samples
from scripts.koln_profile_sources import NativeDGM, model_projection

DIRECTORY = Path(__file__).parent / "fixtures/koln-ground"


def assert_ground_equal(test, actual, expected):
    """Cropped display origins change IEEE-754 arithmetic, not the surface."""
    if isinstance(expected, dict):
        test.assertEqual(actual.keys(), expected.keys())
        for key in expected:
            assert_ground_equal(test, actual[key], expected[key])
    elif isinstance(expected, list):
        test.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            assert_ground_equal(test, a, b)
    elif isinstance(expected, float):
        test.assertAlmostEqual(actual, expected, delta=1e-9)
    else:
        test.assertEqual(actual, expected)


def load_ground(directory=DIRECTORY):
    manifest = json.loads((directory / "manifest.json").read_text())
    path = directory / manifest["file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("Ground fixture hash mismatch")
    fixture = json.loads(path.read_text())
    if fixture["sources"] != manifest["sources"]:
        raise ValueError("Ground fixture raster manifest mismatch")
    native = NativeDGM(directory, fixture, model_projection(
        fixture["presentation"], fixture["registration"], fixture))
    return fixture, native


def replay_ground(fixture, native):
    apron = Polygon(fixture["apronBoundary"]).buffer(20)
    cutout = Polygon(fixture["cutout"])
    results = {}
    for case in fixture["cases"]:
        p = {**fixture["presentation"],
             "surroundings": {"roads": [], "groundElevation": case["groundElevation"]}}
        offsets = renderer_samples(p, case["profile"]["points"])["offsets"]
        rows = evaluate([case["profile"]], offsets, native, fixture["referenceNHN"],
                        fixture["groundLevel"], apron, cutout)
        results[case["id"]] = dict(zip(("samples", "roadSlopes", "roadGradeChanges"), rows))
    return results
