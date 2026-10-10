import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import vm from 'node:vm';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {
  buildElversbergEnvironment, convertElversbergSurroundings,
} from '../static/stadium_editor/elversberg_blueprint_environment.js';
import {studyPreset} from '../static/stadium_editor/study_camera.js';

const source = {
  style: 'elversberg-blueprint', frame: 'pitch',
  buildings: [{id: 'osm-way-1', osmId: 1, h: 9.379,
    heightStatus: 'conditional-lvgl-envelope',
    poly: [[100, 50], [110, 50], [110, 60], [100, 60]]}],
  roads: [{id: 'road-1', w: 6, p: [[-80, 50], [80, 50]]}],
  green: [[[-40, -60], [-16, -60], [-16, -36], [-40, -36]]],
  vegetation: [{id: 'vegetation-1', height: 3.5,
    poly: [[-40, -60], [-16, -60], [-16, -36], [-40, -36]]}],
};
const build = environment => buildElversbergEnvironment(environment, {
  rot: p => p,
  toWorld: (p, height) => new THREE.Vector3(-p[0], height, p[1]),
});

test('approved Elversberg field preset is the unchanged shared study camera', () => {
  assert.deepEqual(studyPreset('approved-elversberg'), studyPreset('perspective'));
});

test('distant OSM road endpoints cannot shrink the initial 2D editor stadium', () => {
  const editor = fs.readFileSync(
    new URL('../static/stadium_editor/editor.js', import.meta.url), 'utf8',
  );
  const radiusFunction = editor.match(
    /function stadiumMaxRadius\(\)\{[\s\S]*?(?=\nfunction fitView)/,
  )[0];
  const D = {
    meta: {fieldC: [0, 0]}, outline: [[-80, -60], [80, 60]],
    surroundings: {...source, roads: [{p: [[-2000, 0], [2000, 0]]}]},
  };
  const context = vm.createContext({D, blocks: []});
  assert.equal(vm.runInContext(`${radiusFunction};stadiumMaxRadius()`, context), 350);
  D.surroundings = null;
  assert.equal(vm.runInContext('stadiumMaxRadius()', context), 100);
});

test('editor coordinates resolve the exact same canonical geometry and canopy instances', () => {
  const theta = .71, center = [17, -9];
  const point = ([x, y]) => [
    center[0] + x * Math.cos(theta) - y * Math.sin(theta),
    center[1] + x * Math.sin(theta) + y * Math.cos(theta),
  ];
  const raw = structuredClone(source);
  raw.frame = 'editor';
  raw.buildings.forEach(b => { b.poly = b.poly.map(point); });
  raw.roads.forEach(r => { r.p = r.p.map(point); });
  raw.green = raw.green.map(r => r.map(point));
  raw.vegetation.forEach(v => { v.poly = v.poly.map(point); });
  const inputBefore = structuredClone(raw);
  const converted = convertElversbergSurroundings(raw, {
    meta: {axisTheta: theta, fieldC: center},
  });
  assert.deepEqual(raw, inputBefore);
  const actual = build(converted), expected = build(source);
  assert.equal(actual.children.length, expected.children.length);
  actual.children.forEach((mesh, index) => {
    const counterpart = expected.children[index];
    assert.deepEqual(mesh.userData, counterpart.userData);
    assert.equal(mesh.count, counterpart.count);
    if (mesh.isInstancedMesh) {
      const values = mesh.instanceMatrix.array;
      assert.equal(values.length, counterpart.instanceMatrix.array.length);
      values.forEach((value, i) => {
        assert.ok(Math.abs(value - counterpart.instanceMatrix.array[i]) < .0001);
      });
    } else {
      const values = mesh.geometry.attributes.position.array;
      assert.equal(values.length, counterpart.geometry.attributes.position.array.length);
      values.forEach((value, i) => {
        assert.ok(Math.abs(value - counterpart.geometry.attributes.position.array[i]) < .0001);
      });
    }
  });
});

test('building caps and sides have valid separate materials; canopies cover all groups', () => {
  const root = build(source);
  const building = root.children.find(m => m.userData.environmentId === 'osm-way-1');
  assert.equal(building.material[0].color.getHex(), 0x31505a);
  assert.equal(building.material[1].color.getHex(), 0x203a43);
  const canopies = root.children.find(m => m.isInstancedMesh);
  assert.ok(canopies.count > 0);
  for (const group of canopies.geometry.groups) {
    assert.ok(canopies.material[group.materialIndex]);
  }
  const second = build(source).children.find(m => m.isInstancedMesh);
  assert.deepEqual(canopies.instanceMatrix.array, second.instanceMatrix.array);
});
