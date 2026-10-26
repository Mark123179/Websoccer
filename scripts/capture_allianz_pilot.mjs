// Read-only visual evidence: installed source model, original/pilot modules.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright-core';

const root = path.resolve('generated-artifacts/allianz-pilot-20261026');
const scene = JSON.parse(await readFile(path.join(root, 'baseline/live-scene.json')));
assert.equal(scene.presentation.clubFmiId, 915);
const beforeModule = execFileSync('unzip', ['-p',
  path.join(root, 'baseline/original-source.zip'),
  'stadium_editor/static/stadium_editor/unity_stadium_scene.js']);
let baseline = true;
const html = `<!doctype html><style>body{margin:0;background:#071316}
#stage{width:1200px;height:675px}</style><div id="stage"></div><script type="module">
import {mountUnityStadium} from '/static/stadium_editor/unity_stadium_scene.js?v=75';
try {
 window.api=await mountUnityStadium({element:document.getElementById('stage'),
 presentation:(await(await fetch('/presentation.json')).json()).presentation});
 window.ready=true;
}catch(e){window.failure=e.stack;}
</script>`;
const cache = new Map();
const server = createServer(async(req, res) => {
  try {
    assert.equal(req.method, 'GET');
    const url = new URL(req.url, 'http://fixture');
    if (url.pathname === '/') {
      res.writeHead(200, {'Content-Type':'text/html'}); res.end(html); return;
    }
    if (url.pathname === '/ui') {
      res.writeHead(200, {'Content-Type':'text/html'});
      res.end(await readFile(path.join(root, 'pilot-ui.html'))); return;
    }
    if (url.pathname === '/presentation.json') {
      res.writeHead(200, {'Content-Type':'application/json'});
      res.end(JSON.stringify(scene)); return;
    }
    if (baseline && url.pathname === '/static/stadium_editor/unity_stadium_scene.js') {
      res.writeHead(200, {'Content-Type':'text/javascript'}); res.end(beforeModule); return;
    }
    assert.ok(url.pathname.startsWith('/static/') ||
      url.pathname.startsWith('/stadion/model-assets/915/'));
    const key = url.pathname;
    if (!cache.has(key) || key.startsWith('/static/')) {
      const upstream = await fetch(`http://127.0.0.1:5000${req.url}`);
      assert.equal(upstream.status, 200, key);
      cache.set(key, {type:upstream.headers.get('content-type'),
        body:Buffer.from(await upstream.arrayBuffer())});
    }
    const value = cache.get(key);
    res.writeHead(200, {'Content-Type':value.type}); res.end(value.body);
  } catch(e) { res.writeHead(500); res.end(e.message); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader',
    '--enable-unsafe-swiftshader','--disable-accelerated-2d-canvas']});
