import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {conceptWeights, SIDES, ROOF_NAMES, SHELL_NAMES} from '../static/stadium_editor/dortmund_concept.js';
import {previewSupportsMaterial, sourceOpaqueColor} from '../static/stadium_editor/dortmund_source_materials.js';
import {RECONSTRUCTED_FACADE_SPANS, reconstructedFacadeVisible} from '../static/stadium_editor/dortmund_reconstructed_facade.js';

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

test('NoDraw surfaces use verified source material state, not a guessed fallback', () => {
  const manifest = JSON.parse(readFileSync(
    new URL('../static/stadium_editor/dortmund_original/manifest.json', import.meta.url), 'utf8'));
  const affected = manifest.meshes.flatMap(mesh =>
    mesh.parts.filter(part => part.material.startsWith('NoDraw_'))
      .map(part => ({mesh: mesh.name, color: sourceOpaqueColor(part), supported: previewSupportsMaterial(part)})));
  assert.deepEqual(affected.map(part => part.mesh).sort(),
    ['back2_1.001', 'left2_1.001', 'right2_13.001']);
  assert.ok(affected.every(part => part.color === '#e7e7e7' && part.supported));
  assert.equal(previewSupportsMaterial({material: 'NoDraw_.003'}), false);
  assert.equal(previewSupportsMaterial({material: 'st051_wall_bsm'}), true);
});

test('the reconstruction is separate, joins the source corner and matches the comparison', () => {
  const [enclosure, lower] = RECONSTRUCTED_FACADE_SPANS;
  assert.deepEqual(enclosure.points.at(-1), lower.points[0]);
  assert.deepEqual(enclosure.points[0], [-93.35, 64.5]);
  assert.deepEqual(lower.points.at(-1), [94.4, -64.3]);
  assert.equal(lower.top, 16.46); // real right2_13 starts here
  assert.ok(enclosure.top <= 36.7);
  const comparison = readFileSync(
    new URL('../../artifacts/mockup-sandbox/src/components/mockups/dortmund-120/_ReconstructedFacade.ts', import.meta.url),
    'utf8');
  const editor = readFileSync(
    new URL('../static/stadium_editor/dortmund_reconstructed_facade.js', import.meta.url), 'utf8');
  const spans = text => text.match(/export const RECONSTRUCTED_FACADE_SPANS = \[([\s\S]*?)\];/)[1];
  assert.equal(spans(editor), spans(comparison));
});

test('Rundum stays free of the reconstructed Bestand wall after camera and light changes', () => {
  let visible = reconstructedFacadeVisible(true, true); // select Rundum
  assert.equal(visible, false);
  visible = reconstructedFacadeVisible(visible, undefined); // move camera
  visible = reconstructedFacadeVisible(visible, undefined); // change daylight
  assert.equal(visible, false);
  visible = reconstructedFacadeVisible(visible, false); // return to Bestand
  assert.equal(visible, true);
});