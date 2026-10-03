"""Coordinate and ownership checks for the shared mapped tree layer."""

from copy import deepcopy
import json
import math

from django.test import SimpleTestCase

from stadium_editor.blueprints.v2 import blueprint_v2
from stadium_editor.surroundings import TREE_CATALOG, with_dortmund_mapped_trees


class DortmundMappedTreeTests(SimpleTestCase):
    def test_map_is_enriched_without_mutating_other_geometry_or_positions(self):
        geometry = {
            'meta': {'fieldC': [0, 0], 'axisTheta': 0},
            'surroundings': {'green': [[[1, 2], [3, 4], [5, 6]]], 'source': 'OpenStreetMap (ODbL)'},
            'blocks': [{'id': 10, 'capacity': 1234}],
        }
        before = deepcopy(geometry)
        result = with_dortmund_mapped_trees(geometry, club_id=3)
        self.assertEqual(geometry, before)
        self.assertEqual(result['blocks'], before['blocks'])
        self.assertEqual(result['surroundings']['green'], before['surroundings']['green'])
        self.assertEqual(len(result['surroundings']['trees']), 248)
        self.assertIn('2026-09-24', result['surroundings']['treeSource'])
        result['surroundings']['trees'][0][0] = -9999
        again = with_dortmund_mapped_trees(geometry, club_id=3)
        self.assertNotEqual(again['surroundings']['trees'][0][0], -9999)

    def test_existing_live_and_legacy_tree_lists_including_empty_have_precedence(self):
        for key in ('bg', 'surroundings'):
            for trees in ([], [[15, 25]]):
                geometry = {key: {'trees': trees}}
                self.assertIs(with_dortmund_mapped_trees(geometry, club_id=3), geometry)

    def test_other_clubs_are_not_given_dortmund_trees(self):
        geometry = {'meta': {'fieldC': [0, 0], 'axisTheta': 0}}
        self.assertIs(with_dortmund_mapped_trees(geometry, club_id=114), geometry)

    def test_shifted_rotated_editor_frame_preserves_pitch_relative_tree_positions(self):
        geometry = {'meta': {'fieldC': [100, -250], 'axisTheta': math.pi / 2}}
        result = with_dortmund_mapped_trees(geometry, club_id=3)
        points = json.loads(TREE_CATALOG.read_text())['points']
        for (x, y), (u, v) in zip(result['surroundings']['trees'], points):
            self.assertAlmostEqual(x, 100 - v)
            self.assertAlmostEqual(y, -250 + u)

    def test_catalog_uses_the_original_map_pitch_axes_not_comparison_fit(self):
        catalog = json.loads(TREE_CATALOG.read_text())
        calibration = catalog['calibration']
        pitch = blueprint_v2.load(blueprint_v2.OSM / 'dortmund.json')
        theta = calibration['pitch_axis_radians']
        self.assertAlmostEqual(pitch['north'][0], math.sin(theta))
        self.assertAlmostEqual(pitch['north'][1], math.cos(theta))
        self.assertAlmostEqual(pitch['pitchLen'], calibration['pitch_length_m'])
        lat0, lon0 = calibration['projection_origin_lat_lon']
        ox, oy = calibration['pitch_center_m']
        origin_lat, origin_lon = catalog['original_origin_lat_lon']
        # Samples from the existing mapped OSM tree extract, not scattered trees.
        for (east, north), actual in zip([[147, 550], [167, 554], [-116, 175]], catalog['points']):
            lat = origin_lat + north / 111320
            lon = origin_lon + east / (111320 * math.cos(math.radians(origin_lat)))
            x, y = blueprint_v2.to_m(lat, lon, lat0, lon0)
            dx, dy = x - ox, y - oy
            expected = [
                dx * math.cos(theta) + dy * math.sin(theta),
                -dx * math.sin(theta) + dy * math.cos(theta),
            ]
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a, b, delta=.001)

    def test_invalid_editor_frame_is_not_silently_used(self):
        for frame in ({'axisTheta': float('nan')}, {'fieldC': [False, 0]}, {'fieldC': [0]}):
            with self.assertRaisesRegex(ValueError, 'Koordinatenrahmen'):
                with_dortmund_mapped_trees({'meta': frame}, club_id=3)