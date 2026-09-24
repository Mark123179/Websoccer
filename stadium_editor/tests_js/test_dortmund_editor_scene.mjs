import test from 'node:test';
import assert from 'node:assert/strict';
import {conceptWeights, SIDES, ROOF_NAMES, SHELL_NAMES} from '../static/stadium_editor/dortmund_concept.js';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {addExistingFacade} from '../static/stadium_editor/dortmund_existing_facade.js';

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

test('the missing short and long Bestand elevations are real surfaces, not a camera overlay', () => {
  const world = new THREE.Group();
  const facade = addExistingFacade(THREE, world);
  const ray = new THREE.Raycaster();
  ray.set(new THREE.Vector3(-200, 15, 0), new THREE.Vector3(1, 0, 0));
  assert.ok(ray.intersectObjects(world.children, true).some(hit =>
    hit.object.name === 'RECONSTRUCTED_SHORT_MINUS_X_WALL'));
  ray.set(new THREE.Vector3(0, 15, -200), new THREE.Vector3(0, 0, 1));
  assert.ok(ray.intersectObjects(world.children, true).some(hit =>
    hit.object.name === 'RECONSTRUCTED_LONG_MINUS_Z_WALL'));
  assert.ok(world.children[0].children.some(child =>
    child.name === 'RECONSTRUCTED_CORNER_MINUS_X_MINUS_Z_WALL'));
  facade.dispose();
});