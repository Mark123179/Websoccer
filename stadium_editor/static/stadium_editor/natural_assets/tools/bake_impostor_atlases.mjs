import {createServer} from 'node:http';
import {createReadStream,existsSync,mkdirSync,readdirSync,unlinkSync,writeFileSync} from 'node:fs';
import {basename,extname,join,normalize,resolve,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';

const require=createRequire(import.meta.url);
const {chromium}=require('playwright-core');
const here=dirname(fileURLToPath(import.meta.url));
const staticRoot=resolve(here,'../..');
const output=resolve(here,'../atlases');
mkdirSync(output,{recursive:true});
function dirname(path){return path.slice(0,path.lastIndexOf('/'));}
const mime={'.js':'text/javascript','.html':'text/html','.json':'application/json','.gltf':'model/gltf+json',
  '.bin':'application/octet-stream','.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg','.jpeg':'image/jpeg'};
const server=createServer((request,response)=>{
  const pathname=decodeURIComponent(new URL(request.url,'http://localhost').pathname);
  if(request.method==='POST'&&pathname.startsWith('/__save/')){
    const name=basename(pathname.slice('/__save/'.length));
    if(!/^[a-z0-9_.-]+$/i.test(name)){response.writeHead(400).end();return;}
    const chunks=[];
    request.on('data',chunk=>chunks.push(chunk));
    request.on('end',()=>{
      const destination=resolve(output,name);
      if(!destination.startsWith(output+sep)){response.writeHead(400).end();return;}
      writeFileSync(destination,Buffer.concat(chunks));
      response.writeHead(204).end();
    });
    return;
  }
  const relative=normalize(pathname).replace(/^([/\\])+/, '');
  const path=resolve(staticRoot,relative);
  if(!path.startsWith(staticRoot+sep)||!existsSync(path)){response.writeHead(404).end();return;}
  response.writeHead(200,{'content-type':mime[extname(path)]||'application/octet-stream',
    'access-control-allow-origin':'*','cache-control':'no-store'});
  createReadStream(path).pipe(response);
});
await new Promise(resolveServer=>server.listen(4179,'127.0.0.1',resolveServer));
let browser;
try{
  browser=await chromium.launch({headless:true,executablePath:'/repl/tools/bin/chromium',
    args:['--no-sandbox','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle',
      '--use-angle=swiftshader','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:700,height:520}});
  page.on('console',message=>{if(message.type()==='error')console.error(message.text());});
  page.on('pageerror',error=>console.error(error.stack||error));
  page.on('requestfailed',request=>{
    if(request.failure()?.errorText!=='net::ERR_ABORTED')
      console.error('REQUEST FAILED',request.url(),request.failure()?.errorText);
  });
  page.on('response',response=>{
    if(response.status()>=400&&!response.url().endsWith('/favicon.ico'))
      console.error('HTTP',response.status(),response.url());
  });
  await page.goto('http://127.0.0.1:4179/natural_assets/tools/bake.html');
  await page.waitForFunction(()=>window.atlasBakeDone||window.atlasBakeError,null,{timeout:300000});
  const failure=await page.evaluate(()=>window.atlasBakeError||null);
  if(failure)throw new Error(failure);
  console.log(await page.evaluate(()=>document.body.dataset.state));
  for(const file of readdirSync(output)){
    if(/^.+_2048\.png$/i.test(file))unlinkSync(join(output,file));
  }
}finally{
  await browser?.close();
  server.close();
}
