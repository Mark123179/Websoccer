import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import test from 'node:test';

import {applyEditorDesign} from '../static/stadium_editor/stadium_stage_adapter.js';
import {
  blockSupportQuads,
  facadeEdgeTopHeights,
} from '../static/stadium_editor/stage/stadium_geometry_helpers.js?v=25';

const require = createRequire(import.meta.url);
const geometryApi = require('../static/stadium_editor/expansion_geometry.js');

const rotate = (point, angle, offset = [0, 0]) => {
  const c = Math.cos(angle), s = Math.sin(angle);
  return [
    offset[0] + point[0] * c - point[1] * s,
    offset[1] + point[0] * s + point[1] * c,
  ];
};
const makeBlock = (id, stand, center, tangent, depth = 8) => {
  const radius = Math.hypot(...center);
  const normal = [center[0] / radius, center[1] / radius];
  const half = tangent / 2;
  const innerCenter = [center[0] - normal[0] * depth, center[1] - normal[1] * depth];
  const left = [-normal[1] * half, normal[0] * half];
  return {
    id, sourceId: id, lineageId: id, stand, tier: 'UNTER', order: id,
    rows: 10, seats: 100, z0: 0, z1: 8, type: 'SITZ',
    quad: [
      [center[0] + left[0], center[1] + left[1]],
      [center[0] - left[0], center[1] - left[1]],
      [innerCenter[0] - left[0], innerCenter[1] - left[1]],
      [innerCenter[0] + left[0], innerCenter[1] + left[1]],
    ],
  };
};

function fixture(angle = 0, asymmetric = false) {
  const offset = [17, -9];
  const specs = [
    ['OST', [asymmetric ? 92 : 80, 0], 38],
    ['NORD', [0, asymmetric ? 68 : 80], 48],
    ['WEST', [asymmetric ? -74 : -80, 0], 42],
    ['SUED', [0, asymmetric ? -97 : -80], 56],
    ['SUED', [-58, -58], 30],
  ];
  const blocks = specs.map(([stand, center, width], id) => {
    const block = makeBlock(id, stand, center, width);
    block.quad = block.quad.map(point => rotate(point, angle, offset));
    return block;
  });
  return {
    blocks,
    geometry: {meta: {fieldC: offset, axisTheta: angle}},
  };
}

for (const [name, angle, asymmetric] of [
  ['rotated', Math.PI / 2, false],
  ['rotated asymmetric', Math.PI / 5, true],
]) {
  test(`assigns every exterior block to exactly one of all four stands (${name})`, () => {
    const {blocks, geometry} = fixture(angle, asymmetric);
    const selected = ['NORD', 'OST', 'SUED', 'WEST'].flatMap(stand =>
      geometryApi.expansionEnvelope(stand, blocks, blocks, geometry)
    );
    assert.deepEqual(new Set(selected.map(block => block.id)), new Set(blocks.map(block => block.id)));
    assert.equal(selected.length, blocks.length);
    for (const stand of ['NORD', 'OST', 'SUED', 'WEST']) {
      assert.ok(
        geometryApi.expansionEnvelope(stand, blocks, blocks, geometry).length,
        `${stand} must receive an expandable sector`,
      );
    }
  });
}

test('SOUTH then WEST uses the shared south-west corner only once', () => {
  const {blocks, geometry} = fixture(Math.PI / 7, true);
  const south = geometryApi.expansionEnvelope('SUED', blocks, blocks, geometry);
  const west = geometryApi.expansionEnvelope('WEST', blocks, blocks, geometry);
  const sharedCornerId = 4;
  assert.equal(south.filter(block => block.id === sharedCornerId).length, 1);
  assert.equal(west.filter(block => block.id === sharedCornerId).length, 0);
  assert.equal([...south, ...west].filter(block => block.id === sharedCornerId).length, 1);
});

test('roof, outline and facade points follow the numeric current exterior edge', () => {
  const scene = {
    blocks: [{
      id: 1, stand: 'SUED', rows: 2, seats: 2,
      quad: [[-2, 0], [2, 0], [2, 4], [-2, 4]],
      z0: 0, z1: 2, rle: [[4, 0]],
    }],
    outline: [[-2, 4], [2, 4]],
    facadeSegments: [[[-2, 4], [2, 4]]],
    palette: ['#111'],
  };
  const current = {
    id: 2, previewId: 'preview-1', lineageId: 1, simulated: true,
    stand: 'SUED', rows: 2, seats: 2,
    quad: [[-3, 8], [3, 8], [2, 4], [-2, 4]],
    z0: 4, z1: 7, supportZ: 2, type: 'SITZ',
  };
  const roof = [{id: 'roof', quad: [[-3, 9], [3, 9], [2, 5], [-2, 5]], heights: [9, 9, 7, 7]}];
  const result = applyEditorDesign(
    scene, [current], [new Uint8Array(4)], [['#222']],
    {meta: {fieldC: [0, 0], axisTheta: 0}}, 4, roof,
  );
  assert.deepEqual(result.outline, [[-3, 8], [3, 8]]);
  assert.deepEqual(result.facadeSegments, [[[-3, 8], [3, 8]]]);
  assert.deepEqual(result.roof.segments[0].quad, roof[0].quad);
});

test('tier underside and side walls terminate at support height', () => {
  const surfaces = blockSupportQuads({
    quad: [[-3, 8], [3, 8], [2, 4], [-2, 4]],
    z0: 7, z1: 12, wallBaseZ: 4,
  });
  assert.equal(surfaces.wallBase, 4);
  assert.deepEqual(surfaces.underside.map(point => point[2]), [7, 7, 4, 4]);
  for (const wall of surfaces.sideWalls) {
    assert.deepEqual(wall.map(point => point[2]), [7, 12, 4, 4]);
  }
});

