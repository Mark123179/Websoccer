// Isolated, unsigned software-WebGL review with the actual project modules.
import {createServer} from 'node:http';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const packageDir = path.resolve(process.argv[2]);
const out = path.resolve('generated-artifacts/augsburg-v2-korrektur');
const staticDir = path.resolve('stadium_editor/static/stadium_editor');
const html = `<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;background:#03070c}#stage{width:1000px;height:560px;position:relative}</style>
<div id="stage"></div><script type="module">
import {mountUnityStadium} from '/static/unity_stadium_scene.js';
const q=new URLSearchParams(location.search);
try {
  const {presentation}=await(await fetch('/presentation.json')).json();
  window.stage=await mountUnityStadium({element:document.getElementById('stage'),
    presentation,tickerPreview:q.get('ticker')==='1'});
  await window.stage.update({day:q.get('night')!=='1',floodlight:q.get('night')==='1',
    roofVisible:q.get('roof')!=='0',camera:q.get('seat')==='1'?'seat':'orbit',
    orbit:{azimuth:Number(q.get('az')||54.43),elevation:Number(q.get('el')||37.24)}});
  const env=window.stage.stage.scene.getObjectByName('EDITOR_SURROUNDINGS_3D');
  window.evidence={terrain:env.userData.terrain,counts:env.userData.counts,
    environmentY:env.position.y,modelY:window.stage.stage.model.position.y};
  window.ready=true;
} catch(error) {window.failure=String(error.stack||error);}
</script>`;
const server = createServer(async (req, res) => {
  try {
    const name = decodeURIComponent(new URL(req.url, 'http://capture').pathname);
    let body, type;
    if (name === '/') { body=html; type='text/html'; }
    else if (name === '/presentation.json') {
      body=await readFile(path.join(out,'presentation_replit_korrigiert.json'));
      type='application/json';
    } else {
      const root = name.startsWith('/static/') ? staticDir :
        name.startsWith('/models/2238/7718595a38dc4253/') ?
          path.join(packageDir,'stadium-models/2238/7718595a38dc4253') : null;
      if (!root) throw new Error('not found');
      const relative = name.startsWith('/static/') ? name.slice(8) : name.split('/').slice(4).join('/');
      const file=path.resolve(root,relative);
      if (!file.startsWith(root+path.sep)) throw new Error('invalid path');
      body=await readFile(file);
      type=file.endsWith('.js')?'text/javascript':file.endsWith('.json')?
        'application/json':file.endsWith('.webp')?'image/webp':'application/octet-stream';
    }
    res.writeHead(200,{'Content-Type':type,'Cache-Control':'no-store'});res.end(body);
  } catch {res.writeHead(404);res.end('Not found');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
await mkdir(path.join(out,'ansichten'),{recursive:true});
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader',
    '--enable-unsafe-swiftshader','--disable-gpu-sandbox','--disable-accelerated-2d-canvas']});
const captures=[];
try {
  for (const [name,query] of [
    ['editor-dach-an',''],['editor-dach-aus','roof=0'],
    ['nord-tief','az=0&el=10'],['sued-tief','az=180&el=10'],
    ['ost-tief','az=90&el=10'],['west-tief','az=270&el=10'],
    ['draufsicht','az=0&el=80'],['ticker-nacht','ticker=1&night=1'],
    ['sitzkamera','seat=1'],
  ]) {
    const page=await browser.newPage({viewport:{width:1000,height:560}});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/?${query}`);
    await page.waitForFunction(()=>window.ready||window.failure,{timeout:90000});
    const failure=await page.evaluate(()=>window.failure);
    if(failure)throw new Error(failure);
    await page.waitForTimeout(350);
    const evidence=await page.evaluate(()=>window.evidence);
    if(evidence.environmentY!==7.7 ||
        JSON.stringify(evidence.terrain.omitted)!==JSON.stringify({green:[3],water:[]}) ||
        errors.length)throw new Error(JSON.stringify({evidence,errors}));
    // Export actual WebGL pixels, not the unreliable headless compositor.
    const image=await page.evaluate(()=>{
      window.stage.stage.render();
      return window.stage.stage.renderer.domElement.toDataURL('image/png');
    });
    await writeFile(path.join(out,'ansichten',`${name}.png`),Buffer.from(image.split(',')[1],'base64'));
    captures.push({name,query,evidence,errors});
    console.log('Captured',name);
    await page.close();
  }
  await writeFile(path.join(out,'render-evidence.json'),JSON.stringify(captures,null,2));
} finally {
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
