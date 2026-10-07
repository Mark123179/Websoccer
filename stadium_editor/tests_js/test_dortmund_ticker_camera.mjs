import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  tickerCameraFrame, TICKER_ELEVATION, TICKER_AZIMUTH,
} from '../static/stadium_editor/dortmund_ticker_camera.js';

test('ticker camera is modestly lower and keeps the horizontal pitch axis', () => {
  assert.ok(TICKER_ELEVATION < .96 && TICKER_ELEVATION > .8);
  assert.equal(TICKER_AZIMUTH, -Math.PI / 2);
});

for (const aspect of [16 / 8.4, 1.32, .8]) {
  test(`entire measured pitch stays visible with a small bottom margin at aspect ${aspect}`, () => {
    const f = tickerCameraFrame(aspect);
    const projectY = x => Math.sin(TICKER_ELEVATION) * x
      - Math.cos(TICKER_ELEVATION) * f.targetY;
    assert.ok(f.right - f.left >= 246 - 1e-9);
    assert.ok(projectY(-37.900013) >= f.bottom);
    assert.ok(projectY(37.900013) <= f.top);
    assert.ok(Math.abs(projectY(-37.900013) - f.bottom - 2.5) < 1e-9);
    for (const x of [-34.08, 34.08]) {
      for (const z of [-52.95, 52.95]) {
        assert.ok(z > f.left && z < f.right);
        assert.ok(projectY(x) > f.bottom && projectY(x) < f.top);
      }
    }
  });
}

test('landscape view is tighter than the previous camera', () => {
  const f = tickerCameraFrame(16 / 8.4);
  assert.equal(f.top - f.bottom, 132);
  assert.ok(f.right - f.left < 174 * 16 / 8.4);
});

test('invalid dimensions fail explicitly; other viewers retain their defaults', () => {
  for (const aspect of [0, -1, NaN, Infinity]) {
    assert.throws(() => tickerCameraFrame(aspect), RangeError);
  }
  const source = readFileSync(new URL(
    '../static/stadium_editor/dortmund_editor_scene.js', import.meta.url), 'utf8');
  assert.match(source, /tickerPreview = false/);
  assert.match(source, /tickerPreview \? TICKER_ELEVATION : \.56/);
  assert.match(source, /tickerPreview \? TICKER_AZIMUTH : \.88/);
  assert.match(source, /if \(tickerPreview\) \{[\s\S]*?tickerCameraFrame\(camera\.aspect\)/);
});
