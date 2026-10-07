import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {
  tickerCameraFrame, tickerHeightElevation, TICKER_ELEVATION, TICKER_AZIMUTH,
} from '../static/stadium_editor/dortmund_ticker_camera.js';

function cameraFor(aspect, degrees = 50) {
  const e = tickerHeightElevation(degrees), f = tickerCameraFrame(aspect, e);
  const camera = new THREE.PerspectiveCamera(f.fov, aspect, 1, 2400);
  camera.position.set(-f.distance * Math.cos(e), f.distance * Math.sin(e), 0);
  camera.lookAt(0, 0, 0);
  camera.setViewOffset(1000 * aspect, 1000, 0, 1000 * f.offsetY, 1000 * aspect, 1000);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  return camera;
}
const project = (camera, x, z) => new THREE.Vector3(x, .01, z).project(camera);

test('reference starting angle retains the horizontal pitch axis', () => {
  assert.equal(TICKER_ELEVATION, 50 * Math.PI / 180);
  assert.equal(TICKER_AZIMUTH, -Math.PI / 2);
  assert.ok(cameraFor(16 / 8.4).isPerspectiveCamera);
});

test('near touchline is genuinely wider than the far one', () => {
  const c = cameraFor(16 / 8.4);
  const width = x => Math.abs(project(c, x, 52.95).x - project(c, x, -52.95).x);
  assert.ok(width(-34.08) > width(34.08) * 1.1);
});

test('entire measured pitch fits at every slider height and screen aspect', () => {
  for (let degrees = 35; degrees <= 75; degrees++) {
    for (const aspect of [16 / 8.4, 1.32, .8, 2.4]) {
      const camera = cameraFor(aspect, degrees);
      for (const x of [-37.900013, 37.900013]) {
        for (const z of [-57.2, 57.2]) {
          const p = project(camera, x, z);
          assert.ok(Math.abs(p.x) < 1, `side cropped: ${degrees} / ${aspect}`);
          assert.ok(Math.abs(p.y) < 1, `end cropped: ${degrees} / ${aspect}`);
          assert.ok(p.z > -1 && p.z < 1);
        }
      }
    }
  }
});

test('aim, distance and composition offset stay fixed as height changes', () => {
  const low = tickerCameraFrame(16 / 8.4, tickerHeightElevation(35));
  const high = tickerCameraFrame(16 / 8.4, tickerHeightElevation(75));
  assert.deepEqual(low, high);
  const near = project(cameraFor(16 / 8.4), -37.900013, 0);
  assert.ok(near.y < -.75 && near.y > -1);
});

test('raising the camera reveals more of the far pitch in the image', () => {
  assert.ok(project(cameraFor(16 / 8.4, 75), 34.08, 0).y
    > project(cameraFor(16 / 8.4, 35), 34.08, 0).y);
});

test('invalid input fails explicitly and slider extremes are clamped', () => {
  for (const aspect of [0, -1, NaN, Infinity]) {
    assert.throws(() => tickerCameraFrame(aspect), RangeError);
  }
  for (const e of [NaN, Infinity, 0, 2]) {
    assert.throws(() => tickerCameraFrame(1.9, e), RangeError);
  }
  for (const degrees of [NaN, Infinity, '50', undefined]) {
    assert.throws(() => tickerHeightElevation(degrees), RangeError);
  }
  assert.equal(tickerHeightElevation(0), tickerHeightElevation(35));
  assert.equal(tickerHeightElevation(100), tickerHeightElevation(75));
});

test('non-ticker viewers retain their camera and framing defaults', () => {
  const source = readFileSync(new URL(
    '../static/stadium_editor/dortmund_editor_scene.js', import.meta.url), 'utf8');
  assert.match(source, /tickerPreview = false/);
  assert.match(source, /PerspectiveCamera\(tickerPreview \? 27 : 42/);
  assert.match(source, /tickerPreview \? TICKER_ELEVATION : \.56/);
  assert.match(source, /tickerPreview \? TICKER_AZIMUTH : \.88/);
  assert.match(source, /tickerPreview \? TICKER_VIEW_OFFSET : verticalFraming/);
});
