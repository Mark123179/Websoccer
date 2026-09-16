import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile, stat} from 'node:fs/promises';
import {extname, join, normalize} from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {chromium} from 'playwright-core';

const root = fileURLToPath(new URL('../..', import.meta.url));
const chromiumPath = process.env.CHROMIUM_PATH || '/repl/tools/bin/chromium';
const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
};

function serveWorkspace() {
  const server = createServer(async (request, response) => {
    try {
      const relative = normalize(decodeURIComponent(new URL(
        request.url, 'http://127.0.0.1',
      ).pathname)).replace(/^[/\\]+/, '');
      const path = join(root, relative);
      assert.ok(path.startsWith(root), 'request must stay inside the workspace');
      assert.ok((await stat(path)).isFile(), 'request must resolve to a file');
      response.writeHead(200, {
        'content-type': contentTypes[extname(path)] || 'application/octet-stream',
      });
      response.end(await readFile(path));
    } catch (_error) {
      response.writeHead(404);
      response.end('Not found');
    }
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

async function snapshot(page) {
  return page.evaluate(() => {
    const camera = window.seatViewTest.api.stage.camera;
    const direction = camera.getWorldDirection(
      new camera.position.constructor(),
    );
    const inward = new camera.position.constructor(
      -camera.position.x, 0, -camera.position.z,
    ).normalize();
    const flat = direction.clone().setY(0).normalize();
    const crossY = inward.clone().cross(flat).y;
    return {
      position: camera.position.toArray(),
      direction: direction.toArray(),
      yaw: Math.atan2(crossY, inward.dot(flat)) * 180 / Math.PI,
      pitch: Math.asin(direction.y) * 180 / Math.PI,
    };
  });
}

function distance(left, right) {
  return Math.hypot(...left.map((value, index) => value - right[index]));
}

async function backgroundSample(page) {
  return page.evaluate(() => {
    const renderer = window.seatViewTest.api.stage.renderer;
    const gl = renderer.getContext();
    const width = gl.drawingBufferWidth;
    const height = gl.drawingBufferHeight;
    const samples = [];
    for (const xRatio of [.05, .25, .5, .75, .95]) {
      const rgba = new Uint8Array(4);
      gl.readPixels(
        Math.floor(width * xRatio), Math.floor(height * .92),
        1, 1, gl.RGBA, gl.UNSIGNED_BYTE, rgba,
      );
      samples.push(Array.from(rgba));
    }
    return samples;
  });
}

async function drag(page, dx, dy) {
  const canvas = page.locator('#editor-stage canvas');
  const box = await canvas.boundingBox();
  assert.ok(box, 'WebGL canvas must be visible');
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx, y + dy, {steps: 8});
  await page.mouse.up();
}

test('seat view pointer controls survive renderer rebuilds', async t => {
  const server = await serveWorkspace();
  t.after(() => new Promise(resolve => server.close(resolve)));
  const browser = await chromium.launch({
    executablePath: chromiumPath,
    headless: true,
    args: ['--no-sandbox', '--use-gl=swiftshader'],
  });
  t.after(() => browser.close());
  const page = await browser.newPage({viewport: {width: 1100, height: 700}});
  const port = server.address().port;
  await page.goto(
    `http://127.0.0.1:${port}/stadium_editor/tests_js/seat_view_harness.html`,
  );
  await page.waitForFunction(() => window.seatViewTest?.ready);
  assert.equal(
    await page.evaluate(() => window.seatViewTest.api.kind),
    'three',
    'the editor must render the WebGL seat view',
  );
  const seatStats = await page.evaluate(() => window.seatViewTest.api.stage.stats);
  assert.ok(seatStats.seats > 2_000, 'the WebGL stage must create individual seat instances');
  assert.equal(seatStats.seats, 2_604);
  assert.equal(seatStats.pitchStripes, 10);
  assert.equal(seatStats.pitchLines, 17);
  assert.equal(seatStats.sky, 'day');
  await page.waitForFunction(
    () => window.seatViewTest.api.stage.backgroundReady(),
  );
  const daySky = await backgroundSample(page);
  assert.ok(daySky.every(pixel => pixel[3] === 255), 'day sky must fill the view');
  assert.ok(daySky.some(pixel => pixel[2] > 80), 'day sky must contain blue pixels');

  const initial = await snapshot(page);
  assert.ok(
    Math.hypot(initial.position[0], initial.position[2]) > 50,
    'seat camera must be fixed on the WEST/OST stand',
  );

  await drag(page, 180, 0);
  const horizontal = await snapshot(page);
  assert.ok(
    distance(initial.direction, horizontal.direction) > 0.2,
    'horizontal drag must visibly change the camera direction',
  );
  assert.ok(distance(initial.position, horizontal.position) < 1e-6);

  await drag(page, 0, 160);
  const vertical = await snapshot(page);
  assert.ok(
    distance(horizontal.direction, vertical.direction) > 0.15,
    'vertical drag must visibly change the camera direction',
  );
  assert.ok(distance(initial.position, vertical.position) < 1e-6);

  await drag(page, 2000, 2000);
  const clamped = await snapshot(page);
  assert.ok(Math.abs(Math.abs(clamped.yaw) - 80) < 0.2, 'yaw clamps at 80°');
  assert.ok(Math.abs(Math.abs(clamped.pitch) - 20) < 0.2, 'pitch clamps at 20°');
  assert.ok(distance(initial.position, clamped.position) < 1e-6);

  await page.locator('#editor-stage canvas').dblclick();
  const reset = await snapshot(page);
  assert.ok(Math.abs(reset.yaw) < 0.1, 'double-click resets yaw toward the pitch');
  assert.ok(Math.abs(reset.pitch) < 0.1, 'double-click resets pitch');
  assert.ok(distance(initial.position, reset.position) < 1e-6);

  await page.evaluate(async () => {
    await window.seatViewTest.api.update({day: false});
  });
  await page.waitForFunction(
    () => window.seatViewTest.api.stage.backgroundReady(),
  );
  const nightStats = await page.evaluate(
    () => window.seatViewTest.api.stage.stats,
  );
  assert.equal(nightStats.sky, 'night');
  const nightPosition = await snapshot(page);
  assert.ok(distance(initial.position, nightPosition.position) < 1e-6);
  const nightSky = await backgroundSample(page);
  assert.ok(nightSky.every(pixel => pixel[3] === 255), 'night sky must fill the view');
  assert.notDeepEqual(nightSky, daySky, 'day/night must swap the sky texture');

  for (const degrees of [0, 90, 180, 270]) {
    await page.evaluate(async ({degrees}) => {
      const testState = window.seatViewTest;
      const radians = degrees * Math.PI / 180;
      const c = Math.cos(radians), s = Math.sin(radians);
      const point = ([x, y]) => [x * c - y * s, x * s + y * c];
      const scene = structuredClone(testState.scene);
      scene.blocks.forEach(block => { block.quad = block.quad.map(point); });
      scene.outline = scene.outline.map(point);
      await testState.api.update({scene, day: true});
    }, {degrees});
    const pitchCenter = await page.evaluate(
      () => window.seatViewTest.api.project(0, 0, 0.03),
    );
    assert.ok(pitchCenter.visible, `${degrees}° pitch center must face the seat`);
    const stats = await page.evaluate(() => window.seatViewTest.api.stage.stats);
    assert.equal(stats.pitchStripes, 10);
    assert.equal(stats.pitchLines, 17);
  }

  await page.locator('#editor-stage canvas').evaluate(
    canvas => { canvas.dataset.beforeRebuild = 'yes'; },
  );
  await page.evaluate(async () => {
    const testState = window.seatViewTest;
    await testState.api.update({scene: structuredClone(testState.scene)});
  });
  assert.equal(
    await page.locator('#editor-stage canvas').getAttribute('data-before-rebuild'),
    null,
    'renderer rebuild must replace the WebGL canvas',
  );
  await drag(page, -140, -90);
  const rebuilt = await snapshot(page);
  assert.ok(
    distance(reset.direction, rebuilt.direction) > 0.2,
    'pointer controls must remain bound after the canvas is replaced',
  );
  assert.ok(distance(initial.position, rebuilt.position) < 1e-6);
});