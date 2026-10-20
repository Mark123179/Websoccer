// Fixed-camera HSV lighting evidence with the unmodified production renderer.
import {createServer} from 'node:http';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {chromium} from 'playwright-core';

const args = process.argv.slice(2);
const study = path.resolve(args[0] || 'generated-artifacts/hsv-night-study');
const scaleArg = args.find(a=>a.startsWith('--scales='))?.split('=')[1];
const scales = scaleArg ? scaleArg.split(',').map(Number) : [];
const serve = args.includes('--serve');
const staticRoot = path.resolve('stadium_editor/static/stadium_editor');
const baselineRaw = await readFile(path.join(study, 'baseline-manifest.json'));
const candidateRaw = await readFile(path.join(study, 'manifest.json'));
const baseline = JSON.parse(baselineRaw), candidate = JSON.parse(candidateRaw);
// Both variants have identical asset hashes; use the reviewed package, not an
// unrelated source-export directory that may predate the seating artwork.
const assetRoot = path.join(study,'package/stadium-models/947',candidate.assetVersion);
const presentation = JSON.parse(await readFile(path.join(study,'presentation.json')));
const sha = bytes=>createHash('sha256').update(bytes).digest('hex');
const html = `<!doctype html><meta charset="utf-8"><title>HSV Lichtvergleich</title><link rel="icon" href="data:,">
<style>html,body{margin:0;background:#02070b}#stage{width:1200px;height:675px}</style>
<div id="stage"></div><script type="module">
import {mountUnityStadium} from '/static/unity_stadium_scene.js';
const q=new URLSearchParams(location.search);
try {
 const baseline=q.get('variant')==='baseline', scale=Number(q.get('scale')||1);
 const presentation=await(await fetch('/presentation.json')).json();
 presentation.presentation.modelUrl='/models/'+(baseline?'baseline':'candidate')+'/manifest.json?scale='+scale;
 window.handle=await mountUnityStadium({element:document.getElementById('stage'),
    presentation:presentation.presentation,tickerPreview:true});
 const roof=q.get('roof')!=='0';
 const camera=handle.stage.camera;
 const lights=handle.stage.scene.children.filter(x=>x.isSpotLight);
 window.setLighting=async function(day,floodlight) {
 await handle.update({day,floodlight,roofVisible:roof});
 window.evidence={camera:{position:camera.position.toArray(),quaternion:camera.quaternion.toArray(),
   projection:camera.projectionMatrix.toArray()},
   lights:lights.map(x=>({id:x.userData.fixture.id,position:x.position.toArray(),
     target:x.target.position.toArray(),intensity:x.intensity,
     onIntensity:x.userData.onIntensity,angle:x.angle,distance:x.distance})),
   roofVisible:roof,day,floodlight,
   exposure:handle.stage.renderer.toneMappingExposure,variant:baseline?'baseline':'candidate',scale};
 };
 await window.setLighting(q.get('night')!=='1',q.get('flood')==='1');
 window.ready=true;
} catch(e) {window.failure=e.stack;console.error(e)}
</script>`;