test('facade edges use nearby stand heights instead of the stadium maximum', () => {
  const blocks = [
    {...makeBlock(1, 'NORD', [0, 80], 40), z1: 30, wallBaseZ: 8},
    {...makeBlock(2, 'SUED', [0, -80], 40), z1: 30, wallBaseZ: 8},
    {...makeBlock(3, 'WEST', [-80, 0], 40), z1: 12},
    {...makeBlock(4, 'OST', [80, 0], 40), z1: 12},
  ];
  const north = facadeEdgeTopHeights([[-20, 80], [20, 80]], blocks);
  const west = facadeEdgeTopHeights([[-80, 20], [-80, -20]], blocks);
  assert.deepEqual(north.map(Math.round), [33, 33]);
  assert.deepEqual(west.map(Math.round), [15, 15]);
  assert.ok(west.every(height => height < 20), 'WEST must not inherit NORD/SUED height');
});

test('facade reaches the local roof edge when a roof is present', () => {
  const block = {...makeBlock(1, 'WEST', [-80, 0], 40), z1: 12};
  const roof = [{
    quad: [[-84, 20], [-84, -20], [-70, -20], [-70, 20]],
    heights: [19, 21, 16, 16],
  }];
  const heights = facadeEdgeTopHeights(
    [[-84, 20], [-84, -20]], [block], 2.5, roof,
  );
  assert.deepEqual(heights, [19, 21]);
});

test('adjacent roof seams share their moved position and height', () => {
  const baseline = [
    {quad: [[0, 10], [10, 10], [8, 5], [0, 5]], heights: [10, 10, 8, 8]},
    {quad: [[10, 10], [20, 10], [20, 5], [8, 5]], heights: [10, 10, 8, 8]},
  ];
  const moved = structuredClone(baseline);
  moved[0].quad[1] = [12, 12];
  moved[0].heights[1] = 14;
  moved[1].quad[0] = [10, 10];
  moved[1].heights[0] = 10;
  const stitched = geometryApi.stitchRoofSegments(moved, baseline);
  assert.deepEqual(stitched[0].quad[1], [11, 11]);
  assert.deepEqual(stitched[1].quad[0], [11, 11]);
  assert.equal(stitched[0].heights[1], 12);
  assert.equal(stitched[1].heights[0], 12);
});

test('absolute expansion size maps 10k and 20k to distinct visible rows', () => {
  assert.equal(geometryApi.expansionVisualRows(10_000), 10);
  assert.equal(geometryApi.expansionVisualRows(20_000), 20);
  assert.equal(geometryApi.expansionVisualRows(68_001), 69);
});

test('expands every exterior section of the selected stand as one batch', () => {
  const {blocks, geometry} = fixture();
  const northCenter = blocks.find(block => block.stand === 'NORD');
  const northUpper = {
    ...structuredClone(northCenter),
    id: 20,
    sourceId: 20,
    lineageId: 20,
    tier: 'OBER',
    order: 20,
    rows: 18,
    z0: 12,
    z1: 26,
    quad: northCenter.quad.map(point => [
      point[0] * 1.22,
      point[1] * 1.22,
    ]),
  };
  const northWest = makeBlock(21, 'NORD', [-48, 64], 28);
  blocks.push(northUpper, northWest);

  const selected = geometryApi.expansionEnvelope(
    'NORD', blocks, blocks, geometry,
  );
  const selectedIds = new Set(selected.map(block => block.id));
  assert.ok(selectedIds.has(20), 'the upper north section must be selected');
  assert.ok(selectedIds.has(21), 'the north-west transition must be selected');
  assert.ok(selectedIds.size >= 2, 'NORD must contain multiple exterior sections');
  assert.ok(
    selected.every(block => block.stand === 'NORD'),
    'no other stand may enter the NORD batch',
  );

  const before = new Map(blocks.map(block => [block.id, block.rows]));
  const step = geometryApi.expansionStep(selected, 'SITZ', 10);
  assert.equal(step.kind, 'grow');
  assert.equal(step.rows, 10);
  for (const block of step.blocks) block.rows += step.rows;

  for (const block of blocks) {
    assert.equal(
      block.rows,
      before.get(block.id) + (selectedIds.has(block.id) ? 10 : 0),
      `${block.stand} block ${block.id} changed unexpectedly`,
    );
  }
});

test('starts one complete new tier when a selected section cannot grow', () => {
  const {blocks, geometry} = fixture(Math.PI / 5, true);
  const selected = geometryApi.expansionEnvelope(
    'NORD', blocks, blocks, geometry,
  );
  selected[0].rows = 42;
  const step = geometryApi.expansionStep(selected, 'SITZ', 20);
  assert.equal(step.kind, 'tier');
  assert.equal(step.rows, 20);
  assert.deepEqual(step.blocks, selected);
});

test('preview expansion blocks are restored by undo snapshots and omitted from export', () => {
  const persistent = {id: 1, sourceId: 1, rows: 2, seats: 2};
  const preview = {id: 2, previewId: 'preview-1', simulated: true, rows: 3, seats: 2};
  const beforeExpansion = geometryApi.snapshotBlocks([persistent]);
  const afterExpansion = geometryApi.snapshotBlocks([persistent, preview]);
  afterExpansion[0].rows = 99;
  assert.equal(beforeExpansion[0].rows, 2);
  assert.deepEqual(
    geometryApi.persistentBlockEntries([persistent, preview]),
    [{block: persistent, index: 0}],
  );
  assert.deepEqual(
    geometryApi.persistentBlockEntries(beforeExpansion).map(entry => entry.block),
    [persistent],
  );
});