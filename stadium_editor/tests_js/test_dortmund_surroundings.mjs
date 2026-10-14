import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {editorPointToDortmund, buildDortmundSurroundings} from '../static/stadium_editor/dortmund_surroundings.js';

const square = [[0, 0], [10, 0], [10, 20], [0, 20], [0, 0]];
const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-5, `${a} != ${b}`);

test('pitch-length axis maps onto the Unity pitch-length axis, not across it', () => {
  assert.deepEqual(editorPointToDortmund([52.5, 0]), [-0, 52.5]);
  assert.deepEqual(editorPointToDortmund([0, 34]), [-34, 0]);
  const [x, z] = editorPointToDortmund([100, 210], {fieldC: [100, 200], axisTheta: Math.PI / 2});
  close(x, 0); close(z, 10);
  const zero = editorPointToDortmund([100, 200], {fieldC: [100, 200], axisTheta: 1});
  zero.forEach(value => close(value, 0));
});

test('editor background preserves mapped polygons, source and explicit heights for rendering', () => {
  const controller = readFileSync(new URL('../static/stadium_editor/editor.js', import.meta.url), 'utf8');
  const fn = controller.match(/function editorBackground\(\)\{[\s\S]*?\n\}/)[0];
  const D = {
    surroundings: {buildings: [{poly: square, h: 12}], roads: [{p: [[0, 0], [10, 0]], w: 2}],
      green: [square], source: 'OpenStreetMap (ODbL)'},
  };
  const data = JSON.parse(JSON.stringify(vm.runInNewContext(`${fn}; editorBackground()`, {D})));
  assert.deepEqual(data.buildings, [square]);
  assert.deepEqual(data.buildingHeights, [12]);
  assert.equal(data.source, 'OpenStreetMap (ODbL)');
  const before = JSON.stringify(data), environment = buildDortmundSurroundings(THREE, data);
  assert.deepEqual(environment.group.userData.counts,
    {green: 1, water: 0, roads: 1, buildings: 1, trees: 0});
  const walls = environment.group.getObjectByName('ENV_BUILDINGS').geometry;
  walls.computeBoundingBox();
  close(walls.boundingBox.min.x, -20); close(walls.boundingBox.max.x, 0);
  close(walls.boundingBox.min.z, 0); close(walls.boundingBox.max.z, 10);
  close(walls.boundingBox.max.y, 12);
  const roofs = environment.group.getObjectByName('ENV_BUILDING_ROOFS').geometry;
  roofs.computeBoundingBox();
  close(roofs.boundingBox.min.y, 12);
  assert.equal(JSON.stringify(data), before, 'rendering must not mutate persisted map data');
  environment.dispose();
});

