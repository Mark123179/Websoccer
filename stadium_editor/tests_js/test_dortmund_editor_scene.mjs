import test from 'node:test';
import assert from 'node:assert/strict';
import {conceptWeights, SIDES, ROOF_NAMES, SHELL_NAMES} from '../static/stadium_editor/dortmund_concept.js';

test('editor stands map to the exported Unity world axes', () => {
  assert.deepEqual(SIDES, {
    SUED: 'PLUS_X', NORD: 'MINUS_X', OST: 'PLUS_Z', WEST: 'MINUS_Z',
  });
  assert.ok(ROOF_NAMES.has('center3_17.001'));
  assert.ok(SHELL_NAMES.has('center3_29.001'));
});

test('only unsaved increases are conceptual; completed baseline stays reference', () => {
  const baseline = new Map([[1, 2000], [2, 3000]]);
  const base = [
    {stand: 'NORD', sourceId: 1, capacity: 2000},
    {stand: 'SUED', sourceId: 2, capacity: 3000},
  ];
  assert.deepEqual(conceptWeights(base, baseline, false), {
    NORD: 0, SUED: 0, OST: 0, WEST: 0,
  });
  const design = [...base, {stand: 'OST', sourceId: null, simulated: true, capacity: 5000}];
  assert.deepEqual(conceptWeights(design, baseline, false), {
    NORD: 0, SUED: 0, OST: .25, WEST: 0,
  });
  assert.equal(conceptWeights([...base, {...base[0], capacity: 3000}], baseline, false).NORD, 1 / 7);
  assert.deepEqual(conceptWeights(base, baseline, true), {
    NORD: 1, SUED: 1, OST: 1, WEST: 1,
  });
});