import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings} from '../static/stadium_editor/dortmund_surroundings.js';

const square = [[0, 0], [10, 0], [10, 20], [0, 20]];

test('dark neon surfaces and cyan contours do not wash out under stadium lighting', () => {
  const environment = buildDortmundSurroundings(THREE, {
    green: [square], buildings: [square], roads: [{p: [[0, 0], [10, 10]], w: 1}],
  });
  const group = environment.group;
  const ground = group.getObjectByName('ENV_GROUND');
  assert.ok(ground.material.isMeshBasicMaterial);
  assert.equal(ground.material.color.getHexString(), '03070c');
  assert.equal(ground.material.toneMapped, false);
  for (const name of ['ENV_ROAD_CONTOURS', 'ENV_BUILDING_CONTOURS']) {
    const object = group.getObjectByName(name);
    assert.ok(object.isLineSegments);
    assert.ok(object.material.isLineBasicMaterial);
    assert.equal(object.material.color.getHexString(), '22e6ff');
    assert.equal(object.material.depthWrite, false);
  }
  environment.dispose();
});

test('all catalog trees have batched green crowns with accurately transformed contours', () => {
  const catalog = JSON.parse(readFileSync(new URL('../blueprints/v2/dortmund_mapped_trees.json', import.meta.url)));
  const environment = buildDortmundSurroundings(THREE, {trees: catalog.points});
  const crowns = environment.group.getObjectByName('ENV_TREE_CROWNS');
  const lines = environment.group.getObjectByName('ENV_TREE_CROWN_CONTOURS');
  assert.equal(crowns.count, 248);
  assert.equal(lines.material.color.getHexString(), '30f29c');
  assert.equal(environment.group.children.filter(object => object.isInstancedMesh).length, 2);
  assert.equal(environment.group.children.filter(object => object.isLineSegments).length, 1);
  const edges = new THREE.EdgesGeometry(crowns.geometry);
  const position = edges.getAttribute('position');
  const matrix = new THREE.Matrix4(), vertex = new THREE.Vector3();
  const actual = lines.geometry.getAttribute('position');
  assert.equal(actual.count, position.count * 248);
  for (const index of [0, 120, 247]) {
    crowns.getMatrixAt(index, matrix);
    vertex.fromBufferAttribute(position, 0).applyMatrix4(matrix);
    const offset = position.count * index;
    for (const [expected, value] of [[vertex.x, actual.getX(offset)], [vertex.y, actual.getY(offset)], [vertex.z, actual.getZ(offset)]])
      assert.ok(Math.abs(expected - value) < .0001);
  }
  edges.dispose(); environment.dispose();
});

test('the existing 2D crown renderer is actually invoked for the shared tree data', () => {
  const source = readFileSync(new URL('../static/stadium_editor/editor.js', import.meta.url), 'utf8');
  const renderBase = source.slice(source.indexOf('function renderBase()'), source.indexOf('function drawPitch('));
  assert.match(renderBase, /drawTrees\(ctx, w2s\)/);
  assert.match(source, /function drawTrees[\s\S]*?const trees = editorBackground\(\)\.trees/);
});