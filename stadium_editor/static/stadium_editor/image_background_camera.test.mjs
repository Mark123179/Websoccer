import assert from 'node:assert/strict';
import test from 'node:test';
import * as THREE from './stage/vendor/three.module.js';
import {imageCameraFrame, applyImageCameraFrame} from './image_background_camera.js';

const config = {
  referenceSize: [1024, 512],
  pitchCorners: [[421, 245], [604, 245], [621, 358], [403, 358]],
  pitchHalfSize: [34.080013275146484, 52.95001220703125], pitchY: .008346,
};
test('all four actual 3D field corners project onto supplied photo lines', () => {
  const frame = imageCameraFrame(config);
  for (const width of [1024, 996, 360, 280]) {
    const height = width / 2;
    const camera = new THREE.PerspectiveCamera();
    applyImageCameraFrame(camera, frame, width, height);
    camera.position.set(-frame.distance * Math.cos(frame.elevation),
      config.pitchY + frame.distance * Math.sin(frame.elevation), 0);
    camera.lookAt(0, config.pitchY, 0);
    camera.updateMatrixWorld(true);
    const [depth, length] = config.pitchHalfSize;
    [[depth, -length], [depth, length], [-depth, length], [-depth, -length]]
      .forEach(([x, z], index) => {
        const p = new THREE.Vector3(x, config.pitchY, z).project(camera);
        const px = (p.x + 1) * width / 2;
        const py = (1 - p.y) * height / 2;
        const expected = config.pitchCorners[index].map(v => v * width / 1024);
        assert.ok(Math.hypot(px - expected[0], py - expected[1]) <= .26 * width / 1024);
      });
  }
});
test('registration is independent of expanded stadium bounds', () => {
  assert.deepEqual(imageCameraFrame(config), imageCameraFrame({...config,
    standsBounds: [-300, -300, 300, 300], capacity: 120000}));
});
test('invalid or incompatible perspective is rejected rather than warped', () => {
  for (const change of [
    {pitchCorners: [[0, 0], [200, 0], [200, 100], [0, 100]]},
    {pitchCorners: [[421, 235], [604, 245], [621, 358], [403, 358]]},
    {referenceSize: [0, 512]}, {pitchY: NaN}, {pitchHalfSize: [true, 52]},
  ]) assert.throws(() => imageCameraFrame({...config, ...change}));
});
