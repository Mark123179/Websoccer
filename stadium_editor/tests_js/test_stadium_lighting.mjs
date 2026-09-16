import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

import {
  buildFloodlightPlan,
} from '../static/stadium_editor/stage/stadium_lighting.js';

const block = (id, stand, order, z1, quad) => ({
  id, stand, order, z1, quad,
});

test('four conventional masts produce four deterministic field-facing sources', () => {
  const scene = {
    standsBounds: [-80, -60, 80, 60],
    steckbrief: {floodlights: {type: 'mast', count: 4, height: 38}},
  };
  const first = buildFloodlightPlan(scene);
  const second = buildFloodlightPlan(structuredClone(scene));
  assert.deepEqual(first, second);
  assert.equal(first.type, 'mast');
  assert.equal(first.fixtures.length, 4);
  assert.equal(first.sources.length, 4);
  assert.deepEqual(
    first.fixtures.map(fixture => fixture.position),
    [
      [86, 66, 39.5], [-86, 66, 39.5],
      [-86, -66, 39.5], [86, -66, 39.5],
    ],
  );
  assert.ok(first.fixtures.every(fixture =>
    Math.abs(fixture.target[0]) <= 36 &&
    Math.abs(fixture.target[1]) <= 22 &&
    fixture.target[2] === 0));
});

test('rim plan uses only the highest outer edge with stable 12 metre spacing', () => {
  const low = block('WEST-LOW', 'WEST', 0, 8, [
    [-58, -24], [-58, 24], [-70, 30], [-70, -30],
  ]);
  const high = block('WEST-HIGH', 'WEST', 0, 18, [
    [-70, -30], [-70, 30], [-78, 30], [-78, -30],
  ]);
  const east = block('OST-HIGH', 'OST', 0, 16, [
    [58, 24], [58, -24], [70, -30], [70, 30],
  ]);
  const scene = {
    blocks: [low, high, east],
    steckbrief: {floodlights: {type: 'rim'}},
  };
  const plan = buildFloodlightPlan(scene);
  assert.equal(plan.type, 'rim');
  assert.equal(plan.fixtures.length, 10);
  assert.equal(plan.sources.length, 6);
  assert.ok(plan.fixtures.every(fixture => fixture.kind === 'rim'));
  assert.ok(plan.fixtures.every(fixture =>
    fixture.position[2] === 17.6 || fixture.position[2] === 19.6));
  assert.deepEqual(
    plan,
    buildFloodlightPlan({...scene, blocks: [east, low, high]}),
    'scene block order must not change rim subdivision',
  );
});

test('stadiums without configured floodlights have no functional sources', () => {
  assert.deepEqual(
    buildFloodlightPlan({blocks: []}),
    {type: 'none', fixtures: [], sources: []},
  );
});

test('real Camp Nou rim keeps visual fixtures but caps functional sources', async () => {
  const path = new URL('../blueprints/v2/campnou_v2.json', import.meta.url);
  const scene = JSON.parse(await readFile(path, 'utf8'));
  const plan = buildFloodlightPlan(scene);
  assert.equal(plan.type, 'rim');
  assert.equal(plan.fixtures.length, 102);
  assert.equal(plan.sources.length, 12);
  assert.ok(plan.sources.length <= 12);
  assert.ok(plan.sources.every(source =>
    plan.fixtures.some(fixture =>
      fixture.position.every((value, index) =>
        value === source.position[index]))));
});