import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright-core';
import {groundFixture, markers, grass} from './fixtures/unity_ground_fixture.mjs';

const root = new URL('../..', import.meta.url);
const harness = '/stadium_editor/tests_js/unity_ground_harness.html';

async function serve() {
  const fixtures = {modern: groundFixture(), legacy: groundFixture(true)};
  const server = createServer(async (request, response) => {
    try {
      const path = new URL(request.url, 'http://fixture').pathname;
      const match = path.match(/^\/fixture\/(modern|legacy)\/(.+)$/);
      let body, type;
      if (match) {
        const fixture = fixtures[match[1]];
        const files = {
          'manifest.json': [JSON.stringify(fixture.manifest), 'application/json'],
          'geometry.bin': [fixture.geometry, 'application/octet-stream'],
          'markers.svg': [markers, 'image/svg+xml'],
          'grass.svg': [grass, 'image/svg+xml'],
        };
        [body, type] = files[match[2]] || [];
        assert.ok(body);
      } else {
        const url = new URL(`.${path}`, root);
        assert.ok(fileURLToPath(url).startsWith(fileURLToPath(root)));
        body = await readFile(url);
        type = path.endsWith('.html') ? 'text/html' : 'text/javascript';
      }
      response.writeHead(200, {'content-type': type});
      response.end(body);
    } catch {
      response.writeHead(404); response.end('Not found');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server;
}

test('Unity ground materials and world UVs remain visible in real WebGL', {timeout: 60000}, async t => {
  const server = await serve();
  t.after(() => new Promise(resolve => server.close(resolve)));
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/repl/tools/bin/chromium',
    headless: true,
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  t.after(() => browser.close());
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const load = async legacy => {
    await page.goto(`${origin}${harness}${legacy ? '?legacy' : ''}`);
    assert.equal(await page.evaluate(() => window.groundReady), true);
  };
  await load(false);
  const modern = await page.evaluate(() => window.groundTest.inspect());
  assert.deepEqual(modern.marker, {transparent: true, alphaTest: .03, depthWrite: false});
  assert.deepEqual(modern.projected, {transparent: false, alphaTest: 0, depthWrite: true});
  // Independent explicit results include every coefficient and nonzero Y.
  const expectedUv = [.15, .26, .814, .132, .898, .804, .234, .932];
  modern.uv.forEach((value, i) => assert.ok(Math.abs(value - expectedUv[i]) < 1e-6,
    `world UV coefficient regression at component ${i}: ${value}`));
  assert.deepEqual(modern.sourceUv, [0, 0, 1, 0, 1, 1, 0, 1]);

  const pixels = await page.evaluate(() => window.groundTest.markers());
  for (const i of [0, 1]) assert.deepEqual(pixels.actual[i], pixels.background[i],
    i === 0 ? 'transparent carrier must not darken grass' : 'alphaTest must discard faint texels');
  const brightness = pixel => pixel.slice(0, 3).reduce((a, b) => a + b, 0);
  assert.ok(brightness(pixels.actual[2]) > brightness(pixels.background[2]) + 30,
    'half-alpha marking must remain visible');
  assert.ok(brightness(pixels.actual[3]) > brightness(pixels.actual[2]) + 30,
    'solid marking must be brighter than the blended marking');
  const depth = await page.evaluate(() => window.groundTest.depthProbe());
  assert.ok(depth[0] > depth[1] + 100 && depth[0] > depth[2] + 100,
    'transparent carriers must not write depth and occlude later geometry');

  const colors = await page.evaluate(() => window.groundTest.projection());
  for (const [i, channel] of [[0, 0], [1, 2], [3, 1]]) {
    assert.ok(colors[i][channel] > 100, `projected patch ${i} must be visible`);
    for (const other of [0, 1, 2].filter(c => c !== channel))
      assert.ok(colors[i][channel] > colors[i][other] + 80, `wrong world-UV patch ${i}`);
  }
  assert.ok(colors[2][0] > 100 && colors[2][1] > 100 && colors[2][2] < 10,
    'fourth world-UV quadrant must be yellow');
  await page.evaluate(() => window.groundTest.dispose());

  await load(true);
  const legacy = await page.evaluate(() => window.groundTest.inspect());
  for (const material of [legacy.marker, legacy.projected])
    assert.deepEqual(material, {transparent: false, alphaTest: 0, depthWrite: true});
  assert.deepEqual(legacy.uv, [1, 0, 0, 0, 0, 1, 1, 1],
    'old manifests must keep their original UV buffer');
  const oldPixels = await page.evaluate(() => window.groundTest.markers());
  assert.ok(brightness(oldPixels.actual[0]) < brightness(oldPixels.background[0]) - 30,
    'legacy carrier deliberately stays opaque: do not change old rendering defaults');
  assert.ok(brightness(oldPixels.actual[3]) > brightness(oldPixels.background[3]) + 30);
  await page.evaluate(() => window.groundTest.dispose());
  assert.deepEqual(errors, [], 'no renderer errors may be swallowed');
});