test('Dortmund 3D receives surroundings and frame from the shared live-scene presentation', () => {
  const controller = readFileSync(new URL('../static/stadium_editor/editor.js', import.meta.url), 'utf8');
  const stage = controller.match(/async function ensureThreeStage\(\)\{[\s\S]*?\n\}/)?.[0];
  assert.ok(stage, '3D stage initialization must exist');
  const branch = stage.match(/if\(isDortmundScene\)\{[\s\S]*?\n    \}/)?.[0];
  assert.ok(branch, 'Dortmund live-scene branch must exist');
  assert.match(branch, /fetch\(EDITOR\.liveSceneUrl,\s*\{credentials:'same-origin'\}\)/);
  assert.match(branch, /if\(!response\.ok\)\s*throw new Error\(/);
  assert.match(branch, /const runtime = \(await response\.json\(\)\)\.presentation;/);
  assert.match(branch, /if\(runtime\?\.renderer !== 'dortmund-spatial'\)\s*throw new Error\(/);
  assert.match(branch, /await mountDortmundScene\(\{\s*element: host,\s*surroundings: runtime\.surroundings,\s*frame: runtime\.frame,/);
});

test('legacy buildings keep 2D precedence and unknown heights; renderer alone supplies 9 metres', () => {
  const controller = readFileSync(new URL('../static/stadium_editor/editor.js', import.meta.url), 'utf8');
  const fn = controller.match(/function editorBackground\(\)\{[\s\S]*?\n\}/)[0];
  const data = JSON.parse(JSON.stringify(vm.runInNewContext(`${fn}; editorBackground()`,
    {D: {bg: {buildings: [square]}, surroundings: {buildings: [{poly: [], h: 12}]}}})));
  assert.deepEqual(data.buildings, [square]);
  assert.deepEqual(data.buildingHeights, [null], 'editor must not invent a source height');
  const before = JSON.stringify(data);
  const environment = buildDortmundSurroundings(THREE, data);
  try {
    assert.equal(environment.group.userData.counts.buildings, 1);
    const walls = environment.group.getObjectByName('ENV_BUILDINGS').geometry;
    walls.computeBoundingBox();
    close(walls.boundingBox.min.x, -20); close(walls.boundingBox.max.x, 0);
    close(walls.boundingBox.min.z, 0); close(walls.boundingBox.max.z, 10);
    close(walls.boundingBox.min.y, -.05); close(walls.boundingBox.max.y, 9);
    const roofs = environment.group.getObjectByName('ENV_BUILDING_ROOFS').geometry;
    roofs.computeBoundingBox();
    close(roofs.boundingBox.min.y, 9); close(roofs.boundingBox.max.y, 9);
    assert.equal(JSON.stringify(data), before, 'schematic height must not be written into source data');
  } finally {
    environment.dispose();
  }
});

test('roads, water and only supplied trees are rendered, with a few batched meshes', () => {
  const environment = buildDortmundSurroundings(THREE, {
    water: [square], roads: [{p: [[0, 0], [10, 0]], w: 2}], trees: [[0, 0], [10, 20]],
  });
  assert.ok(environment.group.getObjectByName('ENV_WATER'));
  const roads = environment.group.getObjectByName('ENV_ROADS').geometry;
  roads.computeBoundingBox();
  close(roads.boundingBox.min.x, -2.5); close(roads.boundingBox.max.x, 2.5);
  const crowns = environment.group.getObjectByName('ENV_TREE_CROWNS');
  assert.equal(crowns.count, 2);
  const matrix = new THREE.Matrix4();
  crowns.getMatrixAt(1, matrix);
  const position = new THREE.Vector3().setFromMatrixPosition(matrix);
  close(position.x, -20); close(position.z, 10);
  assert.ok(environment.group.children.length < 10);
  environment.dispose();
});

test('environment is separate from stadium modes and disposes GPU resources once', () => {
  const environment = buildDortmundSurroundings(THREE,
    {green: [square], buildings: [square], trees: [[0, 0]]});
  const scene = new THREE.Scene();
  scene.add(environment.group);
  const resources = new Set();
  environment.group.traverse(object => {
    if (object.geometry) resources.add(object.geometry);
    if (object.material) resources.add(object.material);
    if (object.isInstancedMesh) resources.add(object);
  });
  let disposals = 0;
  resources.forEach(resource => resource.addEventListener('dispose', () => disposals++));
  environment.dispose(); environment.dispose();
  assert.equal(disposals, resources.size);
  assert.equal(scene.children.length, 0);
  const source = readFileSync(new URL('../static/stadium_editor/dortmund_editor_scene.js', import.meta.url), 'utf8');
  assert.match(source, /scene\.add\(environment\.group\)/);
  assert.match(source, /environment\?\.dispose\(\)/);
  assert.doesNotMatch(source, /environment\.group\.visible\s*=/);
});

test('missing map categories do not invent features; malformed supplied data fails explicitly', () => {
  const empty = buildDortmundSurroundings(THREE);
  assert.deepEqual(empty.group.userData.counts,
    {green: 0, water: 0, roads: 0, buildings: 0, trees: 0});
  assert.equal(empty.group.children.length, 1);
  empty.dispose();
  assert.throws(() => editorPointToDortmund([NaN, 2]), /ungültige Position/);
  assert.throws(() => editorPointToDortmund([0, 0], {axisTheta: Infinity}), /Koordinatenrahmen/);
  assert.throws(() => buildDortmundSurroundings(THREE, {buildings: [square], buildingHeights: [0]}), /Gebäudehöhe/);
  assert.throws(() => buildDortmundSurroundings(THREE, {green: [[]]}), /drei Punkte/);
  assert.throws(() => buildDortmundSurroundings(THREE, {roads: [{p: [[0, 0], [1, 1]], w: -1}]}), /Straßenbreite/);
});