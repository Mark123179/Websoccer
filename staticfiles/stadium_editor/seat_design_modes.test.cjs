'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const modes = require('./seat_design_modes.js');
const fs = require('node:fs');
const path = require('node:path');

test('standalone source renderers load their own mode dependency outside the editor', () => {
  for(const name of ['unity_stadium_scene.js', 'dortmund_editor_scene.js']) {
    const source = fs.readFileSync(path.join(__dirname, name), 'utf8');
    assert.match(source, /import ['"]\.\/seat_design_modes\.js\?v=1['"]/);
  }
});

test('mode changes never mutate the custom draft and old saves infer custom', () => {
  const blocks = [{id: 17, rle: [[3, 4], [5, 2]]}];
  const state = {mode: 'custom', draft: {blocks, palette: ['#111111']}};
  const draft = state.draft;
  const saved = {blocks, palette: ['#111111']};
  assert.equal(modes.inferMode(saved), 'custom');
  assert.equal(modes.inferMode(saved, 'original'), 'custom');
  assert.equal(modes.inferMode({blocks: []}), 'original');
  assert.equal(modes.inferMode({seat_mode: 'original', blocks}), 'original');
  assert.equal(modes.inferMode(null), 'original');
  let switched = state;
  for (const mode of ['original', 'custom', 'original']) switched = modes.switchMode(switched, mode);
  assert.equal(switched.mode, 'original');
  assert.equal(switched.draft, draft);
  assert.deepEqual(switched.draft.blocks, blocks);
});

test('custom mode removes source maps and original restores exact source maps and color', () => {
  const texture = {name: 'source crowd texture'};
  const originalColor = {r: .82, g: .12, b: .19, isColor: true,
    clone() { return {...this}; },
    set(hex) { if(hex === '#ffffff') Object.assign(this,{r:1,g:1,b:1}); }};
  const material = {
    map: texture, alphaMap: null, aoMap: null, emissiveMap: texture,
    bumpMap: null, normalMap: null, roughnessMap: null, metalnessMap: null,
    displacementMap: null, lightMap: null, vertexColors: false,
    color: originalColor, needsUpdate: false,
  };
  const source = modes.captureMaterial(material);
  modes.setMaterialMode(material, source, 'custom');
  assert.equal(material.map, null);
  assert.equal(material.emissiveMap, null);
  assert.equal(material.vertexColors, true);
  assert.deepEqual([material.color.r, material.color.g, material.color.b], [1, 1, 1]);
  modes.setMaterialMode(material, source, 'original');
  assert.equal(material.map, texture);
  assert.equal(material.emissiveMap, texture);
  assert.equal(material.vertexColors, false);
  assert.deepEqual([material.color.r, material.color.g, material.color.b], [.82, .12, .19]);
});
