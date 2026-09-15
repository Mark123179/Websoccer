import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const adapterPath = new URL(
  '../static/stadium_editor/stadium_stage_adapter.js',
  import.meta.url,
);
const adapterSource = await readFile(adapterPath, 'utf8');
const adapterUrl = `data:text/javascript;base64,${Buffer.from(adapterSource).toString('base64')}`;
const {applyEditorDesign} = await import(adapterUrl);
const editorPath = new URL('../static/stadium_editor/editor.js', import.meta.url);
const editorSource = await readFile(editorPath, 'utf8');

const scene = {
  blocks: [{
    id: 1,
    stand: 'SUED',
    tier: 'UNTEN',
    order: 1,
    rows: 2,
    seats: 2,
    quad: [[-2, 0], [2, 0], [2, 4], [-2, 4]],
    z0: 0,
    z1: 2,
    type: 'seating',
    rle: [[4, 0]],
  }],
  roof: {
    mode: 'procedural-ring',
    center: [0, 0],
    depth: 0.5,
    innerEnvelope: [20, 30],
  },
  outline: [[-4, -2], [4, -2], [4, 6], [-4, 6]],
  palette: ['#111111'],
};
const geometry = {meta: {fieldC: [0, 0], axisTheta: 0}};
const originalBlock = {
  id: 1,
  sourceId: 1,
  lineageId: 1,
  stand: 'SUED',
  tier: 'UNTEN',
  order: 1,
  rows: 2,
  seats: 2,
  quad: [[-2, 4], [2, 4], [2, 0], [-2, 0]],
  z0: 0,
  z1: 2,
  type: 'SITZ',
};
const expandedBlock = {
  ...originalBlock,
  id: 2,
  previewId: 'preview-1-1-SITZ',
  simulated: true,
  tier: 'AUSBAU1',
  rows: 3,
  quad: [[-3, 8], [3, 8], [2, 4], [-2, 4]],
  z0: 4,
  z1: 7,
  supportZ: 2,
};

test('preserves procedural roof through expansion and undo without explicit editor roofs', () => {
  const expanded = applyEditorDesign(
    scene,
    [originalBlock, expandedBlock],
    [new Uint8Array(4), new Uint8Array(6)],
    [['#222222']],
    geometry,
    10,
    null,
  );
  assert.deepEqual(expanded.roof, scene.roof);
  assert.equal(expanded.blocks.length, 2);

  const emptyExplicit = applyEditorDesign(
    scene,
    [originalBlock],
    [new Uint8Array(4)],
    [['#222222']],
    geometry,
    4,
    [],
  );
  assert.deepEqual(emptyExplicit.roof, scene.roof);

  const undone = applyEditorDesign(
    scene,
    [originalBlock],
    [new Uint8Array(4)],
    [['#222222']],
    geometry,
    4,
    null,
  );
  assert.deepEqual(undone.roof, scene.roof);
  assert.equal(undone.blocks.length, 1);
});

test('uses transformed explicit editor roofs when segments are available', () => {
  const explicit = [{
    id: 'roof-1',
    quad: [[-3, 9], [3, 9], [2, 5], [-2, 5]],
    heights: [9, 9, 7, 7],
  }];
  const result = applyEditorDesign(
    scene,
    [originalBlock, expandedBlock],
    [new Uint8Array(4), new Uint8Array(6)],
    [['#222222']],
    geometry,
    10,
    explicit,
  );
  assert.equal(result.roof.mode, 'explicit');
  assert.equal(result.roof.segments.length, 1);
  assert.deepEqual(result.roof.segments[0].quad, explicit[0].quad);
  assert.deepEqual(result.roof.segments[0].heights, explicit[0].heights);
});

test('2D roof render helper remains iterable without explicit roof segments', () => {
  const match = editorSource.match(/function roofsFor2D\(\)\{\s*([^}]+)\}/);
  assert.ok(match, 'roofsFor2D helper must remain present in the editor render path');
  assert.match(editorSource, /for\(const roof of roofsFor2D\(\)\)\{/);
  const helperWith = new Function(
    'previewRoofs',
    `return function roofsFor2D(){${match[1]}}`,
  )(() => [{id: 'roof'}]);
  const helperWithout = new Function(
    'previewRoofs',
    `return function roofsFor2D(){${match[1]}}`,
  )(() => null);
  assert.deepEqual(helperWith(), [{id: 'roof'}]);
  assert.deepEqual(helperWithout(), []);
  assert.doesNotThrow(() => {
    for (const _roof of helperWithout()) {
      assert.fail('null fallback must not produce roof segments');
    }
  });
});