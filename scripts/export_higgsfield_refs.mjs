// Asset-only export using the real study renderer. No app route/auth/data edits.
import fs from 'node:fs';
import {chromium} from 'playwright-core';

const out='attached_assets/higgsfield_stadium_pack';
fs.mkdirSync(out,{recursive:true});
const base=`https://${process.env.REPLIT_DEV_DOMAIN}`;
const source=JSON.parse(fs.readFileSync('stadium_editor/blueprints/v2/elversberg_v2.json','utf8'));
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
  const page=await browser.newPage({viewport:{width:1880,height:940}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(`${base}/static/game/css/stadium_study.css?v=3`,{waitUntil:'domcontentloaded'});
  await page.setContent(`<!doctype html><link rel="icon" href="data:,"><script type="importmap">{"imports":{"three":"${base}/static/stadium_editor/stage/vendor/three.module.js","three/addons/":"${base}/static/stadium_editor/stage/vendor/addons/"}}</script><div id="host" style="width:1880px;height:940px;position:relative"></div>`);
  for(const club of ['dortmund','elversberg']) {
    const data=await page.evaluate(async ({base,source,club})=>{
      const THREE=await import('three');
      const {mountStudyModel}=await import(`${base}/static/stadium_editor/study_models.js?v=higgsfield-1`);
      const {applyStudyCamera,projectStudy}=await import(`${base}/static/stadium_editor/study_camera.js?v=1`);
      const {createStudyLighting}=await import(`${base}/static/stadium_editor/study_lighting.js?v=3`);
      const host=document.getElementById('host');
      const handle=await mountStudyModel({host,club,source,concept:'cutaway'});
      const lighting=createStudyLighting(handle,null);
      lighting.setState(false,false,false);
      const stage=handle.stage;
      applyStudyCamera(stage.camera,'cutaway',1880,940);
      stage.render();
      const reference=handle.canvas.toDataURL('image/png');
      const corners=[[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34]]
        .map(([x,y])=>projectStudy(stage.camera,1880,940,x,y));
      const saved=[],replacements=new Set(),background=stage.sceneRoot.background;
      // A rendered silhouette is a geometric reference, not an API inpaint
      // selection. The separate pitch mask protects exact game-field pixels.
      stage.sceneRoot.background=new THREE.Color('#000000');
      stage.sceneRoot.traverse(object=>{
        if(!object.isMesh)return;
        saved.push({object,material:object.material,visible:object.visible,instanceColor:object.instanceColor});
        if(object.userData.studyPitch) {object.visible=false;return;}
        const materials=Array.isArray(object.material)?object.material:[object.material];
        object.material=materials.map(m=>{
          const white=new THREE.MeshBasicMaterial({color:'#ffffff',side:THREE.DoubleSide,
            clippingPlanes:m.clippingPlanes});
          replacements.add(white);return white;
        });
        if(object.isInstancedMesh)object.instanceColor=null;
      });
      stage.render();
      const silhouette=handle.canvas.toDataURL('image/png');
      saved.forEach(({object,material,visible,instanceColor})=>{
        object.material=material;object.visible=visible;
        if(object.isInstancedMesh)object.instanceColor=instanceColor;
      });
      replacements.forEach(material=>material.dispose());
      stage.sceneRoot.background=background;
      stage.sceneRoot.traverse(object=>{
        if(object.isMesh&&!stage.pitchMaterials.has(object.material))object.visible=false;
      });
      stage.render();
      const cleanFrame=handle.canvas.toDataURL('image/png');
      lighting.dispose();handle.dispose();
      return {reference,silhouette,cleanFrame,corners,
        projectionMatrix:stage.camera.projectionMatrix.toArray()};
    },{base,source,club});
    const directory=`${out}/${club}`;fs.mkdirSync(directory,{recursive:true});
    for(const [key,name] of [['reference','01_camera_reference'],['silhouette','02_stadium_silhouette'],['cleanFrame','03_empty_site_camera']])
      fs.writeFileSync(`${directory}/${name}.png`,Buffer.from(data[key].split(',')[1],'base64'));
    fs.writeFileSync(`${directory}/camera.json`,JSON.stringify({
      format:[1880,940],concept:'cutaway',height:98,distance:76,tilt:44,
      pitch:[105,68],corners:data.corners,projectionMatrix:data.projectionMatrix,
      note:'Grounded in the real study renderer. Map-north to mesh orientation is not independently calibrated.',
    },null,2));
  }
  if(errors.length)throw new Error(errors.join('\n'));
  console.log('Exact 1880×940 camera, stadium silhouette and empty-site references exported for both clubs.');
}finally {await browser.close();}
