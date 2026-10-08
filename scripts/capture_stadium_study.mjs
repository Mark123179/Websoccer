import fs from 'node:fs';
import {chromium} from 'playwright-core';

const dir=process.env.CAPTURE_DIR || 'docs/stadium/field-study-review';
fs.mkdirSync(dir,{recursive:true});
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const errors=[],failures=[],captures=[];
try {
  const base=`https://${process.env.REPLIT_DEV_DOMAIN}`;
  const context=await browser.newContext({viewport:{width:1560,height:1100}});
  await context.addCookies([{...JSON.parse(fs.readFileSync(process.env.SESSION_FILE)),
    url:base,httpOnly:true,secure:true,sameSite:'Lax'}]);
  const page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  page.on('response',r=>{if(r.status()>=400)failures.push([r.status(),r.url().split('?')[0]]);});
  await page.goto(base+'/live/stadium-study/',{waitUntil:'domcontentloaded',timeout:90000});
  if(!new URL(page.url()).pathname.startsWith('/live/stadium-study/'))
    throw new Error('Die kurzfristige Aufnahme-Sitzung ist abgelaufen.');
  await page.waitForFunction(()=>document.body.dataset.studyReady,{timeout:90000});
  if(await page.getAttribute('body','data-study-ready')!=='2')
    throw new Error(await page.locator('.ss-stage-status').allTextContents());
  await page.locator('#study-pause').click();
  async function capture(name) {
    await page.waitForTimeout(180);
    for(const club of ['dortmund','elversberg']) {
      await page.locator(`#study-${club}`).screenshot({path:`${dir}/${name}-${club}.png`});
    }
    captures.push({name,...await page.evaluate(()=>({
      parity:Number(document.body.dataset.fieldParity),
      corners:['dortmund','elversberg'].map(club=>JSON.parse(document.querySelector(`#study-${club}`).dataset.fieldCorners)),
      lightCounts:['dortmund','elversberg'].map(club=>Number(document.querySelector(`#study-${club}`).dataset.fixtureCount)),
      overflow:document.documentElement.scrollWidth>innerWidth,
    }))});
  }
  if(process.env.CAPTURE_PRESENTATION==='1') {
    await capture('perspective-day');
    await page.locator('#study-concept').selectOption('cutaway');
    await capture('cutaway-day');
    for(const [id,file] of [['reference','camera-reference.png'],['mask','stadium-mask.png']]) {
      const pending=page.waitForEvent('download');
      await page.locator(`#study-export-${id}`).click();
      await (await pending).saveAs(`${dir}/${file}`);
    }
    fs.writeFileSync(`${dir}/presentation-check.json`,JSON.stringify({errors,failures,captures},null,2));
    if(errors.length||failures.length)throw new Error(JSON.stringify({errors,failures}));
    console.log('Both final camera directions and fixed-size reference/mask captured.');
  } else if(process.env.CAPTURE_QUICK==='1') {
    await page.locator('#study-concept').selectOption('cutaway');
    await capture('cutaway-day');
    await page.locator('#study-night').check();
    await capture('cutaway-night');
    await page.locator('#study-lights').check();
    await capture('declared-lamp-diagnostics');
    await page.locator('#study-lights').uncheck();
    await page.locator('#study-floodlight').uncheck();
    await capture('night-floodlight-off');
    fs.writeFileSync(`${dir}/targeted-check.json`,JSON.stringify({errors,failures,captures},null,2));
    if(errors.length||failures.length)throw new Error(JSON.stringify({errors,failures}));
    console.log(JSON.stringify({errors,failures,captures:captures.map(c=>({name:c.name,parity:c.parity,lightCounts:c.lightCounts}))}));
    await page.screenshot({path:`${dir}/page-preview.png`,fullPage:true});
  } else {
  await capture('perspective-day');
  await page.locator('#study-concept').selectOption('cutaway');
  await capture('cutaway-day');
  await page.locator('#study-roof').uncheck();
  await capture('cutaway-roof-off');
  await page.locator('#study-roof').check();
  await page.locator('#study-night').check();
  await capture('cutaway-night');
  await page.locator('#study-lights').check();
  await capture('declared-lamp-diagnostics');
  await page.locator('#study-lights').uncheck();
  await page.locator('#study-floodlight').uncheck();
  await capture('night-floodlight-off');
  await page.locator('#study-floodlight').check();
  // Actual downloads confirm the export buttons, without touching game data.
  for(const [id,file] of [['reference','camera-reference.png'],['mask','stadium-mask.png']]) {
    const pending=page.waitForEvent('download');
    await page.locator(`#study-export-${id}`).click();
    const download=await pending;await download.saveAs(`${dir}/${file}`);
  }
  await page.locator('#study-night').uncheck();
  await page.setViewportSize({width:390,height:850});
  await capture('mobile-cutaway-day');
  fs.writeFileSync(`${dir}/report.json`,JSON.stringify({errors,failures,captures,
    note:'Real authenticated software-WebGL captures; 2D figures are a declared demo, not simulation.'},null,2));
  if(errors.length||failures.length||captures.some(c=>c.parity>1e-9||c.overflow))
    throw new Error(JSON.stringify({errors,failures,captures}));
  console.log(JSON.stringify({errors,failures,captures},null,2));
  }
}finally {await browser.close();}
