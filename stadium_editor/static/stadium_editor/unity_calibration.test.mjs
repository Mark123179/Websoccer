import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import * as THREE from './stage/vendor/three.module.js';
import {applyStudyCamera} from './study_camera.js';
import {validateCalibration, standForCenter, tickerQuaternion} from './unity_calibration.js';
import {mountUnityStadium} from './unity_stadium_scene.js';

const manifest = JSON.parse(fs.readFileSync(new URL('../../blueprints/v2/models/908.json', import.meta.url)));
const calibration = manifest.calibration;

test('complete manifest calibration has no implicit defaults', () => {
  assert.equal(validateCalibration(calibration), calibration);
  assert.throws(() => validateCalibration(), /Kalibrierung fehlt: calibration/);
  for (const field of Object.keys(calibration)) {
    const c = structuredClone(calibration);
    delete c[field];
    assert.throws(() => validateCalibration(c), new RegExp(`Kalibrierung fehlt: ${field}`));
  }
  for (const [parent, field] of [['tickerFrontCut', 'normal'], ['tickerFrontCut', 'constant'],
    ['orbitDefault', 'azimuth'], ['orbitDefault', 'elevation'], ['orbitDefault', 'distance'],
    ['standAxes', '+x'], ['standAxes', '-x'], ['standAxes', '+z'], ['standAxes', '-z']]) {
    const c = structuredClone(calibration);
    delete c[parent][field];
    assert.throws(() => validateCalibration(c), error => error.message === `Kalibrierung fehlt: ${parent}.${field}`);
  }
});

test('dominant signed native axis maps through manifest standAxes, including ties', () => {
  for (const [x, z, expected] of [[10, 1, 'SUED'], [-10, 1, 'NORD'],
    [1, 10, 'OST'], [1, -10, 'WEST'], [0, 0, 'WEST'], [10, 10, 'OST']])
    assert.equal(standForCenter({x, z}, calibration.standAxes), expected);
  const changed = {'+x':'WEST', '-x':'OST', '+z':'NORD', '-z':'SUED'};
  assert.equal(standForCenter({x:10, z:1}, changed), 'WEST');
});

test('manifest -90 degree rotation produces exactly the previous camera matrices', () => {
  for (const [width, height] of [[1000, 500], [390, 850], [1440, 900]]) {
    const before = new THREE.PerspectiveCamera(42, 1, 1, 2400);
    const after = before.clone();
    for (const [camera, q] of [[before, new THREE.Quaternion().setFromAxisAngle(
      new THREE.Vector3(0,1,0), -Math.PI/2)], [after, tickerQuaternion(calibration.tickerRotationY)]]) {
      applyStudyCamera(camera, 'approved-elversberg', width, height);
      camera.position.applyQuaternion(q);
      camera.quaternion.premultiply(q);
      camera.updateMatrixWorld(true);
    }
    assert.deepEqual(after.matrixWorld.elements, before.matrixWorld.elements);
    assert.deepEqual(after.matrixWorldInverse.elements, before.matrixWorldInverse.elements);
    assert.deepEqual(after.projectionMatrix.elements, before.projectionMatrix.elements);
  }
});

test('mount rejects missing calibration before loading binary or creating a renderer', async () => {
  const missing = structuredClone(manifest);
  delete missing.calibration.roofMinHeight;
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; return {ok:true, json:async () => missing}; };
  try {
    await assert.rejects(mountUnityStadium({presentation:{
      renderer:'unity-spatial', clubFmiId:908, sourceSha256:manifest.sourceSha256, modelUrl:'/test',
    }}), /Kalibrierung fehlt: roofMinHeight/);
    assert.equal(calls, 1);
  } finally { globalThis.fetch = original; }
});

test('identity is manifest-bound, not restricted to Gladbach', async () => {
  const original = globalThis.fetch;
  const other = {...manifest, clubFmiId:12345, calibration:undefined};
  globalThis.fetch = async () => ({ok:true, json:async () => other});
  try {
    await assert.rejects(mountUnityStadium({presentation:{
      renderer:'unity-spatial', clubFmiId:12345, sourceSha256:manifest.sourceSha256,
    }}), /Kalibrierung fehlt: calibration/);
    await assert.rejects(mountUnityStadium({presentation:{
      renderer:'unity-spatial', clubFmiId:908, sourceSha256:manifest.sourceSha256,
    }}), /Modellquelle gehört nicht/);
    await assert.rejects(mountUnityStadium({presentation:{
      renderer:'unity-spatial', clubFmiId:12345, sourceSha256:'wrong',
    }}), /Modellquelle gehört nicht/);
  } finally { globalThis.fetch = original; }
});
