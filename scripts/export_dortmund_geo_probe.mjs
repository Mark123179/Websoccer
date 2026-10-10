// Read-only, isolated renders of the existing model. No app or game writes.
import fs from 'node:fs';
import {chromium} from 'playwright-core';

const output='generated-artifacts/dortmund-site-study';
fs.mkdirSync(output,{recursive:true});
const base=`https://${process.env.REPLIT_DEV_DOMAIN}`;
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
  const page=await browser.newPage({viewport:{width:1880,height:940}});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`${base}/static/game/css/stadium_study.css?v=3`);
  await page.setContent(`<script type="importmap">{"imports":{"three":"${base}/static/stadium_editor/stage/vendor/three.module.js","three/addons/":"${base}/static/stadium_editor/stage/vendor/addons/"}}</script><div id="host" style="width:1880px;height:940px"></div>`);
  const result=await page.evaluate(async ({base})=>{
    const THREE=await import('three');
    const {mountStudyModel}=await import(`${base}/static/stadium_editor/study_models.js?v=geo-probe`);
    const {applyStudyCamera,projectStudy}=await import(`${base}/static/stadium_editor/study_camera.js?v=1`);
    const {createStudyLighting}=await import(`${base}/static/stadium_editor/study_lighting.js?v=3`);
    const handle=await mountStudyModel({host:document.getElementById('host'),club:'dortmund',concept:'cutaway'});
    const lighting=createStudyLighting(handle,null);
    lighting.setState(false,false,false);
    const stage=handle.stage;
    applyStudyCamera(stage.camera,'cutaway',1880,940);
    stage.render();
    const cutaway=handle.canvas.toDataURL('image/png');
    const metadata={
      format:[1880,940],position:stage.camera.position.toArray(),
      projection:stage.camera.projectionMatrix.toArray(),
      worldInverse:stage.camera.matrixWorldInverse.toArray(),
      corners:[[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34]]
        .map(([x,y])=>projectStudy(stage.camera,1880,940,x,y)),
    };
    // An overhead source audit, not a new game-camera preset.
    stage.sceneRoot.traverse(object=>{
      for(const material of Array.isArray(object.material)?object.material:[object.material]){
        if(material)material.clippingPlanes=[];
      }
    });
    stage.renderer.setSize(1024,1024,false);
    const top=new THREE.OrthographicCamera(-145,145,145,-145,1,2000);
    top.position.set(0,500,0);top.up.set(0,0,-1);top.lookAt(0,0,0);top.updateMatrixWorld(true);
    stage.renderer.render(stage.sceneRoot,top);
    const overhead=handle.canvas.toDataURL('image/png');
    handle.setRoof(false);
    stage.renderer.render(stage.sceneRoot,top);
    const overheadNoRoof=handle.canvas.toDataURL('image/png');
    lighting.dispose();handle.dispose();
    return {cutaway,overhead,overheadNoRoof,metadata};
  },{base});
  if(errors.length)throw new Error(errors.join('\n'));
  for(const name of ['cutaway','overhead','overheadNoRoof'])
    fs.writeFileSync(`${output}/model_${name}.png`,Buffer.from(result[name].split(',')[1],'base64'));
  fs.writeFileSync(`${output}/camera_exact.json`,JSON.stringify(result.metadata,null,2));
  console.log('Source-model overhead audit and exact camera matrices exported.');
}finally{await browser.close();}
