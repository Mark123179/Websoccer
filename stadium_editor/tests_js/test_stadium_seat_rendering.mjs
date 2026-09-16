import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildSeatRenderPlan,
  decodeSeatRle,
  seatBasis,
} from '../static/stadium_editor/stage/seat_rendering.js';

function rotate(point, angle) {
  const c = Math.cos(angle), s = Math.sin(angle);
  return [
    point[0] * c - point[2] * s,
    point[1],
    point[0] * s + point[2] * c,
  ];
}

test('creates one seat instance per physical raster cell with spatial colours intact', () => {
  const plan = buildSeatRenderPlan({
    width: 4, depth: 3.2, rowPitch: .8, seatPitch: .5,
    rows: 2, seats: 4, paletteSize: 8,
    rle: [[1, 1], [1, 2], [1, 3], [1, 4],
          [1, 5], [1, 6], [1, 7], [1, 0]],
  });
  assert.equal(plan.rows, 4);
  assert.equal(plan.cols, 8);
  assert.equal(plan.count, 32);
  assert.deepEqual(Array.from(plan.colours.slice(0, 8)), [1, 1, 2, 2, 3, 3, 4, 4]);
  assert.deepEqual(Array.from(plan.colours.slice(-8)), [5, 5, 6, 6, 7, 7, 0, 0]);
});

test('seat backs point away from the pitch for all four sides and rotated axes', () => {
  const base = {
    NORD: [[-3, 0, 4], [3, 0, 4], [-4, 0, 8], [4, 0, 8]],
    SUED: [[3, 0, -4], [-3, 0, -4], [4, 0, -8], [-4, 0, -8]],
    OST: [[4, 0, 3], [4, 0, -3], [8, 0, 4], [8, 0, -4]],
    WEST: [[-4, 0, -3], [-4, 0, 3], [-8, 0, -4], [-8, 0, 4]],
  };
  for (const angle of [0, Math.PI / 5, Math.PI / 2]) {
    for (const [stand, points] of Object.entries(base)) {
      const [frontLeft, frontRight, backLeft, backRight] =
        points.map(point => rotate(point, angle));
      const axes = seatBasis(frontLeft, frontRight, backLeft, backRight);
      const frontMid = frontLeft.map((value, i) => (value + frontRight[i]) / 2);
      const backMid = backLeft.map((value, i) => (value + backRight[i]) / 2);
      const outward = backMid.map((value, i) => value - frontMid[i]);
      const dot = axes.back.reduce((sum, value, i) => sum + value * outward[i], 0);
      assert.ok(dot > 0, `${stand} back must point away at ${angle}`);
      assert.ok(axes.up[1] > .999, `${stand} seat must remain upright`);
      const rightCrossUp = [
        axes.right[1] * axes.up[2] - axes.right[2] * axes.up[1],
        axes.right[2] * axes.up[0] - axes.right[0] * axes.up[2],
        axes.right[0] * axes.up[1] - axes.right[1] * axes.up[0],
      ];
      const determinant = rightCrossUp.reduce(
        (sum, value, i) => sum + value * axes.back[i], 0,
      );
      assert.ok(determinant > .999, `${stand} basis must be a rotation`);
    }
  }
});

test('rejects truncated, oversized and invalid-colour RLE before rendering', () => {
  assert.throws(() => decodeSeatRle([[3, 0]], 4, 2), /Ungültige Sitzfolge/);
  assert.throws(() => decodeSeatRle([[5, 0]], 4, 2), /Ungültige Sitzfolge/);
  assert.throws(() => decodeSeatRle([[4, 2]], 4, 2), /Ungültige Sitzfolge/);
  assert.throws(
    () => decodeSeatRle(Array.from({length: 10_001}, () => [1, 0]), 10_001, 2),
    /Ungültige Sitzfolge/,
  );
});