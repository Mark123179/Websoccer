/** Offline WebGL regression: real Dortmund + Elversberg frames, no DB/server. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {resolve, sep} from 'node:path';
import {chromium} from 'playwright-core';

const root = fileURLToPath(new URL('../', import.meta.url));
const staticRoot = resolve(root, 'stadium_editor/static/stadium_editor');
const out = resolve(root, 'generated-artifacts/grass-render-check');

export async function checkGrassRender() {
  // Rebuild from tracked canonical sources, never an old ignored export/DB.
  const source = JSON.parse(execFileSync('python', ['-c', `
import json
from stadium_editor.elversberg_environment import load_surroundings
with open('stadium_editor/blueprints/v2/elversberg_v2.json') as f:
    scene = json.load(f)
scene['surroundings'] = load_surroundings()
print(json.dumps(scene))
`], {cwd: root, maxBuffer: 4 * 1024 * 1024}).toString());
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/repl/tools/bin/chromium',
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader', '--disable-accelerated-2d-canvas'],
  });
  const states = [], errors = [];
  try {
    await fs.mkdir(out, {recursive: true});
    for (const club of ['dortmund', 'elversberg']) {
      const page = await browser.newPage({viewport: {width: 1880, height: 940}});
      page.setDefaultTimeout(180000);
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {
        if (message.type() === 'error') errors.push(message.text());
      });
      // Fully offline, limited to the static renderer tree. Missing assets fail.
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname === '/') return route.fulfill({
          contentType: 'text/html', body: `<!doctype html>
<style>body{margin:0}#host{width:1880px;height:940px}</style>
<script type="importmap">{"imports":{"three":"/stage/vendor/three.module.js",
"three/addons/":"/stage/vendor/addons/"}}</script><div id="host"></div>`,
        });
        try {
          const path = resolve(staticRoot, '.' + decodeURIComponent(url.pathname));
          assert.ok(path.startsWith(staticRoot + sep));
          const body = await fs.readFile(path);
          const ext = path.split('.').at(-1);
          await route.fulfill({body, contentType: {
            js: 'text/javascript', mjs: 'text/javascript', json: 'application/json', webp: 'image/webp',
            png: 'image/png', svg: 'image/svg+xml',
          }[ext] || 'application/octet-stream'});
        } catch (error) {
          errors.push(`Asset ${url.pathname}: ${error.message}`);
          await route.abort();
        }
      });
      await page.goto('http://grass-study.test/');
      await page.evaluate(async ({club, source}) => {
        window.requestAnimationFrame = () => 0;
        window.ResizeObserver = class { observe() {} disconnect() {} unobserve() {} };
        const {mountStudyModel} = await import('/study_models.js');
        const {renderGrassDiagnostic} = await import('/grass_surface_diagnostic.js');
        const handle = await mountStudyModel({
          host: document.getElementById('host'), club, source, concept: 'cutaway',
        });
        if (club === 'dortmund') handle.model.rotation.y += Math.PI;
        handle.setRoof(true);
        window.diagnostic = {handle, renderGrassDiagnostic};
      }, {club, source});
      for (const fault of ['none', 'flipY', 'mirrorX', 'linearColorSpace', 'none']) {
        const result = await page.evaluate(async fault => {
          const {handle, renderGrassDiagnostic} = window.diagnostic;
          return renderGrassDiagnostic(handle, fault);
        }, fault);
        const {image, ...proof} = result;
        const file = `${club}-${states.length}-${fault}.png`;
        const bytes = Buffer.from(image.split(',')[1], 'base64');
        await fs.writeFile(resolve(out, file), bytes);
        states.push({club, file, sha256: createHash('sha256').update(bytes).digest('hex'), ...proof});
        assert.equal(proof.surfaceMeshes, 10, `${club}: all ten real grass surfaces`);
        assert.equal(proof.ok, fault === 'none',
          `${club}/${fault}: ${JSON.stringify(proof.failures)}`);
      }
      await page.evaluate(() => window.diagnostic.handle.dispose());
      await page.close();
    }
    const first = states[0];
    for (const state of states) {
      assert.deepEqual(state.projection, first.projection, 'identical field projection');
      assert.deepEqual(state.view, first.view, 'identical camera pose');
      assert.deepEqual(state.samples.map(s => s.pixel), first.samples.map(s => s.pixel),
        'identical rendered reference positions in both stadium frames');
    }
    assert.deepEqual(errors, [], 'no missing assets or browser/renderer errors');
    return {states, errors};
  } finally {
    await fs.mkdir(out, {recursive: true});
    await fs.writeFile(resolve(out, 'verification.json'), JSON.stringify({states, errors}, null, 2));
    await browser.close();
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = await checkGrassRender();
  console.log(`${result.states.length} WebGL checks passed (two frames, three negative controls, recovery).`);
}
