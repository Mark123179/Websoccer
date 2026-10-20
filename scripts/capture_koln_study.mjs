// Check the Cologne package through the application's unchanged WebGL renderer.
import {createServer} from 'node:http';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright-core';

const study = path.resolve('generated-artifacts/koln-study');
const review = path.join(study,'osm-fresh');
const assets = path.join(study,'source-export');
const staticDir = path.resolve('stadium_editor/static/stadium_editor');
const manifest = JSON.parse(await readFile(path.join(review,'manifest.json'),'utf8'));
const base = `/models/916/${manifest.assetVersion}/`;
const installed = process.argv.includes('--installed');
const flatRoofs = process.argv.includes('--flat-roofs');
const roofStudy = process.argv.includes('--roof-study');
const presentationFile = installed ? path.join(review,'installed-presentation.json') :
  path.join(review,'presentation.json');
let presentationBytes=await readFile(presentationFile);
if(flatRoofs){
  const data=JSON.parse(presentationBytes);
  for(const g of data.presentation.surroundings.buildingParts.groups)for(const p of g.parts)
    for(const key of ['roofSurfaces','roofStatus','roofRejection','rejectedRoofEvidence'])delete p[key];
  presentationBytes=Buffer.from(JSON.stringify(data));
}
const presentationSha256=createHash('sha256').update(presentationBytes).digest('hex');
const html = `<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;background:#060b10;color:white}
#stage{width:1200px;height:675px;position:relative}
</style><div id="stage"></div><script type="module">
import {mountUnityStadium} from '/static/unity_stadium_scene.js';
import {editorPointToDortmund} from '/static/dortmund_surroundings.js';
const q=new URLSearchParams(location.search);
try {
  const {presentation}=await(await fetch('/presentation.json')).json();
  window.stage=await mountUnityStadium({element:document.getElementById('stage'),
    presentation,tickerPreview:q.get('ticker')==='1'});
  await window.stage.update({day:q.get('night')!=='1',floodlight:q.get('flood')==='1',
    roofVisible:q.get('roof')!=='0',camera:q.get('seat')==='1'?'seat':'orbit',
    orbit:{azimuth:Number(q.get('az')||55),elevation:Number(q.get('el')||37)}});
  const roof=window.stage.stage.model.children.filter(x=>x.name?.startsWith('SOURCE_DACH_'));
  const env=window.stage.stage.scene.getObjectByName('EDITOR_SURROUNDINGS_3D');
  window.evidence={roofMeshes:roof.length,visibleRoof:roof.filter(x=>x.visible).length,
    fixtures:window.stage.lightingEvidence().length,modelMeshes:window.stage.stage.model.children.length,
    terrain:env.userData.terrain,counts:env.userData.counts,environmentY:env.position.y,
    buildingParts:env.userData.buildingParts};
  window.capture=()=>{
    window.stage.stage.render();
    if(q.has('detail')){
      const g=presentation.surroundings.buildingParts.groups.find(g=>g.osm===q.get('detail'));
      if(!g) throw new Error('Missing Abelbau detail');
      const points=presentation.surroundings.buildings[g.buildingIndex].map(p=>
        editorPointToDortmund(p,presentation.frame,presentation.calibration.surroundingsAxes));
      const x=points.reduce((s,p)=>s+p[0],0)/points.length;
      const z=points.reduce((s,p)=>s+p[1],0)/points.length;
      const {camera,renderer,scene}=window.stage.stage;
      camera.position.set(x+75,65,z+95);camera.lookAt(x,5,z);camera.updateMatrixWorld(true);
      renderer.render(scene,camera);
      window.evidence.detail={osm:g.osm,camera:'diagnostic closeup, not gameplay camera',
        position:camera.position.toArray(),target:[x,5,z]};
    }
    return window.stage.stage.renderer.domElement.toDataURL('image/png');
  };
  window.ready=true;
}catch(e){window.failure=e.message;console.error(e)}
</script>`;
const mime = name => name.endsWith('.js')?'text/javascript':name.endsWith('.json')?
  'application/json':name.endsWith('.webp')?'image/webp':'application/octet-stream';
