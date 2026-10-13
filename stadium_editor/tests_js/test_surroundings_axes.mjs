import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {editorPointToDortmund, buildDortmundSurroundings,
  resolveSurroundingsAxes} from '../static/stadium_editor/dortmund_surroundings.js';
import {validateCalibration, standForCenter} from '../static/stadium_editor/unity_calibration.js';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';

const frankfurt = JSON.parse(readFileSync(
  new URL('../blueprints/v2/models/912.json', import.meta.url))).calibration;
const leipzig = JSON.parse(readFileSync(
  new URL('../blueprints/v2/models/91013388.json', import.meta.url))).calibration;
const oldMap = (point, frame) => {
  const [cx, cy] = frame.fieldC || [0, 0], theta = frame.axisTheta ?? 0;
  const dx = point[0] - cx, dy = point[1] - cy;
  const u = dx * Math.cos(theta) + dy * Math.sin(theta);
  const v = -dx * Math.sin(theta) + dy * Math.cos(theta);
  return [-v, u];
};

test('existing models preserve their map coordinates including signed zero', () => {
  for (const frame of [{}, {fieldC:[3, 7], axisTheta:2.4871}])
    for (const point of [[0,0], [52.5,0], [0,34], [182,-40]])
      assert.deepEqual(editorPointToDortmund(point, frame), oldMap(point, frame));
  assert.deepEqual(editorPointToDortmund([52.5,0]), [-0,52.5]);
});

for (const [name, calibration] of [['Frankfurt', frankfurt], ['Leipzig', leipzig]]) {
test(`${name} places the north end at -z and the west side at -x`, () => {
  assert.equal(validateCalibration(calibration), calibration);
  const axes = calibration.surroundingsAxes;
  assert.deepEqual(axes, {NORD:'-z', WEST:'-x'});
  for (const [editor, expected] of [
    [[100,0], [0,-100]], [[-100,0],[0,100]],
    [[0,80],[-80,0]], [[0,-80],[80,0]]]) {
    const mapped = editorPointToDortmund(editor, {}, axes);
    for (let index=0; index<2; index++)
      assert.ok(Math.abs(mapped[index]-expected[index]) < 1e-9);
    assert.equal(standForCenter({x:expected[0], z:expected[1]}, calibration.standAxes),
      editor[0] > 0 ? 'NORD' : editor[0] < 0 ? 'SUED' :
        editor[1] > 0 ? 'WEST' : 'OST');
  }
});
}

test('build uses the declared axes without changing source map data', () => {
  const data = {buildings:[[[0,0],[10,0],[10,20],[0,20]]], buildingHeights:[12]};
  const snapshot = JSON.stringify(data);
  const normal = buildDortmundSurroundings(THREE, data);
  const mirrored = buildDortmundSurroundings(THREE, data, {}, frankfurt.surroundingsAxes);
  try {
    const box = scene => {
      const geometry = scene.group.getObjectByName('ENV_BUILDINGS').geometry;
      geometry.computeBoundingBox();
      return geometry.boundingBox;
    };
    assert.equal(box(normal).min.x, box(mirrored).min.x);
    assert.equal(box(normal).max.x, box(mirrored).max.x);
    assert.equal(box(normal).min.z, -box(mirrored).max.z);
    assert.equal(box(normal).max.z, -box(mirrored).min.z);
    assert.equal(JSON.stringify(data), snapshot);
  } finally { normal.dispose(); mirrored.dispose(); }
});

test('invalid axes fail closed even for an empty map', () => {
  for (const axes of [null, [], {NORD:'-z'}, {NORD:'-z',WEST:'+z'},
    {NORD:'-z',WEST:'constructor'}]) {
    assert.throws(() => resolveSurroundingsAxes(axes), /Ortsplan-Achsen/);
    assert.throws(() => buildDortmundSurroundings(THREE, {}, {}, axes), /Ortsplan-Achsen/);
  }
});
