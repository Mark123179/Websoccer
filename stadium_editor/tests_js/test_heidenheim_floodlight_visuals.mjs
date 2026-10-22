import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {heidenheimEmitterPlan, mountHeidenheimFloodlightVisuals}
  from '../static/stadium_editor/heidenheim_floodlight_visuals.js';
import {lampFacesFixture} from './fixtures/heidenheim_lamp_faces.mjs';

const source = JSON.parse(await readFile(new URL('../blueprints/v2/models/880295.json', import.meta.url)));

test('144 distinct lamp discs follow original UV faces and all twelve declared sources', () => {
  const {manifest, buffer} = lampFacesFixture(source);
  const before = JSON.stringify(manifest);
  const emitters = heidenheimEmitterPlan(manifest, buffer);
  assert.equal(emitters.length, 144);
  assert.equal(new Set(emitters.map(e => e.position.toArray().map(v => v.toFixed(5)).join(','))).size, 144);
  for (let panel = 0; panel < 4; panel++) assert.equal(emitters.filter(e => e.panel === panel).length, 36);
  for (const fixture of source.fixtures) assert.ok(emitters.some(e =>
    e.position.distanceTo(new THREE.Vector3(...fixture.position)) < 1e-4));
  assert.equal(JSON.stringify(manifest), before, 'source geometry/photometry must not be mutated');
});

test('missing or displaced emitter evidence fails rather than inventing positions', () => {
  const {manifest, buffer} = lampFacesFixture(source);
  manifest.fixtures[0].position[0] += 1;
  assert.throws(() => heidenheimEmitterPlan(manifest, buffer), /nicht durch Quellgeometrie belegt/);
  manifest.meshes = [];
  assert.throws(() => heidenheimEmitterPlan(manifest, buffer), /nicht durch Quellgeometrie belegt/);
});

test('floodlight visuals switch independently of day, reuse geometry and clean up every resource', () => {
  const {manifest, buffer} = lampFacesFixture(source);
  const scene = new THREE.Scene(), ambient = new THREE.AmbientLight(0xffffff, .08);
  scene.add(ambient);
  const api = mountHeidenheimFloodlightVisuals(scene, manifest, buffer);
  const group = scene.getObjectByName('SOURCE_FLOODLIGHT_VISUALS');
  const lamps = group.getObjectByName('SOURCE_LAMP_DISC_GLOW');
  assert.equal(lamps.count, 144);
  assert.equal(group.children.length, 13);
  assert.equal(group.visible, false);
  const meshes = [...group.children], lampMatrix = lamps.instanceMatrix.array.slice();
  api.update({enabled: true, day: false});
  assert.equal(group.visible, true);
  const nightStrength = group.children[1].material.uniforms.strength.value;
  api.update({enabled: true, day: true});
  assert.equal(group.visible, true, 'daylight must not turn the lights off');
  assert.ok(group.children[1].material.uniforms.strength.value < nightStrength);
  api.update({enabled: false, day: false});
  assert.equal(group.visible, false);
  assert.deepEqual(group.children, meshes, 'toggles must not rebuild any effect');
  assert.deepEqual(lamps.instanceMatrix.array, lampMatrix);
  const lights = [];
  scene.traverse(o => {if (o.isLight) lights.push(o);});
  assert.deepEqual(lights, [ambient], 'visual effects add no functional light sources');
  assert.equal(ambient.intensity, .08);
  let disposed = 0;
  for (const mesh of meshes) {
    mesh.geometry.addEventListener('dispose', () => disposed++);
    mesh.material.addEventListener('dispose', () => disposed++);
  }
  api.dispose(); api.dispose();
  assert.equal(disposed, 26);
  assert.equal(scene.getObjectByName('SOURCE_FLOODLIGHT_VISUALS'), undefined);
});

test('every beam starts at its declared lamp and points along the existing source axis', () => {
  const {manifest, buffer} = lampFacesFixture(source), scene = new THREE.Scene();
  const api = mountHeidenheimFloodlightVisuals(scene, manifest, buffer);
  const group = scene.getObjectByName('SOURCE_FLOODLIGHT_VISUALS');
  manifest.fixtures.forEach((fixture, i) => {
    const beam = group.children[i + 1], normal = new THREE.Vector3(...fixture.direction);
    assert.ok(beam.position.distanceTo(new THREE.Vector3(...fixture.position)) < .031);
    assert.ok(new THREE.Vector3(0, -1, 0).applyQuaternion(beam.quaternion).dot(normal) > .99999);
    assert.equal(beam.material.depthTest, true);
    assert.equal(beam.material.depthWrite, false);
  });
  api.dispose();
});

test('other stadiums remain an exact no-op', () => {
  for (const clubFmiId of [907, 915, 908, 879997]) {
    const scene = new THREE.Scene();
    assert.equal(heidenheimEmitterPlan({clubFmiId}, null), null);
    const api = mountHeidenheimFloodlightVisuals(scene, {clubFmiId}, null);
    api.update({enabled: true, day: false}); api.dispose();
    assert.equal(scene.children.length, 0);
  }
});
