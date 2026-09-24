import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {conceptWeights, SIDES, ROOF_NAMES, SHELL_NAMES} from '../static/stadium_editor/dortmund_concept.js';
import {previewSupportsMaterial} from '../static/stadium_editor/dortmund_source_materials.js';

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

test('unresolved NoDraw materials stay in the source manifest but are not rendered as opaque walls', () => {
  const manifest = JSON.parse(readFileSync(
    new URL('../static/stadium_editor/dortmund_original/manifest.json', import.meta.url), 'utf8'));
  const affected = manifest.meshes.flatMap(mesh =>
    mesh.parts.filter(part => !previewSupportsMaterial(part.material)).map(() => mesh.name)).sort();
  assert.deepEqual(affected, ['back2_1.001', 'left2_1.001', 'right2_13.001']);
  assert.equal(previewSupportsMaterial('NoDraw_.003'), false);
  assert.equal(previewSupportsMaterial('st051_wall_bsm'), true);
});