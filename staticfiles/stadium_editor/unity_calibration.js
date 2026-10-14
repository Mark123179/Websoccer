import * as THREE from './stage/vendor/three.module.js';

/** No defaults: a source model must supply its complete calibration. */
export function validateCalibration(calibration) {
  const fail = field => { throw new Error(`Kalibrierung fehlt: ${field}`); };
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string' && value.trim().length > 0;
  const vector = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);
  if (!object(calibration)) fail('calibration');
  if (calibration.roofMeshPrefixes !== undefined &&
      (!Array.isArray(calibration.roofMeshPrefixes) || !calibration.roofMeshPrefixes.every(text)))
    fail('roofMeshPrefixes');
  for (const field of ['roofMinHeight', 'tickerRotationY'])
    if (!Number.isFinite(calibration[field])) fail(field);
  if (!Array.isArray(calibration.skipMeshPrefixes) || !calibration.skipMeshPrefixes.every(text))
    fail('skipMeshPrefixes');
  for (const field of ['crowdPrefix', 'pitchPrefix'])
    if (!text(calibration[field])) fail(field);
  if (!object(calibration.tickerFrontCut)) fail('tickerFrontCut');
  if (!vector(calibration.tickerFrontCut.normal) || !calibration.tickerFrontCut.normal.some(v => v !== 0))
    fail('tickerFrontCut.normal');
  if (!Number.isFinite(calibration.tickerFrontCut.constant)) fail('tickerFrontCut.constant');
  if (!object(calibration.standAxes)) fail('standAxes');
  const stands = new Set(['NORD', 'SUED', 'OST', 'WEST']);
  for (const axis of ['+x', '-x', '+z', '-z'])
    if (!stands.has(calibration.standAxes[axis])) fail(`standAxes.${axis}`);
  if (Object.keys(calibration.standAxes).length !== 4 ||
      new Set(Object.values(calibration.standAxes)).size !== 4) fail('standAxes');
  if (calibration.surroundingsAxes !== undefined) {
    const axes = calibration.surroundingsAxes;
    if (!object(axes) || Object.keys(axes).length !== 2 ||
        !Object.hasOwn(axes, 'NORD') || !Object.hasOwn(axes, 'WEST'))
      fail('surroundingsAxes');
    for (const stand of ['NORD', 'WEST']) {
      if (!['+x', '-x', '+z', '-z'].includes(axes[stand]))
        fail(`surroundingsAxes.${stand}`);
      if (calibration.standAxes[axes[stand]] !== stand)
        throw new Error(`Kalibrierung widerspricht standAxes: surroundingsAxes.${stand}`);
    }
    if (axes.NORD[1] === axes.WEST[1]) fail('surroundingsAxes');
  }
  if (!object(calibration.orbitDefault)) fail('orbitDefault');
  for (const field of ['azimuth', 'elevation', 'distance'])
    if (!Number.isFinite(calibration.orbitDefault[field])) fail(`orbitDefault.${field}`);
  if (calibration.orbitDefault.distance <= 0) fail('orbitDefault.distance');
  return calibration;
}

export function standForCenter(center, standAxes) {
  const axis = Math.abs(center.x) > Math.abs(center.z)
    ? (center.x > 0 ? '+x' : '-x') : (center.z > 0 ? '+z' : '-z');
  return standAxes[axis];
}

export function tickerQuaternion(rotationDegrees) {
  return new THREE.Quaternion().setFromAxisAngle(
    new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(rotationDegrees));
}