const report = {};
try {
  for (const mode of (process.argv.includes('--after-only') ? ['after'] : ['before', 'after'])) {
    baseline = mode === 'before';
    const out = path.join(root, mode);
    await mkdir(out, {recursive:true});
    const page = await browser.newPage({viewport:{width:1200,height:675},
      deviceScaleFactor:1,reducedMotion:'reduce'});
    page.setDefaultTimeout(90000);
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => window.ready || window.failure, null, {timeout:180000});
    assert.equal(await page.evaluate(() => window.failure), undefined);
    const evidence = [];
    if (process.argv.includes('--calibrate')) {
      for (const scale of [32,64,128]) {
        const image = await page.evaluate(async scale => {
          await window.api.update({day:false,floodlight:true,camera:'seat',roofVisible:true});
          window.api.stage.scene.traverse(light => {
            const fixture = light.userData.fixture;
            if (fixture) light.intensity = fixture.intensity * scale *
              Math.min(4, Math.sqrt(fixture.representedIds.length));
          });
          window.api.stage.render();
          return window.api.stage.renderer.domElement.toDataURL('image/png');
        }, scale);
        await writeFile(path.join(out, `calibration-${scale}.png`),
          Buffer.from(image.split(',')[1], 'base64'));
        console.log('calibration', scale, 'captured');
      }
      await page.close();
      continue;
    }
    for (const [name, day, floodlight, camera, roofVisible] of [
      ['day-exterior',true,false,'orbit',true],
      ['night-exterior',false,true,'orbit',true],
      ['night-lights-off',false,false,'orbit',true],
      ['day-interior',true,false,'seat',true],
      ['night-interior',false,true,'seat',true],
      ['night-no-roof',false,true,'orbit',false],
    ]) {
      const shot = await page.evaluate(async state => {
        const {api} = window;
        await api.update(state);
        api.stage.render();
        const {renderer,camera,model} = api.stage;
        const lights = [];
        api.stage.scene.traverse(light => {
          if (light.userData.fixture) lights.push({
            id:light.userData.fixture.id, intensity:light.intensity,
            position:light.position.toArray(),
            sourcePosition:light.userData.fixture.position,
          });
        });
        return {image:renderer.domElement.toDataURL('image/png'),
          lights,
          modelId:model.uuid,cameraId:camera.uuid,cameraPosition:camera.position.toArray(),
          cameraMatrix:camera.projectionMatrix.toArray(),
          drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles};
      }, {day,floodlight,camera,roofVisible});
      await writeFile(path.join(out, `${name}.png`),
        Buffer.from(shot.image.split(',')[1], 'base64'));
      delete shot.image;
      evidence.push({name,...shot});
      console.log(mode, name, 'captured');
    }
    for (const shot of evidence) {
      assert.equal(shot.lights.length, 12);
      shot.lights.forEach(light => assert.deepEqual(light.position,light.sourcePosition));
    }
    assert.ok(evidence.find(shot => shot.name === 'night-exterior').lights.every(light => light.intensity > 0));
    assert.ok(evidence.find(shot => shot.name === 'night-lights-off').lights.every(light => light.intensity === 0));
    assert.equal(evidence[0].modelId, evidence[1].modelId);
    assert.equal(evidence[0].cameraId, evidence[1].cameraId);
    assert.deepEqual(evidence[0].cameraPosition,evidence[1].cameraPosition);
    assert.deepEqual(evidence[0].cameraMatrix,evidence[1].cameraMatrix);
    if (mode === 'after') {
      await page.emulateMedia({reducedMotion:'no-preference'});
      const animation = await page.evaluate(async() => {
        await window.api.update({day:true});
        await new Promise(resolve => setTimeout(resolve,1750));
        const renderer=window.api.stage.renderer;
        const before=renderer.info.render.frame;
        await window.api.update({day:false});
        await new Promise(resolve => setTimeout(resolve,800));
        const during=renderer.info.render.frame;
        await new Promise(resolve => setTimeout(resolve,1000));
        const finished=renderer.info.render.frame;
        await new Promise(resolve => setTimeout(resolve,200));
        return {before,during,finished,idle:renderer.info.render.frame};
      });
      assert.ok(animation.during>animation.before+1, 'Transition must paint intermediate frames');
      assert.ok(animation.finished>animation.during,'Transition must reach the final frame');
      assert.equal(animation.finished,animation.idle,'No idle animation loop');
      report.animation=animation;
    }
    assert.deepEqual(errors,[]);
    report[mode]={evidence,errors};
    await page.evaluate(() => window.api.dispose());
    await page.close();
  }
  if (process.argv.includes('--ui')) {
    baseline = false;
    const page = await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});
    await page.goto(`http://127.0.0.1:${server.address().port}/ui`);
    await page.waitForFunction(() =>
      ['ready','error'].includes(document.querySelector('#pilotStatus')?.dataset.state),
      null, {timeout:180000});
    assert.equal(await page.locator('#pilotStatus').getAttribute('data-state'),'ready');
    await page.locator('#pilotDay').uncheck();
    await page.locator('#pilotFloodlight').check();
    await page.locator('#pilotCamera').selectOption('seat');
    await page.locator('#pilotRoof').uncheck();
    const image = await page.evaluate(() =>
      document.querySelector('#pilotStage canvas').toDataURL('image/png'));
    await writeFile(path.join(root,'after/pilot-ui-controls.png'),
      Buffer.from(image.split(',')[1],'base64'));
    report.ui={status:'ready',day:false,floodlight:true,roof:false,camera:'seat'};
    console.log('Actual pilot template and all four UI controls verified');
    await page.close();
  }
  await writeFile(path.join(root,'render-evidence.json'),JSON.stringify(report,null,2));
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
