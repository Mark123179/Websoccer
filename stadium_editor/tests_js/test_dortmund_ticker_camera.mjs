import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  tickerCameraFrame, tickerHeightElevation, TICKER_ELEVATION, TICKER_AZIMUTH,
} from '../static/stadium_editor/dortmund_ticker_camera.js';

test('ticker camera starts higher to reveal more field, retaining the horizontal axis', () => {
  assert.equal(TICKER_ELEVATION, Math.PI / 3);
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
  assert.match(source, /if \(tickerPreview\) \{[\s\S]*?tickerCameraFrame\(camera\.aspect, elevation\)/);
});

test('height slider clamps extremes and rejects invalid values', () => {
  assert.equal(tickerHeightElevation(0), tickerHeightElevation(35));
  assert.equal(tickerHeightElevation(100), tickerHeightElevation(75));
  for (const value of [NaN, Infinity, '60', undefined]) {
    assert.throws(() => tickerHeightElevation(value), RangeError);
  }
});

test('entire pitch fits at every height and aspect, anchored at the lower edge', () => {
  for (let degrees = 35; degrees <= 75; degrees++) {
    const e = tickerHeightElevation(degrees);
    for (const aspect of [16 / 8.4, 1.32, .8]) {
      const f = tickerCameraFrame(aspect, e);
      const y = x => Math.sin(e) * x - Math.cos(e) * f.targetY;
      assert.ok(y(-37.900013) >= f.bottom - 1e-9);
      assert.ok(y(37.900013) <= f.top);
      assert.ok(Math.abs(y(-37.900013) - f.bottom - 2.5) < 1e-9);
    }
  }
});

test('raising the camera reveals more field towards the back', () => {
  const top = degrees => {
    const e = tickerHeightElevation(degrees), f = tickerCameraFrame(16 / 8.4, e);
    return Math.sin(e) * 37.900013 - Math.cos(e) * f.targetY;
  };
  assert.ok(top(60) > top(49));
  assert.ok(top(75) > top(60));
});
