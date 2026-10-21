// Isolated, read-only fixture of the real editor template/JS and saved geometry.
// No authentication changes, session creation, or mutable application requests.
import {createServer} from 'node:http';
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const root=path.resolve(process.argv[2]);
if(!root)throw new Error('Fixture directory required');
const fixture=JSON.parse(await readFile(path.join(root,'editor-fixture.json'),'utf8'));
const html=await readFile(path.join(root,'editor-fixture.html'));
const server=createServer(async(req,res)=>{
  try{
    if(req.method!=='GET'){res.writeHead(405);res.end();return;}
    const pathname=new URL(req.url,'http://127.0.0.1').pathname;
    if(pathname==='/'){res.writeHead(200,{'Content-Type':'text/html'});res.end(html);return;}
    if(Object.hasOwn(fixture,pathname)){
      res.writeHead(200,{'Content-Type':'application/json'});
      res.end(JSON.stringify(fixture[pathname]));return;
    }
    if(!pathname.startsWith('/static/')&&!pathname.startsWith('/assets/')){
      res.writeHead(404);res.end();return;
    }
    const upstream=await fetch(`http://127.0.0.1:5000${req.url}`);
    res.writeHead(upstream.status,{'Content-Type':upstream.headers.get('content-type')||'application/octet-stream'});
    res.end(Buffer.from(await upstream.arrayBuffer()));
  }catch{res.writeHead(500);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',args:['--no-sandbox']});
try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`,{waitUntil:'networkidle'});
  await page.waitForFunction(()=>{
    const canvas=document.querySelector('#cvBlocks');
    return canvas?.width>0&&!document.querySelector('#stageStatus')?.textContent.includes('Laden');
  });
  await page.locator('#zoom2dIn').click();
  await page.locator('#zoom2dIn').click();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  if(errors.length)throw new Error(JSON.stringify(errors));
  await page.locator('#stage').screenshot({path:path.join(root,'editor-2d.png')});
  await writeFile(path.join(root,'editor-2d-evidence.json'),JSON.stringify({
    source:'Actual Django editor template, application editor.js, persisted geometry and effective standard design',
    fixture:true,readOnly:true,errors,zoom:await page.locator('#zoom2dValue').textContent(),
  },null,2));
  console.log('Actual 2D editor captured without application writes.');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
