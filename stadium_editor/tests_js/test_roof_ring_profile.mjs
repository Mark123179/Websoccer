import test from 'node:test';
import assert from 'node:assert/strict';
import {ringVertexHeight, ringFasciaHeights} from
  '../static/stadium_editor/stage/roof_ring_profile.mjs';

test('measured ring slopes from outside to inside; fascia begins at inner edge', () => {
  const inner = [{x: -58.688, y: -44.852}, {x: 57.252, y: -44.852}];
  const zOuter = 41.03, zInner = 39.53;
  // ShapeGeometry stores points as Float32.
  const sampledInner = new Float32Array([-58.688, -44.852]);
  assert.equal(ringVertexHeight(sampledInner[0], sampledInner[1],
    inner, zInner, zOuter), 39.53);
  assert.equal(ringVertexHeight(-104.8166, -85.6734,
    inner, zInner, zOuter), 41.03);
  assert.deepEqual(ringFasciaHeights(zInner, 1.2),
    {top: 39.53, bottom: 38.33});
  assert.equal(zOuter - zInner, 1.5);
});