const server = createServer(async(req,res)=>{
  try {
    const url = new URL(req.url,'http://127.0.0.1'), name = decodeURIComponent(url.pathname);
    if(name==='/favicon.ico') {res.writeHead(204);res.end();return;}
    let data, mime = 'application/octet-stream';
    if(name==='/') {data=html;mime='text/html';}
    else if(name==='/review') {data=await readFile(path.join(study,'pruefbericht.html'));mime='text/html';}
    else if(name==='/night-comparison') {
      const before=await readFile(path.join(study,'views/baseline-night-on.png'));
      const after=await readFile(path.join(study,'views/candidate-night-on.png'));
      data=`<!doctype html><meta charset="utf-8"><style>body{background:#0c151b;color:white;font:18px system-ui;margin:20px}img{width:100%;display:block}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}h1{font-size:24px}</style>
      <h1>HSV · Nacht mit Flutlicht · identische Kamera</h1><p>Separates Prüfpaket · bestehende Registrierung unverändert</p>
      <div class="pair"><figure><img alt="Bisherige Nachtansicht" src="data:image/png;base64,${before.toString('base64')}"><figcaption>Bisher</figcaption></figure>
      <figure><img alt="Kalibrierte Nachtansicht" src="data:image/png;base64,${after.toString('base64')}"><figcaption>HSV-Kandidat · drei belegte Originalquellen</figcaption></figure></div>`;
      mime='text/html';
    }
    else if(name==='/presentation.json') {data=JSON.stringify(presentation);mime='application/json';}
    else if(/^\/models\/(baseline|candidate)\/manifest\.json$/.test(name)) {
      const manifest=structuredClone(name.includes('/baseline/')?baseline:candidate);
      const scale=Number(url.searchParams.get('scale')||1);
      if(!Number.isFinite(scale)||scale<=0||scale>128)throw new Error('Invalid scale');
      // Trial multiplier only; source values and persisted package remain unchanged.
      manifest.fixtures.forEach(f=>{f.intensity*=scale;});
      data=JSON.stringify(manifest);mime='application/json';
    } else {
      const root=name.startsWith('/static/')?staticRoot:assetRoot;
      const relative=name.startsWith('/static/')?name.slice(8):name.replace(/^\/models\/(baseline|candidate)\//,'');
      const file=path.resolve(root,relative);
      if(!file.startsWith(root+path.sep))throw new Error('Invalid path');
      data=await readFile(file);
      mime=file.endsWith('.js')?'text/javascript':file.endsWith('.webp')?'image/webp':mime;
    }
    res.writeHead(200,{'Content-Type':mime,'Cache-Control':'no-store'});res.end(data);
  } catch(e) {console.error('Asset request failed:',req.url,e.message);res.writeHead(404);res.end('Not found');}
});
await new Promise(resolve=>server.listen(serve?8080:0,'0.0.0.0',resolve));
console.log('HSV light study on port',server.address().port);
if(serve) await new Promise(()=>{});
else {
  const output=path.join(study,'views');
  await mkdir(output,{recursive:true});
  const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',args:[
    '--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader',
    '--disable-gpu-sandbox','--disable-accelerated-2d-canvas']});
  const records=[];
  try {
    const cases=[
      ['baseline-day-off','variant=baseline'],['baseline-day-on','variant=baseline&flood=1'],
      ['baseline-night-off','variant=baseline&night=1'],
      ['baseline-night-on','variant=baseline&night=1&flood=1'],
      ...scales.map(scale=>[`trial-${scale}-night-on`,`night=1&flood=1&scale=${scale}`]),
      ['candidate-day-off',''], ['candidate-day-on','flood=1'],
      ['candidate-night-off','night=1'],['candidate-night-on','night=1&flood=1'],
    ];
    let page, activeKey, errors;
    for(const [name,query] of cases) {
      const parameters=new URLSearchParams(query);
      const key=(parameters.get('variant')||'candidate')+':'+(parameters.get('scale')||'1');
      if(key!==activeKey) {
      if(page)await page.close();
      page=await browser.newPage({viewport:{width:1200,height:675}});
      errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text());});
      // Keep the drawing buffer only in the capture browser.
      await page.addInitScript(()=>{
        const original=HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext=function(type,options) {
          return original.call(this,type,type.includes('webgl')?{...options,preserveDrawingBuffer:true}:options);
        };
      });
      await page.goto(`http://127.0.0.1:${server.address().port}/?${query}`);
      await page.waitForFunction(()=>window.ready||window.failure,null,{timeout:120000});
      activeKey=key;
      } else {
        await page.evaluate(({day,floodlight})=>window.setLighting(day,floodlight),
          {day:parameters.get('night')!=='1',floodlight:parameters.get('flood')==='1'});
      }
      const failure=await page.evaluate(()=>window.failure);
      if(failure||errors.length)throw new Error(JSON.stringify({name,failure,errors}));
      const evidence=await page.evaluate(()=>window.evidence);
      const camera=JSON.stringify(evidence.camera);
      if(records.length&&camera!==JSON.stringify(records[0].evidence.camera))
        throw new Error('Camera changed between lighting states');
      if(evidence.lights.length>12)throw new Error('Runtime light limit exceeded');
      if(evidence.lights.some(l=>evidence.floodlight?l.intensity<=0:l.intensity!==0))
        throw new Error('Floodlight state mismatch');
      const image=await page.evaluate(()=>{
        handle.stage.render();return handle.stage.renderer.domElement.toDataURL('image/png');
      });
      const bytes=Buffer.from(image.split(',')[1],'base64');
      await writeFile(path.join(output,name+'.png'),bytes);
      records.push({name,query,evidence,errors,imageSha256:sha(bytes),
        manifestSha256:sha(evidence.variant==='baseline'?baselineRaw:candidateRaw)});
      await writeFile(path.join(output,'render-evidence.json'),JSON.stringify(records,null,2));
      console.log('Captured',name);
    }
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
}
