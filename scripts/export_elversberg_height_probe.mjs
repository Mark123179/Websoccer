// Isolated ID/depth-buffer visibility experiment. Never serves or edits app data.
import fs from 'node:fs';
import {chromium} from 'playwright-core';

const out='generated-artifacts/elversberg-height-visibility';
const inputs=JSON.parse(fs.readFileSync(`${out}/height_inputs.json`,'utf8'));
const source=JSON.parse(fs.readFileSync('stadium_editor/blueprints/v2/elversberg_v2.json','utf8'));
const baseline=JSON.parse(fs.readFileSync('generated-artifacts/stadium-main-stand-back-probe/verification.json','utf8'));
const base=`https://${process.env.REPLIT_DEV_DOMAIN}`;
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
  const page=await browser.newPage({viewport:{width:1880,height:940}});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`${base}/static/game/css/stadium_study.css?v=3`);
  await page.setContent(`<script type="importmap">{"imports":{"three":"${base}/static/stadium_editor/stage/vendor/three.module.js","three/addons/":"${base}/static/stadium_editor/stage/vendor/addons/"}}</script><div id="host" style="width:1880px;height:940px"></div>`);
  const result=await page.evaluate(async({base,inputs,source,baseline})=>{
    const THREE=await import('three');
    const {mountStudyModel}=await import(`${base}/static/stadium_editor/study_models.js?v=height-probe`);
    const {projectStudy}=await import(`${base}/static/stadium_editor/study_camera.js?v=1`);
    const rotate=p=>[-p[0],-p[1],...p.slice(2)];
    source.blocks.forEach(b=>b.quad=b.quad.map(rotate));
    source.outline=source.outline.map(rotate);
    source.roof.segments.forEach(b=>b.quad=b.quad.map(rotate));
    source.mainStand='NORD';source.farStand='SUED';
    const h=await mountStudyModel({host:document.getElementById('host'),club:'elversberg',source,concept:'cutaway'});
    const {stage}=h, camera=stage.camera, c=inputs.camera;
    camera.position.fromArray(c.position);
    camera.matrixWorldInverse.fromArray(c.worldInverse);
    camera.matrixWorld.copy(camera.matrixWorldInverse).invert();
    camera.matrixWorld.decompose(camera.position,camera.quaternion,camera.scale);
    camera.projectionMatrix.fromArray(c.projection);
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    camera.updateMatrixWorld(true);
    const corners=[[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34]]
      .map(([x,z])=>projectStudy(camera,1880,940,x,z));
    if(Math.max(...corners.flatMap((p,i)=>['x','y'].map(k=>Math.abs(p[k]-c.corners[i][k]))))>1e-9)
      throw new Error('Approved field corners changed');
    if(Math.max(...camera.matrixWorldInverse.elements.map((v,i)=>Math.abs(v-c.worldInverse[i])))>1e-12)
      throw new Error('Approved view matrix changed');
    const renderer=stage.renderer;
    renderer.toneMapping=THREE.NoToneMapping;
    renderer.setClearColor(0,1);
    stage.sceneRoot.background=null;
    // Preserve real instancing, clipping, material side, and visibility.
    stage.sceneRoot.traverse(o=>{
      if(!o.isMesh)return;
      const replace=m=>new THREE.MeshBasicMaterial({color:0xffff00,side:m.side,
        visible:m.visible,clippingPlanes:m.clippingPlanes,clipIntersection:m.clipIntersection});
      o.material=Array.isArray(o.material)?o.material.map(replace):replace(o.material);
    });
    const stadiumChildren=stage.sceneRoot.children.map(object=>({object,visible:object.visible}));
    const group=new THREE.Group();stage.sceneRoot.add(group);
    const target=new THREE.WebGLRenderTarget(1880,940,{depthBuffer:true});
    target.texture.colorSpace=THREE.NoColorSpace;
    function mat(code){
      return new THREE.MeshBasicMaterial({color:new THREE.Color().setRGB(
        (code&255)/255,((code>>8)&255)/255,((code>>16)&255)/255,THREE.LinearSRGBColorSpace),
        side:THREE.DoubleSide,toneMapped:false});
    }
    const objects=inputs.objects.filter(o=>o.matched);
    const meshes=[];
    function add(o,height,index){
      const shape=new THREE.Shape(o.polygon.map(([x,z])=>new THREE.Vector2(x,-z)));
      const geometry=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false,steps:1});
      geometry.rotateX(-Math.PI/2);
      // Code 0=empty, 65535=stadium, 2i+1=roof caps, 2i+2=facades.
      const mesh=new THREE.Mesh(geometry,[mat(index*2+1),mat(index*2+2)]);
      group.add(mesh);meshes.push(mesh);return mesh;
    }
    objects.forEach((o,i)=>add(o,o.height_envelope_m,i));
    function capture(name,selected=null,stadium=true){
      for(const saved of stadiumChildren)saved.object.visible=stadium&&saved.visible;
      meshes.forEach((m,i)=>m.visible=selected===null||selected.includes(i));
      // Roof-state visibility lives below stadium roots, not overwritten here.
      renderer.setRenderTarget(target);renderer.render(stage.sceneRoot,camera);
      const pixels=new Uint8Array(1880*940*4);
      renderer.readRenderTargetPixels(target,0,0,1880,940,pixels);
      renderer.setRenderTarget(null);
      let binary='';for(let i=0;i<pixels.length;i+=32768)
        binary+=String.fromCharCode(...pixels.subarray(i,i+32768));
      return {name,rgbaBottomUp:btoa(binary)};
    }
    const captures=[];
    for(const roof of [true,false]){
      h.setRoof(roof);
      const state=roof?'roof':'no_roof';
      captures.push(capture(`all_${state}`));
      for(const id of [30887518,53864244]){
        const index=objects.findIndex(o=>o.osm_id===id);
        if(index<0)throw new Error(`Missing verified landmark ${id}`);
        captures.push(capture(`${id}_stadium_${state}`,[index]));
        captures.push(capture(`${id}_alone_${state}`,[index],false));
      }
      // Lidl is expressly a sensitivity sweep, NEVER a measured height.
      const lidl=inputs.objects.find(o=>o.osm_id===53864241);
      const index=objects.length;
      for(const height of [3,6,9,12]){
        const mesh=add(lidl,height,index);
        captures.push(capture(`lidl_h${height}_${state}`,null,true));
        group.remove(mesh);meshes.pop();mesh.geometry.dispose();
        mesh.material.forEach(m=>m.dispose());
      }
      // Stadium-only depth occupancy for parity against fresh silhouette.
      captures.push(capture(`stadium_${state}`,[],true));
    }
    target.dispose();h.dispose();
    return {captures,objects:objects.map(o=>o.osm_id),camera:c,
      fieldCorners:corners,renderer:'Chromium ANGLE SwiftShader; non-MSAA ID buffer',
      baselineStates:baseline.states.filter(s=>s.club==='elversberg'&&s.variant==='day')
        .map(s=>({roof:s.roof,visibleRoofMeshes:s.visibleRoofMeshes}))};
  },{base,inputs,source,baseline});
  if(errors.length)throw new Error(errors.join('\n'));
  for(const c of result.captures){
    fs.writeFileSync(`${out}/${c.name}.rgba`,Buffer.from(c.rgbaBottomUp,'base64'));
    delete c.rgbaBottomUp;
  }
  fs.writeFileSync(`${out}/render_verification.json`,JSON.stringify(result,null,2));
  console.log(`Captured ${result.captures.length} depth-tested ID passes; field corners unchanged.`);
}finally{await browser.close();}
