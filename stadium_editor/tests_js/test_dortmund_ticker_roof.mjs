import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {ROOF_NAMES} from '../static/stadium_editor/dortmund_concept.js';
import {TICKER_ROOF_NAMES, setTickerRoofVisibility} from '../static/stadium_editor/dortmund_ticker_roof.js';

const manifest = JSON.parse(readFileSync(new URL(
  '../static/stadium_editor/dortmund_original/manifest.json', import.meta.url), 'utf8'));

test('roof mode covers the exported skin, ceiling, structure and mounted equipment', () => {
  const names = new Set(manifest.meshes.map(mesh => mesh.name));
  for (const name of TICKER_ROOF_NAMES) assert.ok(names.has(name), name);
  for (const name of ROOF_NAMES) assert.ok(TICKER_ROOF_NAMES.has(name), name);
  assert.equal(TICKER_ROOF_NAMES.size, 33);
  for (const mesh of manifest.meshes.filter(mesh => mesh.name.startsWith('center3_'))) {
    assert.ok(TICKER_ROOF_NAMES.has(mesh.name), mesh.name);
  }
});

test('pitch, seating, stands and separate reconstructed facade are not removed', () => {
  const seating = manifest.meshes.filter(mesh => mesh.parts.some(part => /seat/i.test(part.material)));
  assert.ok(seating.length > 0);
  for (const mesh of seating) assert.ok(!TICKER_ROOF_NAMES.has(mesh.name), mesh.name);
  for (const name of ['st081_pitch_0', 'st081_pitch_1', 'right2_13.001', 'back2_1.001']) {
    assert.ok(!TICKER_ROOF_NAMES.has(name));
  }
});

test('on/off changes visibility only and restores the same objects', () => {
  const geometry = {}, material = {}, camera = {height: 50};
  const meshes = [{visible: true, geometry, material}, {visible: true, geometry, material}];
  setTickerRoofVisibility(meshes, false);
  assert.ok(meshes.every(mesh => !mesh.visible));
  assert.equal(meshes[0].geometry, geometry);
  assert.equal(meshes[0].material, material);
  assert.equal(camera.height, 50);
  setTickerRoofVisibility(meshes, true);
  assert.ok(meshes.every(mesh => mesh.visible));
  for (const value of [null, undefined, 'false', 0]) {
    assert.throws(() => setTickerRoofVisibility(meshes, value), TypeError);
  }
});

test('the extended roof toggle stays confined to the admin ticker scene', () => {
  const source = readFileSync(new URL(
    '../static/stadium_editor/dortmund_editor_scene.js', import.meta.url), 'utf8');
  assert.match(source, /if \(tickerPreview && TICKER_ROOF_NAMES\.has\(entry\.name\)\)/);
  assert.match(source, /setTickerRoofVisible\(visible\) \{\s*if \(disposed \|\| !tickerPreview\) return;/);
});
