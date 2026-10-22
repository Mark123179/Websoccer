// Read-only rendering of installed Heidenheim assets. No login or DB writes.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const study = path.resolve('generated-artifacts/heidenheim-study');
const out = path.resolve('generated-artifacts/heidenheim-floodlight-review');
const presentation = JSON.parse(await readFile(path.join(study, 'osm-fresh/installed-presentation.json')));
assert.equal(presentation.presentation.clubFmiId, 880295);
await mkdir(out, {recursive: true});
const html = `<!doctype html><style>html,body{margin:0;background:#02070b}
#stage{width:1200px;height:675px}</style><div id="stage"></div><script type="module">
import {mountUnityStadium} from '/static/stadium_editor/unity_stadium_scene.js?floodlight-review=1';
try {
window.api = await mountUnityStadium({element:document.getElementById('stage'),
presentation:(await(await fetch('/presentation.json')).json()).presentation,tickerPreview:true});
window.ready=true;
}catch(e){window.failure=e.message;}
</script>`;
const server = createServer(async(req, res) => {
  try {
    if (req.method !== 'GET') {res.writeHead(405);res.end();return;}
    const pathname = new URL(req.url, 'http://fixture').pathname;
    if (pathname === '/') {
      res.writeHead(200, {'Content-Type': 'text/html'});res.end(html);return;
    }
    if (pathname === '/presentation.json') {
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify(presentation));return;
    }
    if (!pathname.startsWith('/static/') && !pathname.startsWith('/stadion/model-assets/880295/'))
      throw new Error('Unexpected request');
    const upstream = await fetch(`http://127.0.0.1:5000${req.url}`);
    assert.equal(upstream.status, 200, pathname);
    res.writeHead(200, {'Content-Type': upstream.headers.get('content-type') || 'application/octet-stream'});
    res.end(Buffer.from(await upstream.arrayBuffer()));
  } catch(e) {res.writeHead(500);res.end(e.message);}
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({executablePath: '/repl/tools/bin/chromium',
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
try {
  const page = await browser.newPage({viewport: {width: 1200, height: 675}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(() => window.ready || window.failure, null, {timeout: 120000});
  assert.equal(await page.evaluate(() => window.failure), undefined);
  const evidence = [];
  for (const [name, day, floodlight, roofVisible, effects] of [
    ['tag-aus', true, false, true, true],
    ['tag-an', true, true, true, true],
    ['nacht-aus', false, false, true, true],
    ['nacht-an', false, true, true, true],
    ['nacht-bisher', false, true, true, false],
    ['nacht-ohne-dach', false, true, false, true],
  ]) {
    const result = await page.evaluate(async({day, floodlight, roofVisible, effects}) => {
      const {api} = window;
      const model = api.stage.model, camera = api.stage.camera;
      await api.update({day, floodlight, roofVisible});
      const visuals = api.stage.scene.getObjectByName('SOURCE_FLOODLIGHT_VISUALS');
      const lampCount = visuals.getObjectByName('SOURCE_LAMP_DISC_GLOW').count;
      if (!effects) visuals.visible = false;
      api.stage.render();
      const sources = [];
      api.stage.scene.traverse(o => {if (o.isSpotLight) sources.push(o.intensity);});
      return {image: api.stage.renderer.domElement.toDataURL('image/png'),
        evidence: {...visuals.userData, visible: visuals.visible, lampCount,
          sourceIntensities: sources, modelId: model.uuid, cameraId: camera.uuid,
          cameraPosition: camera.position.toArray()}};
    }, {day, floodlight, roofVisible, effects});
    assert.equal(result.evidence.visible, floodlight && effects);
    assert.equal(result.evidence.lampCount, 144);
    assert.equal(result.evidence.sourceIntensities.length, 12);
    assert.ok(result.evidence.sourceIntensities.every(i => floodlight ? i > 0 : i === 0));
    if (evidence.length) {
      assert.equal(result.evidence.modelId, evidence[0].modelId);
      assert.equal(result.evidence.cameraId, evidence[0].cameraId);
      assert.deepEqual(result.evidence.cameraPosition, evidence[0].cameraPosition);
    }
    await writeFile(path.join(out, `${name}.png`), Buffer.from(result.image.split(',')[1], 'base64'));
    evidence.push({name, day, floodlight, roofVisible, effects, ...result.evidence});
    console.log('Captured', name, 'visible:', result.evidence.visible);
  }
  assert.deepEqual(errors, []);
  const shaderErrors = await page.evaluate(() =>
    window.api.stage.renderer.info.programs.filter(p => p.diagnostics?.runnable === false)
      .map(p => p.diagnostics.programLog));
  assert.deepEqual(shaderErrors, []);
  await writeFile(path.join(out, 'render-evidence.json'), JSON.stringify({errors, shaderErrors, evidence}, null, 2));
  await page.evaluate(() => window.api.dispose());
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
