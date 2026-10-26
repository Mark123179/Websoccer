/** Actual common 3D pitch and approved study camera; no app/data modifications. */
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright-core';

const out='generated-artifacts/grass-study';
const club=process.argv.includes('--elversberg')?'elversberg':'dortmund';
const manifest=JSON.parse(fs.readFileSync(`${out}/manifest.json`));
const source=JSON.parse(fs.readFileSync(`${out}/elversberg-scene.json`));
const fixtures=JSON.parse(fs.readFileSync('stadium_editor/static/stadium_editor/study_assets/dortmund_lights.json'));
// This is the selected, 75% compromise, not a new automatic stadium fit.
const camera={focal:1337.4782524186542,cx:940,cy:681.3221103379157,
  position:[0,98,110],tilt:44,format:[1880,940]};
const base=`https://${process.env.REPLIT_DEV_DOMAIN}`;
if(!process.env.REPLIT_DEV_DOMAIN)throw new Error('Dev host required.');
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
  const page=await browser.newPage({viewport:{width:1880,height:940}});
  page.setDefaultTimeout(180000);
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  await page.route('**/favicon.ico',r=>r.fulfill({status:204}));
  await page.route('**/__grass_study__/textures/*',r=>{
    const id=new URL(r.request().url()).pathname.split('/').at(-1);
    if(!/^[A-D][1-4]\.webp$/.test(id))return r.abort();
    return r.fulfill({status:200,contentType:'image/webp',body:fs.readFileSync(`${out}/textures/${id}`)});
  });
  await page.goto(`${base}/static/game/css/stadium_study.css?v=7`);
  await page.setContent(`<!doctype html><style>body{margin:0}#host{position:relative;width:1880px;height:940px}</style>
    <script type="importmap">{"imports":{"three":"${base}/static/stadium_editor/stage/vendor/three.module.js",
    "three/addons/":"${base}/static/stadium_editor/stage/vendor/addons/"}}</script><div id="host"></div>`);
  await page.evaluate(async({base,source,fixtures,club,camera})=>{
    // Fixed offline capture surface; no interactive-frame behaviour is changed.
    window.requestAnimationFrame=()=>0;
    window.ResizeObserver=class{observe(){}disconnect(){}unobserve(){}};
    const {mountStudyModel}=await import(`${base}/static/stadium_editor/study_models.js?v=grass-study`);
    const {createStudyLighting}=await import(`${base}/static/stadium_editor/study_lighting.js?v=grass-study`);
    const {mountGrassSurfaceStudy}=await import(`${base}/static/stadium_editor/grass_surface_study.js?v=1`);
    const {projectStudy}=await import(`${base}/static/stadium_editor/study_camera.js?v=3`);
    const handle=await mountStudyModel({host:document.getElementById('host'),club,source,concept:'cutaway'});
    // Elversberg's production adapter owns additional preview lights. The
    // isolated comparison uses only the same explicit study daylight for both.
    handle.stage.sceneRoot.traverse(object=>{if(object.isLight)object.intensity=0;});
    const lighting=createStudyLighting(handle,club==='dortmund'?fixtures:null);
    if(club==='dortmund') {
      handle.model.rotation.y+=Math.PI;
    }
    handle.setRoof(true);
    lighting.setState(false,false,false);
    const stage=handle.stage;
    stage.renderer.setPixelRatio(1);
    stage.renderer.setSize(1880,940,false);
    stage.camera.position.fromArray(camera.position);
    const tilt=camera.tilt*Math.PI/180;
    stage.camera.lookAt(0,98-Math.sin(tilt),110-Math.cos(tilt));
    stage.camera.updateMatrixWorld(true);
    stage.camera.projectionMatrix.makePerspective(-camera.cx/camera.focal,
      (1880-camera.cx)/camera.focal,camera.cy/camera.focal,-(940-camera.cy)/camera.focal,1,6000);
    stage.camera.projectionMatrixInverse.copy(stage.camera.projectionMatrix).invert();
    const coordinates=[[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34],[0,0],[16,10]];
    const corners=()=>coordinates.map(([x,y])=>projectStudy(stage.camera,1880,940,x,y));
    const baseline=corners();
    const positionDigest=()=>{
      const values=[];
      stage.sceneRoot.traverse(mesh=>{
        if(mesh.userData.studyPitch&&mesh.geometry)
          values.push(Array.from(mesh.geometry.getAttribute('position').array));
      });
      return JSON.stringify(values);
    };
    window.capture={handle,lighting,stage,mountGrassSurfaceStudy,corners,baseline,
      positionDigest,positions:positionDigest(),projection:stage.camera.projectionMatrix.toArray(),
      active:null,base,proof:[]};
  },{base,source,fixtures,club,camera});
  async function render(id,night=false) {
    const data=await page.evaluate(async({id,night})=>{
      const c=window.capture;
      c.active?.dispose();c.active=null;
      if(id!=='bestand')c.active=await c.mountGrassSurfaceStudy(c.stage,
        `${c.base}/__grass_study__/textures/${id}.webp`);
      c.lighting.setState(night,false,night);
      if(night)c.lighting.inspectAlignment();
      if(JSON.stringify(c.corners())!==JSON.stringify(c.baseline)||
         JSON.stringify(c.stage.camera.projectionMatrix.toArray())!==JSON.stringify(c.projection)||
         c.positionDigest()!==c.positions)throw new Error('Pitch geometry/projection changed.');
      c.stage.render();
      c.stage.renderer.getContext().finish();
      const bytes=c.handle.canvas.toDataURL('image/png');
      const stats={id,night,corners:c.corners(),surfaceMeshes:c.active?.targets.length||0,
        verifiedFixtures:c.lighting.verifiedCount,activeLights:c.lighting.sources.filter(s=>s.intensity>0).length,
        shaderErrors:c.stage.renderer.info.programs?.filter(p=>p.diagnostics?.runnable===false).length||0};
      if(stats.shaderErrors)throw new Error('Grass shader failed.');
      return {bytes,stats};
    },{id,night});
    const filename=club==='elversberg'?`${id}-elversberg.png`:`${id}-${night?'night':'day'}.png`;
    const bytes=Buffer.from(data.bytes.split(',')[1],'base64');
    fs.writeFileSync(`${out}/renders/${filename}`,bytes);
    data.stats.sha256=createHash('sha256').update(bytes).digest('hex');
    data.stats.file=filename;
    console.log(filename,bytes.length,'bytes',data.stats.surfaceMeshes,'surfaces');
    return data.stats;
  }
  const states=[];
  if(club==='dortmund'){
    states.push(await render('bestand'));
    for(const variant of manifest.variants)states.push(await render(variant.id));
    states.push(await render('A1',true));
    states.push(await render('C2',true));
  }else{
    states.push(await render('A1'));
    states.push(await render('C2'));
  }
  if(errors.length)throw new Error(errors.join('\n'));
  fs.writeFileSync(`${out}/verification-${club}.json`,JSON.stringify({
    club,camera,states,errors,geometryChanged:false,
  },null,2));
}finally{await browser.close();}
