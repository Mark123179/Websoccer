// Isolated source review with the application's real Three.js renderer.
import {createServer} from 'node:http';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const out = path.resolve('generated-artifacts/mainz-study');
const staticDir = path.resolve('stadium_editor/static/stadium_editor');
const assets = path.join(out,'source-export');
const manifest = JSON.parse(await readFile(path.join(out,'manifest.json'),'utf8'));
const base = `/models/918/${manifest.assetVersion}/`;
const contentType = file => file.endsWith('.js')?'text/javascript':
  file.endsWith('.json')?'application/json':file.endsWith('.webp')?'image/webp':
  file.endsWith('.png')?'image/png':'application/octet-stream';
const html = `<!doctype html><meta charset="utf-8"><style>
  html,body{margin:0;background:#060b10;color:white}
  #stage{width:1200px;height:675px;position:relative}
  #message{position:absolute;bottom:12px;left:16px;color:#d3dce4;
    font:14px sans-serif;background:#0b1622b8;padding:6px 10px}
  </style><div id="stage"></div><div id="message">Mainz · Quellmodell / lokale Vorschau</div>
  <script type="module">
  import {mountUnityStadium} from '/static/unity_stadium_scene.js';
  const q=new URLSearchParams(location.search);
  try {
    const {presentation}=await(await fetch('/presentation.json')).json();
    window.stage=await mountUnityStadium({element:document.getElementById('stage'),
      presentation,tickerPreview:q.get('ticker')==='1'});
    await window.stage.update({
      day:q.get('night')!=='1',floodlight:q.get('flood')==='1',
      roofVisible:q.get('roof')!=='0',camera:q.get('seat')==='1'?'seat':'orbit',
      orbit:{azimuth:Number(q.get('az')||55),elevation:Number(q.get('el')||37)}
    });
    const roof=window.stage.stage.model.children.filter(x=>x.name?.startsWith('SOURCE_DACH_'));
    window.evidence={roofMeshes:roof.length,visibleRoof:roof.filter(x=>x.visible).length,
      fixtures:window.stage.lightingEvidence().length,
      modelMeshes:window.stage.stage.model.children.length};
    window.ready=true;
  } catch(e){window.failure=e.message;console.error(e)}
  </script>`;
const server=createServer(async(req,res)=>{
  try {
    const name=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);
    if (name==='/') {res.writeHead(200,{'Content-Type':'text/html'});res.end(html);return}
    let file;
    if(name==='/presentation.json')file=path.join(out,'presentation.json');
    else if(name.startsWith('/static/'))file=path.join(staticDir,name.slice(8));
    else if(name.startsWith(base))
      file=path.join(assets,name.slice(base.length));
    else throw new Error('unknown path');
    const root=name.startsWith('/static/')?staticDir:
      name==='/presentation.json'?out:assets;
    const resolved=path.resolve(file);
    if(!resolved.startsWith(root+path.sep))throw new Error('invalid path');
    const data=name===base+'manifest.json'?
      await readFile(path.join(out,'manifest.json')):await readFile(file);
    res.writeHead(200,{'Content-Type':contentType(resolved),'Cache-Control':'no-store'});
    res.end(data);
  } catch(e){res.writeHead(404);res.end('Not found')}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
await mkdir(path.join(out,'ansichten'),{recursive:true});
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',args:[
  '--no-sandbox','--use-gl=angle','--use-angle=swiftshader',
  '--enable-unsafe-swiftshader','--disable-gpu-sandbox','--disable-accelerated-2d-canvas'
]});
const captures=[];
const selected = new Set(process.argv.slice(2));
try {
  for(const [name,query] of [
    ['3d-editor-dach-an',''],['3d-editor-dach-aus','roof=0'],
    ['ticker-tag-dach-an','ticker=1'],['ticker-tag-dach-aus','ticker=1&roof=0'],
    ['ticker-nacht-flutlicht','ticker=1&night=1&flood=1'],
    ['editor-nacht-ohne-flutlicht','night=1'],
    ['editor-nacht-flutlicht','night=1&flood=1'],
    ['tribuene-nah','az=90&el=12'],['draufsicht','az=0&el=80'],
    ['sitzkamera','seat=1'],
  ]) {
    if(selected.size && !selected.has(name))continue;
    const page=await browser.newPage({viewport:{width:1200,height:675}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/?${query}`);
    await page.waitForFunction(()=>window.ready||window.failure,{timeout:90000});
    const failure=await page.evaluate(()=>window.failure);
    if(failure||errors.length)throw new Error(JSON.stringify({name,failure,errors}));
    const evidence=await page.evaluate(()=>window.evidence);
    if(evidence.roofMeshes!==34||evidence.fixtures!==12 ||
       evidence.visibleRoof!==(query.includes('roof=0')?0:34))
      throw new Error(JSON.stringify({name,evidence}));
    await page.waitForTimeout(300);
    const image=await page.evaluate(()=>{
      window.stage.stage.render();
      return window.stage.stage.renderer.domElement.toDataURL('image/png');
    });
    await writeFile(path.join(out,'ansichten',`${name}.png`),
      Buffer.from(image.split(',')[1],'base64'));
    captures.push({name,query,evidence,errors,assetVersion:manifest.assetVersion});
    await writeFile(path.join(out,'render-evidence.json'),JSON.stringify(captures,null,2));
    console.log('Captured',name,JSON.stringify(evidence));
    await page.close();
  }
  await writeFile(path.join(out,'render-evidence.json'),JSON.stringify(captures,null,2));
} finally {
  await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
