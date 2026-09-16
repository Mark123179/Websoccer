import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {mkdir, readFile, stat} from 'node:fs/promises';
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

async function fieldBrightness(page) {
  const pixels = await page.evaluate(() => {
    const gl = window.seatViewTest.api.stage.renderer.getContext();
    const width = gl.drawingBufferWidth;
    const height = gl.drawingBufferHeight;
    const result = [];
    for (const yRatio of [.18, .28, .38]) {
      for (const xRatio of [.2, .4, .6, .8]) {
        const rgba = new Uint8Array(4);
        gl.readPixels(
          Math.floor(width * xRatio), Math.floor(height * yRatio),
          1, 1, gl.RGBA, gl.UNSIGNED_BYTE, rgba,
        );
        result.push(...rgba.slice(0, 3));
      }
    }
    return result;
  });
  return pixels.reduce((sum, value) => sum + value, 0) / pixels.length;
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

const visualCases = [
  {
    name: 'seat-day-mast-light',
    query: 'scene=campnou&camera=seat&lighting=day&floodlight=on' +
      '&floodlightType=mast&seatColor=light',
    expected: {
      camera: 'seat', lighting: 'day', floodlightType: 'mast',
      floodlightFixtures: 4, seatColor: '#edf2f7',
    },
  },
  {
    name: 'seat-night-rim-dark',
    query: 'scene=campnou&camera=seat&lighting=night&floodlight=on' +
      '&floodlightType=rim&seatColor=dark',
    expected: {
      camera: 'seat', lighting: 'night', floodlightType: 'rim',
      floodlightFixtures: 102, seatColor: '#111820',
    },
  },
  {
    name: 'orbit-day-rim-light',
    query: 'scene=campnou&camera=orbit&lighting=day&floodlight=on' +
      '&floodlightType=rim&seatColor=light',
    expected: {
      camera: 'orbit', lighting: 'day', floodlightType: 'rim',
      floodlightFixtures: 102, seatColor: '#edf2f7',
    },
  },
  {
    name: 'orbit-night-mast-dark',
    query: 'scene=campnou&camera=orbit&lighting=night&floodlight=on' +
      '&floodlightType=mast&seatColor=dark',
    expected: {
      camera: 'orbit', lighting: 'night', floodlightType: 'mast',
      floodlightFixtures: 4, seatColor: '#111820',
    },
  },
];

async function compareVisual(page, baselineUrl) {
  return page.evaluate(async url => {
    const current = window.seatViewTest.api.stage.renderer.domElement;
    const baseline = new Image();
    baseline.src = url;
    await baseline.decode();
    const width = current.width;
    const height = current.height;
    if (baseline.naturalWidth !== width || baseline.naturalHeight !== height) {
      return {
        dimensionError: `${baseline.naturalWidth}x${baseline.naturalHeight}` +
          ` statt ${width}x${height}`,
      };
    }
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d', {willReadFrequently: true});
    context.drawImage(current, 0, 0);
    const actual = context.getImageData(0, 0, width, height);
    context.clearRect(0, 0, width, height);
    context.drawImage(baseline, 0, 0);
    const expected = context.getImageData(0, 0, width, height);
    const diff = context.createImageData(width, height);
    let changed = 0;
    let darkClippedActual = 0;
    let darkClippedExpected = 0;
    let brightClippedActual = 0;
    let brightClippedExpected = 0;
    const sums = [0, 0, 0];
    const expectedSums = [0, 0, 0];
    let luma = 0;
    let expectedLuma = 0;
    let absoluteLumaDelta = 0;
    let squaredLumaDelta = 0;
    const threshold = 6;
    for (let index = 0; index < actual.data.length; index += 4) {
      let maxDelta = 0;
      for (let channel = 0; channel < 3; channel += 1) {
        const actualValue = actual.data[index + channel];
        const expectedValue = expected.data[index + channel];
        sums[channel] += actualValue;
        expectedSums[channel] += expectedValue;
        maxDelta = Math.max(maxDelta, Math.abs(actualValue - expectedValue));
      }
      const actualLuma = actual.data[index] * .2126 +
        actual.data[index + 1] * .7152 + actual.data[index + 2] * .0722;
      const expectedPixelLuma = expected.data[index] * .2126 +
        expected.data[index + 1] * .7152 + expected.data[index + 2] * .0722;
      luma += actualLuma;
      expectedLuma += expectedPixelLuma;
      const lumaDelta = actualLuma - expectedPixelLuma;
      absoluteLumaDelta += Math.abs(lumaDelta);
      squaredLumaDelta += lumaDelta ** 2;
      if (actualLuma < 3) darkClippedActual += 1;
      if (expectedPixelLuma < 3) darkClippedExpected += 1;
      if (actualLuma > 252) brightClippedActual += 1;
      if (expectedPixelLuma > 252) brightClippedExpected += 1;
      if (maxDelta > threshold) changed += 1;
      const strength = Math.min(255, maxDelta * 5);
      diff.data[index] = strength;
      diff.data[index + 1] = maxDelta > threshold ? 24 : strength;
      diff.data[index + 2] = maxDelta > threshold ? 255 - strength : strength;
      diff.data[index + 3] = 255;
    }
    const pixels = width * height;
    context.putImageData(diff, 0, 0);
    canvas.id = 'stadium-visual-diff';
    canvas.style.cssText = 'position:fixed;inset:0;z-index:9999';
    document.body.append(canvas);
    const channels = sums.map((value, index) =>
      (value - expectedSums[index]) / pixels);
    const castDelta = Math.max(...channels) - Math.min(...channels);
    return {
      changedRatio: changed / pixels,
      brightnessDelta: (luma - expectedLuma) / pixels,
      meanAbsoluteLumaDelta: absoluteLumaDelta / pixels,
      lumaRms: Math.sqrt(squaredLumaDelta / pixels),
      darkClippingDelta: (darkClippedActual - darkClippedExpected) / pixels,
      brightClippingDelta:
        (brightClippedActual - brightClippedExpected) / pixels,
      castDelta,
      channels,
    };
  }, baselineUrl);
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
  page.setDefaultTimeout(90_000);
  page.setDefaultNavigationTimeout(90_000);
  const browserErrors = [];
  page.on('console', message => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', error => browserErrors.push(error.message));
  const port = server.address().port;
  const origin = `http://127.0.0.1:${port}`;
  await page.goto(
    `${origin}/stadium_editor/tests_js/seat_view_harness.html`,
  );
  await page.waitForFunction(() => window.seatViewTest?.ready);
  assert.equal(
    await page.evaluate(() => window.seatViewTest.api.kind),
    'three',
    'the editor must render the WebGL seat view',
  );
  const seatStats = await page.evaluate(() => window.seatViewTest.api.stage.stats);
  assert.ok(seatStats.seats > 2_000, 'the WebGL stage must create individual seat instances');
  assert.equal(seatStats.seats, 2_790);
  assert.equal(seatStats.pitchStripes, 10);
  assert.equal(seatStats.pitchLines, 17);
  assert.equal(seatStats.sky, 'day');
  assert.equal(seatStats.floodlightType, 'mast');
  assert.equal(seatStats.floodlightFixtures, 4);
  assert.equal(seatStats.floodlightSources, 4);
  assert.equal(seatStats.floodlightEnabled, false);
  await page.waitForFunction(
    () => window.seatViewTest.api.stage.backgroundReady(),
  );
  const daySky = await backgroundSample(page);
  assert.ok(daySky.every(pixel => pixel[3] === 255), 'day sky must fill the view');
  assert.ok(daySky.some(pixel => pixel[2] > 80), 'day sky must contain blue pixels');
  const dayField = await fieldBrightness(page);

  const initial = await snapshot(page);
  assert.ok(
    Math.hypot(initial.position[0], initial.position[2]) > 50,
    'seat camera must be fixed on the WEST/OST stand',
  );
  const lightToggle = await page.evaluate(async () => {
    const before = window.seatViewTest.api.stage;
    await window.seatViewTest.api.update({floodlight: true});
    return {
      sameStage: before === window.seatViewTest.api.stage,
      enabled: window.seatViewTest.api.stage.stats.floodlightEnabled,
      fixtures: window.seatViewTest.api.stage.stats.floodlightFixtures,
      sources: window.seatViewTest.api.stage.stats.floodlightSources,
    };
  });
  assert.deepEqual(lightToggle, {
    sameStage: true, enabled: true, fixtures: 4, sources: 4,
  });
  assert.ok(
    distance(initial.position, (await snapshot(page)).position) < 1e-6,
    'floodlight toggle must not move the seat camera',
  );
  await page.evaluate(
    () => window.seatViewTest.api.update({floodlight: false}),
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

  const dayNightToggle = await page.evaluate(async () => {
    const before = window.seatViewTest.api.stage;
    const canvas = before.renderer.domElement;
    const cameraPosition = before.camera.position.toArray();
    await window.seatViewTest.api.update({day: false, floodlight: false});
    return {
      sameStage: before === window.seatViewTest.api.stage,
      sameCanvas: canvas === window.seatViewTest.api.stage.renderer.domElement,
      cameraPosition,
      nextCameraPosition: window.seatViewTest.api.stage.camera.position.toArray(),
      lightingMode: window.seatViewTest.api.stage.stats.lightingMode,
    };
  });
  assert.equal(dayNightToggle.sameStage, true);
  assert.equal(dayNightToggle.sameCanvas, true);
  assert.deepEqual(
    dayNightToggle.nextCameraPosition,
    dayNightToggle.cameraPosition,
    'day/night changes must keep geometry and camera in place',
  );
  assert.equal(dayNightToggle.lightingMode, 'night');
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
  const darkField = await fieldBrightness(page);
  assert.ok(
    darkField > 12,
    `ambient night must keep the unlit field readable (${darkField})`,
  );
  assert.ok(
    dayField > darkField,
    `daylight must remain visibly brighter than ambient night (${dayField} > ${darkField})`,
  );
  await page.evaluate(async () => {
    window.__nightStage = window.seatViewTest.api.stage;
    await window.seatViewTest.api.update({floodlight: true});
  });
  const lightField = await fieldBrightness(page);
  assert.ok(
    lightField > darkField * 1.35,
    `floodlight must visibly brighten the stadium (${darkField} -> ${lightField})`,
  );
  assert.equal(
    await page.evaluate(
      () => window.seatViewTest.api.stage === window.__nightStage,
    ),
    true,
    'floodlight toggles must not rebuild stadium geometry',
  );
  const exposureToggle = await page.evaluate(async () => {
    const before = window.seatViewTest.api.stage;
    await window.seatViewTest.api.update({exposure: 1.1});
    return {
      sameStage: before === window.seatViewTest.api.stage,
      exposure: window.seatViewTest.api.stage.stats.toneMappingExposure,
    };
  });
  assert.equal(exposureToggle.sameStage, true);
  assert.ok(exposureToggle.exposure > 1.1);
  assert.equal(
    await page.evaluate(
      () => window.seatViewTest.api.stage.stats.floodlightEnabled,
    ),
    true,
  );
  await page.evaluate(
    () => window.seatViewTest.api.update({camera: 'orbit'}),
  );
  assert.equal(
    await page.evaluate(
      () => window.seatViewTest.api.stage.stats.floodlightEnabled,
    ),
    true,
    'orbit rebuild must preserve the floodlight state',
  );
  await page.evaluate(
    () => window.seatViewTest.api.update({camera: 'seat'}),
  );
  assert.equal(
    await page.evaluate(
      () => window.seatViewTest.api.stage.stats.floodlightEnabled,
    ),
    true,
    'seat rebuild must preserve the floodlight state',
  );

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
    assert.equal(stats.floodlightEnabled, true);
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

  await page.goto(
    `${origin}/stadium_editor/tests_js/seat_view_harness.html` +
    '?scene=campnou&camera=orbit&lighting=night&floodlight=on',
  );
  await page.waitForFunction(() => window.seatViewTest?.ready);
  const rimStats = await page.evaluate(() => window.seatViewTest.api.stage.stats);
  assert.equal(rimStats.floodlightType, 'rim');
  assert.equal(rimStats.floodlightFixtures, 102);
  assert.equal(rimStats.floodlightSources, 12);
  assert.equal(rimStats.floodlightEnabled, true);
  assert.equal(
    browserErrors.filter(message => /shader|uniform|webgl/i.test(message)).length,
    0,
    'bounded Camp Nou rim lighting must render without WebGL shader failures',
  );
});

test('stadium lighting visual references stay readable and color neutral', async t => {
  const server = await serveWorkspace();
  t.after(() => new Promise(resolve => server.close(resolve)));
  const browser = await chromium.launch({
    executablePath: chromiumPath,
    headless: true,
    args: ['--no-sandbox', '--use-gl=swiftshader'],
  });
  t.after(() => browser.close());
  const page = await browser.newPage({
    viewport: {width: 1100, height: 700},
    deviceScaleFactor: 1,
  });
  page.setDefaultTimeout(90_000);
  page.setDefaultNavigationTimeout(90_000);
  const browserErrors = [];
  page.on('console', message => {
    if (message.type() === 'error') browserErrors.push(message.text());
  });
  page.on('pageerror', error => browserErrors.push(error.message));
  const port = server.address().port;
  const origin = `http://127.0.0.1:${port}`;
  const outputDir = join(root, 'test-results', 'stadium-lighting');
  const baselineDir = join(
    root, 'stadium_editor', 'tests_js', 'visual_baselines',
  );
  await mkdir(outputDir, {recursive: true});
  await mkdir(baselineDir, {recursive: true});

  for (const visualCase of visualCases) {
    await t.test(visualCase.name, async () => {
      await page.goto(
        `${origin}/stadium_editor/tests_js/seat_view_harness.html?` +
        visualCase.query,
      );
      await page.waitForFunction(() => window.seatViewTest?.ready);
      await page.evaluate(() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const effective = await page.evaluate(() => {
        const query = new URLSearchParams(location.search);
        const {stats} = window.seatViewTest.api.stage;
        return {
          camera: query.get('camera'),
          lighting: stats.lightingMode,
          floodlightType: stats.floodlightType,
          floodlightFixtures: stats.floodlightFixtures,
          floodlightEnabled: stats.floodlightEnabled,
          palette: window.seatViewTest.scene.palette,
        };
      });
      assert.equal(effective.camera, visualCase.expected.camera);
      assert.equal(effective.lighting, visualCase.expected.lighting);
      assert.equal(
        effective.floodlightType, visualCase.expected.floodlightType,
      );
      assert.equal(
        effective.floodlightFixtures, visualCase.expected.floodlightFixtures,
      );
      assert.equal(effective.floodlightEnabled, true);
      assert.ok(
        effective.palette.every(color => color === visualCase.expected.seatColor),
        `${visualCase.name}: seat palette must match its light/dark scenario`,
      );
      const canvas = page.locator('#editor-stage canvas');
      const baselinePath = join(baselineDir, `${visualCase.name}.png`);
      if (process.env.UPDATE_STADIUM_SNAPSHOTS === '1') {
        await canvas.screenshot({path: baselinePath});
        return;
      }
      const result = await compareVisual(
        page,
        `${origin}/stadium_editor/tests_js/visual_baselines/` +
          `${visualCase.name}.png`,
      );
      assert.equal(
        result.dimensionError,
        undefined,
        `${visualCase.name}: Referenzbild hat ${result.dimensionError}`,
      );
      const failures = [];
      if (result.changedRatio > .005) {
        failures.push(
          `${(result.changedRatio * 100).toFixed(2)}% abweichende Pixel ` +
          '(Kanalabweichung > 6; erlaubt: 0.50%)',
        );
      }
      if (Math.abs(result.brightnessDelta) > 1.5) {
        failures.push(
          `Helligkeitsabweichung ${result.brightnessDelta.toFixed(2)} ` +
          '(erlaubt: ±1.50)',
        );
      }
      if (result.meanAbsoluteLumaDelta > 1) {
        failures.push(
          `mittlere absolute Helligkeitsabweichung ` +
          `${result.meanAbsoluteLumaDelta.toFixed(2)} (erlaubt: 1.00)`,
        );
      }
      if (result.lumaRms > 3) {
        failures.push(
          `Helligkeits-RMS ${result.lumaRms.toFixed(2)} (erlaubt: 3.00)`,
        );
      }
      if (Math.abs(result.darkClippingDelta) > .0025) {
        failures.push(
          `Schwarz-Clipping-Abweichung ` +
          `${(result.darkClippingDelta * 100).toFixed(2)}% ` +
          '(erlaubt: ±0.25%)',
        );
      }
      if (Math.abs(result.brightClippingDelta) > .0025) {
        failures.push(
          `Weiß-Clipping-Abweichung ` +
          `${(result.brightClippingDelta * 100).toFixed(2)}% ` +
          '(erlaubt: ±0.25%)',
        );
      }
      if (result.castDelta > 1.5) {
        failures.push(
          `Farbstich-Abweichung ${result.castDelta.toFixed(2)} ` +
          `(RGB: ${result.channels.map(value => value.toFixed(2)).join('/')}; ` +
          'erlaubt: 1.50)',
        );
      }
      if (failures.length) {
        const diffPath = join(outputDir, `${visualCase.name}-diff.png`);
        await page.locator('#stadium-visual-diff').screenshot({path: diffPath});
        assert.fail(
          `${visualCase.name}: ${failures.join('; ')}. ` +
          `Verstärktes Diff-Bild: ${diffPath}`,
        );
      }
    });
  }
  assert.equal(
    browserErrors.filter(message => /shader|uniform|webgl/i.test(message)).length,
    0,
    'visual reference scenes must render without WebGL shader failures',
  );
});