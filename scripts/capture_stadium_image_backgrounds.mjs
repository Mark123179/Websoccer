// Read-only authenticated visual verification; private session file is deleted
// by the caller. No credentials, game mutations, or permanent browser hooks.
import fs from 'node:fs';
import {chromium} from 'playwright-core';

const dir = process.env.CAPTURE_DIR || '/tmp/stadium-image-backgrounds';
fs.mkdirSync(dir, {recursive: true});
const browser = await chromium.launch({
  executablePath: '/repl/tools/bin/chromium', headless: true,
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
const errors = [], failures = [], requests = [], captures = [];
let rejectNightOnce = true;
try {
  const url = `https://${process.env.REPLIT_DEV_DOMAIN}`;
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  await context.addCookies([{...JSON.parse(fs.readFileSync(process.env.SESSION_FILE)),
    url, httpOnly: true, secure: true, sameSite: 'Lax'}]);
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.status() >= 400) failures.push([response.status(), response.url().split('?')[0]]);
  });
  page.on('request', request => requests.push(request.url().split('?')[0]));
  await page.addInitScript(() => {
    const get = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, options) {
      return get.call(this, type, /webgl/.test(type) ? {...options, preserveDrawingBuffer: true} : options);
    };
  });
  // Browser-only hooks expose the actual camera and expansion API for parity
  // checks. The deployed sources and administrator access remain unchanged.
  await page.route('**/dortmund_editor_scene.js?*', async route => {
    const response = await route.fetch();
    const source = await response.text();
    await route.fulfill({response, body: source.replace('stage: {renderer, render}',
      'stage: {renderer, render, camera}')});
  });
  await page.route('**/ticker_stadium_preview.js?*', async route => {
    const response = await route.fetch();
    await route.fulfill({response, body: (await response.text()).replace(
      'sceneHandle = mounted;', 'sceneHandle = mounted; window.__imageStudyHandle = mounted;')});
  });
  await page.route('**/907/night.webp', route => {
    if (rejectNightOnce) { rejectNightOnce = false; return route.abort('failed'); }
    return route.continue();
  });
  await page.goto(url + '/live/test/', {waitUntil: 'domcontentloaded', timeout: 120000});
  await page.waitForFunction(() => document.querySelector('#ticker-stadium-preview')?.dataset.state === 'ready' ||
    document.querySelector('#ticker-stadium-preview')?.dataset.state === 'error', {timeout: 120000});
  if (await page.locator('#ticker-stadium-preview').getAttribute('data-state') === 'error')
    throw new Error(await page.locator('#ticker-stadium-status').textContent());
  await page.waitForFunction(() => window.__imageStudyHandle);
  if (await page.locator('#ticker-camera-height').count()) throw new Error('Variable camera still present.');
  async function capture(name) {
    await page.waitForTimeout(250);
    const host = page.locator('#ticker-stadium-preview');
    await host.scrollIntoViewIfNeeded();
    await host.screenshot({path: `${dir}/${name}.png`});
    captures.push({name, ...await page.evaluate(() => ({
      profile: document.querySelector('#ticker-stadium-preview').dataset.imageProfile,
      metrics: JSON.parse(document.querySelector('#ticker-stadium-preview').dataset.metrics),
      overflow: document.documentElement.scrollWidth > innerWidth,
      photo: (() => {
        const image = document.querySelector('.ticker-image-background');
        return {width: image.naturalWidth, height: image.naturalHeight};
      })(),
    }))});
  }
  async function profile(value) {
    await page.locator(`.ticker-image-profiles [data-profile="${value}"]`).click();
    await page.waitForFunction(expected =>
      document.querySelector('#ticker-stadium-preview').dataset.imageProfile === expected &&
      !document.querySelector('.ticker-image-profiles button').disabled, value);
  }
  await capture('desktop-day-roof-on');
  await page.locator('.ticker-image-profiles [data-profile="night"]').click();
  await page.waitForFunction(() =>
    document.querySelector('#ticker-stadium-status').textContent.includes('nicht verfügbar') &&
    !document.querySelector('.ticker-image-profiles button').disabled);
  const retainedDay = await page.locator('#ticker-stadium-preview').getAttribute('data-image-profile');
  if (retainedDay !== 'day') throw new Error('Failed image replaced current photo.');
  await profile('night');
  await capture('desktop-night-roof-on');
  await page.locator('#ticker-roof-visible').uncheck();
  await capture('desktop-night-roof-off');
  await profile('day');
  await capture('desktop-day-roof-off');
  await page.locator('#ticker-roof-visible').check();
  const cameraBefore = await page.evaluate(() => window.__imageStudyHandle.stage.camera.projectionMatrix.elements);
  const photosBefore = requests.filter(value => value.includes('/image_backgrounds/')).length;
  await page.evaluate(() => window.__imageStudyHandle.update({
    weights: {NORD: 1, SUED: 1, OST: 1, WEST: 1}, fullConcept: true,
  }));
  await capture('desktop-expanded-same-day-image');
  const cameraAfter = await page.evaluate(() => window.__imageStudyHandle.stage.camera.projectionMatrix.elements);
  if (JSON.stringify(cameraBefore) !== JSON.stringify(cameraAfter)) throw new Error('Expansion moved registered camera.');
  if (photosBefore !== requests.filter(value => value.includes('/image_backgrounds/')).length)
    throw new Error('Expansion requested a new background image.');
  // Restore the original geometry for mobile captures.
  await page.evaluate(() => window.__imageStudyHandle.update({
    weights: {NORD: 0, SUED: 0, OST: 0, WEST: 0}, fullConcept: false,
  }));
  await page.setViewportSize({width: 390, height: 850});
  await capture('mobile-day');
  await profile('night');
  await capture('mobile-night');
  const forbiddenRequests = requests.filter(value =>
    /natural_assets|natural_surroundings|natural_lighting|\/hdri\//.test(value));
  if (forbiddenRequests.length || errors.length || failures.length || captures.some(c => c.overflow))
    throw new Error(JSON.stringify({errors, failures, forbiddenRequests, captures}));
  const report = {captures, errors, failures, forbiddenRequests,
    failedNightRetainedDay: retainedDay === 'day', retryRecovered: true,
    expansionKeptCameraAndImage: true, requests,
    measurement: 'Software WebGL, capture-only preserved buffer; not hardware FPS.'};
  fs.writeFileSync(`${dir}/report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({captures, errors, failures, forbiddenRequests,
    failedNightRetainedDay: true, expansionKeptCameraAndImage: true}, null, 2));
} finally {
  await browser.close();
}
