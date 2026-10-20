// Render source packages through the existing application's WebGL renderer.
import {createServer} from 'node:http';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright-core';

const args=process.argv.slice(2);
const study=path.resolve(args[0]), fmi=Number(args[1]);
const installed=args.includes('--installed');
const selected=new Set(args.slice(2).filter(s=>s!=='--installed'));
const review=path.join(study,'osm-fresh'),assets=path.join(study,'source-export');
const staticDir=path.resolve('stadium_editor/static/stadium_editor');
const manifest=JSON.parse(await readFile(path.join(review,'manifest.json'),'utf8'));
if(manifest.clubFmiId!==fmi)throw new Error('Club identity mismatch');
const base=`/models/${fmi}/${manifest.assetVersion}/`;
const presentationFile=path.join(review,installed?'installed-presentation.json':'presentation.json');
const presentationSha256=createHash('sha256').update(await readFile(presentationFile)).digest('hex');
const roofCount=manifest.meshes.filter(m=>m.name.startsWith('DACH_')).length;
const html=`<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;background:#060b10;color:white}#stage{width:1200px;height:675px;position:relative}
</style><div id="stage"></div><script type="module">
import {mountUnityStadium} from '/static/unity_stadium_scene.js';
const q=new URLSearchParams(location.search);
try{
 const {presentation}=await(await fetch('/presentation.json')).json();
 window.stage=await mountUnityStadium({element:document.getElementById('stage'),presentation,
   tickerPreview:q.get('ticker')==='1'});
 await window.stage.update({day:q.get('night')!=='1',floodlight:q.get('flood')==='1',
   roofVisible:q.get('roof')!=='0',camera:q.get('seat')==='1'?'seat':'orbit',
   orbit:{azimuth:Number(q.get('az')||55),elevation:Number(q.get('el')||37)}});
 const roof=window.stage.stage.model.children.filter(x=>x.name?.startsWith('SOURCE_DACH_'));
 const env=window.stage.stage.scene.getObjectByName('EDITOR_SURROUNDINGS_3D');
 window.evidence={roofMeshes:roof.length,visibleRoof:roof.filter(x=>x.visible).length,
 fixtures:window.stage.lightingEvidence().length,modelMeshes:window.stage.stage.model.children.length,
 terrain:env.userData.terrain,counts:env.userData.counts,environmentY:env.position.y};
 window.ready=true;
}catch(e){window.failure=e.message;console.error(e)}
</script>`;
const mime=n=>n.endsWith('.js')?'text/javascript':n.endsWith('.json')?'application/json':
 n.endsWith('.webp')?'image/webp':'application/octet-stream';
const server=createServer(async(req,res)=>{
 try{
  const n=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);
  if(n==='/'){res.writeHead(200,{'Content-Type':'text/html'});res.end(html);return;}
  let file,root;
  if(n==='/presentation.json'){file=presentationFile;root=review;}
  else if(n.startsWith('/static/')){file=path.join(staticDir,n.slice(8));root=staticDir;}
  else if(n.startsWith(base)){
   file=n===base+'manifest.json'?path.join(review,'manifest.json'):path.join(assets,n.slice(base.length));
   root=n===base+'manifest.json'?review:assets;
  }else if(installed&&n.startsWith(`/stadion/model-assets/${fmi}/${manifest.assetVersion}/`)){
   const response=await fetch(`http://127.0.0.1:5000${req.url}`);
   if(!response.ok)throw new Error(`Registered asset HTTP ${response.status}`);
   res.writeHead(200,{'Content-Type':mime(n)});res.end(Buffer.from(await response.arrayBuffer()));return;
  }else throw new Error('Unknown path');
  if(!path.resolve(file).startsWith(root+path.sep))throw new Error('Invalid path');
  res.writeHead(200,{'Content-Type':mime(file),'Cache-Control':'no-store'});res.end(await readFile(file));
 }catch(e){res.writeHead(404);res.end('Not found');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const output=path.join(review,installed?'installed-views':'ansichten');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',args:[
 '--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader',
 '--disable-gpu-sandbox','--disable-accelerated-2d-canvas']});
const captures=[];
try{
 for(const [name,query] of [
  ['editor-dach-an',''],['editor-dach-aus','roof=0'],['draufsicht','az=0&el=80'],
  ['ticker-tag','ticker=1'],['ticker-ohne-dach','ticker=1&roof=0'],
  ['ticker-nacht-flutlicht','ticker=1&night=1&flood=1'],['sitzkamera','seat=1'],
 ]){
  if(selected.size&&!selected.has(name))continue;
  const page=await browser.newPage({viewport:{width:1200,height:675}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/?${query}`);
  await page.waitForFunction(()=>window.ready||window.failure,null,{timeout:120000});
  const failure=await page.evaluate(()=>window.failure);
  if(failure||errors.length)throw new Error(JSON.stringify({name,failure,errors}));
  const evidence=await page.evaluate(()=>window.evidence);
  if(evidence.roofMeshes!==roofCount||evidence.fixtures!==manifest.fixtures.length||
     evidence.visibleRoof!==(query.includes('roof=0')?0:roofCount)||!evidence.terrain?.groundCutout)
    throw new Error(JSON.stringify({name,evidence}));
  if(evidence.terrain.omitted.green.length||evidence.terrain.omitted.water.length)
    throw new Error(JSON.stringify({name,message:'Omitted source ground features',evidence}));
  const image=await page.evaluate(()=>{
   window.stage.stage.render();return window.stage.stage.renderer.domElement.toDataURL('image/png');
  });
  await writeFile(path.join(output,name+'.png'),Buffer.from(image.split(',')[1],'base64'));
  captures.push({name,query,evidence,errors,assetVersion:manifest.assetVersion,installed,presentationSha256});
  await writeFile(path.join(output,'render-evidence.json'),JSON.stringify(captures,null,2));
  console.log('Captured',name,JSON.stringify(evidence));await page.close();
 }
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