const server = createServer(async(req,res)=>{
  try {
    const name=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);
    if(name==='/'){res.writeHead(200,{'Content-Type':'text/html'});res.end(html);return;}
    let file,root;
    if(name==='/presentation.json'){
      res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});
      res.end(presentationBytes);return;
    }
    else if(name.startsWith('/static/')){file=path.join(staticDir,name.slice(8));root=staticDir;}
    else if(name.startsWith(base)){
      file=name===base+'manifest.json'?path.join(review,'manifest.json'):path.join(assets,name.slice(base.length));
      root=name===base+'manifest.json'?review:assets;
    }else if(installed && name.startsWith(`/stadion/model-assets/916/${manifest.assetVersion}/`)){
      // Exercise the actual application's registered, allowlisted asset endpoint.
      const response=await fetch(`http://127.0.0.1:5000${req.url}`);
      if(!response.ok)throw new Error(`Registered asset HTTP ${response.status}`);
      res.writeHead(200,{'Content-Type':mime(name)});res.end(Buffer.from(await response.arrayBuffer()));return;
    }else throw new Error('unknown path');
    if(!path.resolve(file).startsWith(root+path.sep))throw new Error('invalid path');
    res.writeHead(200,{'Content-Type':mime(file),'Cache-Control':'no-store'});
    res.end(await readFile(file));
  }catch(e){res.writeHead(404);res.end('Not found');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const output=path.join(review,roofStudy?(flatRoofs?'roof-baseline-views':'roof-views'):
  installed?'installed-views':'ansichten');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',args:[
  '--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader',
  '--disable-gpu-sandbox','--disable-accelerated-2d-canvas']});
const captures=[];
const selected=new Set(process.argv.slice(2).filter(x=>!x.startsWith('--')));
try {
  for(const [name,query] of [
    ['editor-dach-an',''],['editor-dach-aus','roof=0'],['draufsicht','az=0&el=80'],
    ['ticker-tag','ticker=1'],['ticker-ohne-dach','ticker=1&roof=0'],
    ['ticker-nacht-flutlicht','ticker=1&night=1&flood=1'],['sitzkamera','seat=1'],
    ['editor-nacht-flutlicht','night=1&flood=1'],
    ['abel-ost-tag','detail=way/73467119'],
    ['abel-west-tag','detail=way/73467122'],
    ['abel-ost-nacht','detail=way/73467119&night=1&flood=1'],
    ['abel-west-nacht','detail=way/73467122&night=1&flood=1'],
  ]){
    if(selected.size&&!selected.has(name))continue;
    const page=await browser.newPage({viewport:{width:1200,height:675}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/?${query}`);
    await page.waitForFunction(()=>window.ready||window.failure,{timeout:90000});
    const failure=await page.evaluate(()=>window.failure);
    if(failure||errors.length)throw new Error(JSON.stringify({name,failure,errors}));
    const evidence=await page.evaluate(()=>window.evidence);
    if(evidence.roofMeshes!==51||evidence.fixtures!==12||
       evidence.visibleRoof!==(query.includes('roof=0')?0:51)||
       !evidence.terrain?.groundCutout)
      throw new Error(JSON.stringify({name,evidence}));
    if(evidence.terrain.omitted.green.length||evidence.terrain.omitted.water.length)
      throw new Error(JSON.stringify({name,message:'omitted source ground features',evidence}));
    if(evidence.buildingParts?.groups.map(g=>g.components).join(',')!=='5,6')
      throw new Error(JSON.stringify({name,message:'Abelbau components missing',evidence}));
    const image=await page.evaluate(()=>window.capture());
    const imageBytes=Buffer.from(image.split(',')[1],'base64');
    await writeFile(path.join(output,name+'.png'),imageBytes);
    captures.push({name,query,evidence:await page.evaluate(()=>window.evidence),errors,
      imageSha256:createHash('sha256').update(imageBytes).digest('hex'),
      assetVersion:manifest.assetVersion,installed,flatRoofs,
      presentationSha256});
    await writeFile(path.join(output,'render-evidence.json'),JSON.stringify(captures,null,2));
    console.log('Captured',name,JSON.stringify(evidence));
    await page.close();
  }
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
