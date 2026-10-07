// Read-only browser measurements. Session material must be in a private file.
// SESSION_FILE=/tmp/private.json CAPTURE_DIR=/tmp/captures node scripts/capture_natural_surroundings.mjs
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright-core';
const dir = process.env.CAPTURE_DIR || '/tmp/natural-surroundings';
const captureSet = process.env.CAPTURE_SET || 'all';
fs.mkdirSync(dir, {recursive: true});
const browser = await chromium.launch({
  executablePath: '/repl/tools/bin/chromium', headless: true,
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
try {
  const context = await browser.newContext({viewport: captureSet === 'mobile'
    ? {width: 390, height: 850} : {width: 1440, height: 1000}});
  const url = `https://${process.env.REPLIT_DEV_DOMAIN}`;
  await context.addCookies([{...JSON.parse(fs.readFileSync(process.env.SESSION_FILE)),
    url, httpOnly: true, secure: true, sameSite: 'Lax'}]);
  const page = await context.newPage();
  if (process.env.BASELINE_COMPARE === '1') {
    // Baseline geometry/materials from HEAD, but identical final canvas/camera
    // framing. Browser-only response interception never changes app files.
    const original = execFileSync('git',['show','HEAD:stadium_editor/static/stadium_editor/dortmund_editor_scene.js'],{encoding:'utf8'});
    const baseline = original.replace('tickerPreview ? TICKER_VIEW_OFFSET : verticalFraming',
      'tickerPreview ? -.24 : verticalFraming').replace(
      'const render = () => { positionCamera(); renderer.render(scene, camera); };',
      `const render = () => { positionCamera(); const t=performance.now(); renderer.render(scene,camera);
        element.dataset.metrics=JSON.stringify({renderSubmitMs:performance.now()-t,
          triangles:renderer.info.render.triangles,drawCalls:renderer.info.render.calls,
          geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures}); };`);
    await page.route('**/dortmund_editor_scene.js?*',route=>route.fulfill({status:200,contentType:'application/javascript',body:baseline}));
  }
  const errors = [], failures = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => {if (r.status() >= 400) failures.push([r.status(),r.url().split('?')[0]]);});
  // Capture-only override: never enable the permanent buffer in app code.
  await page.addInitScript(() => {
    const get = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, options) {
      const result = get.call(this, type, /webgl/.test(type) ? {...options, preserveDrawingBuffer: true} : options);
      if (result && /webgl/.test(type)) {
        window.__captureGL = result;
        const draw = result.drawElements.bind(result);
        window.__drawSamples = [];
        result.drawElements = function (...args) {
          const t = performance.now(); const out = draw(...args);
          window.__drawSamples.push(performance.now() - t); return out;
        };
      }
      return result;
    };
  });
  const response = await page.goto(url + '/live/test/', {waitUntil: 'domcontentloaded', timeout: 120000});
  if (!response.ok()) throw new Error(`HTTP ${response.status()}`);
  await page.waitForSelector('#ticker-stadium-preview[data-state="ready"], #ticker-stadium-preview[data-state="error"]', {timeout: 180000});
  if (await page.locator('#ticker-stadium-preview').getAttribute('data-state') === 'error')
    throw new Error(await page.locator('#ticker-stadium-status').textContent());
  await page.waitForFunction(() => !document.querySelector('#ticker-camera-height').disabled);
  const results = [];
  async function capture(name) {
    await page.waitForTimeout(800);
    const data = await page.evaluate(() => {
      const canvas = document.querySelector('#ticker-stadium-preview canvas');
      const t = performance.now(); window.__captureGL.finish();
      return {image:canvas.toDataURL('image/png'),finishMs:performance.now()-t,
        width:canvas.width,height:canvas.height,
        overflow:document.documentElement.scrollWidth>innerWidth,
        status:document.querySelector('#ticker-stadium-status').textContent,
        metrics:document.querySelector('#ticker-stadium-preview').dataset.metrics || null};
    });
    fs.writeFileSync(`${dir}/${name}.png`, Buffer.from(data.image.split(',')[1], 'base64'));
    delete data.image; results.push({name,...data});
    fs.writeFileSync(`${dir}/checkpoint.json`, JSON.stringify({results,errors,failures},null,2));
    console.log(`Captured ${name}: ${Math.round(data.finishMs)} ms GPU finish`);
  }
  if (captureSet === 'all' || captureSet === 'desktop') {
  await capture('desktop-roof-on');
  await page.locator('#ticker-roof-visible').uncheck();
  await capture('desktop-roof-off');
  for (const degrees of [35, 75]) {
    await page.locator('#ticker-camera-height').evaluate((e,n)=>{e.value=n;e.dispatchEvent(new Event('input'));},degrees);
    await capture(`desktop-height-${degrees}`);
  }
  await page.locator('#ticker-camera-reset').click();
  await page.locator('#ticker-roof-visible').check();
  await capture('desktop-restored');
  }
  if (captureSet === 'all' || captureSet === 'mobile') {
  await page.setViewportSize({width:390,height:850});
  await page.locator('#ticker-roof-visible').uncheck();
  await capture('mobile-roof-off');
  }
  if (captureSet === 'lighting' || captureSet === 'mobile') {
    await page.locator('#ticker-roof-visible').uncheck();
    await page.getByRole('button',{name:'Flutlicht-Abend',exact:true}).click();
    await capture(captureSet === 'mobile' ? 'mobile-night' : 'desktop-night');
    await page.locator('#ticker-camera-height').evaluate(e=>{
      e.value=35;e.dispatchEvent(new Event('input'));
    });
    await capture(captureSet === 'mobile' ? 'mobile-night-height-35' : 'desktop-night-height-35');
    await page.getByRole('button',{name:'Tageslicht',exact:true}).click();
    await capture(captureSet === 'mobile' ? 'mobile-day-restored' : 'desktop-day-restored');
  }
  const resources = await page.evaluate(() => performance.getEntriesByType('resource')
    .filter(e=>/stadium_editor/.test(e.name)).map(e=>({file:e.name.split('/').pop(),bytes:e.encodedBodySize,durationMs:Math.round(e.duration)})));
  const report={results,errors,failures,resources};
  fs.writeFileSync(`${dir}/report.json`,JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
  if (errors.length || failures.length || results.some(r=>r.overflow)) process.exitCode=1;
} finally { await browser.close(); }
