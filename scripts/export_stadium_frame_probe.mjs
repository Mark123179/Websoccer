// Isolated framing study. Never changes app camera presets or club data.
import fs from 'node:fs';
import {chromium} from 'playwright-core';

const mode=process.argv.includes('--middle')?'middle':'full';
const mainStandBack=process.argv.includes('--main-stand-back');
if(mainStandBack && mode!=='middle')throw new Error('Main-stand-back requires the approved --middle camera.');
const output=mainStandBack?'generated-artifacts/stadium-main-stand-back-probe':
  mode==='middle'?'generated-artifacts/stadium-middle-probe':'generated-artifacts/stadium-frame-probe';
const approved=mainStandBack?JSON.parse(fs.readFileSync(
  'generated-artifacts/stadium-middle-probe/verification.json','utf8')).states[0]:null;
fs.mkdirSync(output,{recursive:true});
const source=JSON.parse(fs.readFileSync('stadium_editor/blueprints/v2/elversberg_v2.json','utf8'));
const base=`https://${process.env.REPLIT_DEV_DOMAIN}`;
const browser=await chromium.launch({executablePath:'/repl/tools/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
  const page=await browser.newPage({viewport:{width:1880,height:940}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(`${base}/static/game/css/stadium_study.css?v=3`);
  await page.setContent(`<script type="importmap">{"imports":{"three":"${base}/static/stadium_editor/stage/vendor/three.module.js","three/addons/":"${base}/static/stadium_editor/stage/vendor/addons/"}}</script><div id="host" style="width:1880px;height:940px;position:relative"></div>`);
  const result=await page.evaluate(async ({base,source,mode,mainStandBack,approved})=>{
    const THREE=await import('three');
    const {mountStudyModel}=await import(`${base}/static/stadium_editor/study_models.js?v=frame-probe`);
    const {applyStudyCamera,projectStudy,studyPreset}=await import(`${base}/static/stadium_editor/study_camera.js?v=1`);
    const {createStudyLighting}=await import(`${base}/static/stadium_editor/study_lighting.js?v=3`);
    const width=1880,height=940,margin=32;
    const original=studyPreset('cutaway');
    const corners=[[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34]];
    const states=[];
    let fitted=null;

    // Measure only indexed, visible geometry after its real clipping planes.
    // Crossings at a cut plane count too; not just surviving source vertices.
    function measure(stage,store=null){
      stage.sceneRoot.updateMatrixWorld(true);
      const view=stage.camera.matrixWorldInverse.elements;
      let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity,count=0;
      function visit(p){
        if(store)store.push(p.x,p.y,p.z);
        const x=view[0]*p.x+view[4]*p.y+view[8]*p.z+view[12];
        const y=view[1]*p.x+view[5]*p.y+view[9]*p.z+view[13];
        const depth=-(view[2]*p.x+view[6]*p.y+view[10]*p.z+view[14]);
        if(depth<=0)throw new Error('Visible geometry is behind the camera.');
        minX=Math.min(minX,x/depth);maxX=Math.max(maxX,x/depth);
        minY=Math.min(minY,y/depth);maxY=Math.max(maxY,y/depth);count++;
      }
      function triangle(a,b,c,planes){
        let polygon=[a,b,c];
        for(const plane of planes){
          const clipped=[];
          for(let i=0;i<polygon.length;i++){
            const p=polygon[i],q=polygon[(i+1)%polygon.length];
            const dp=plane.distanceToPoint(p),dq=plane.distanceToPoint(q);
            if(dp>=0)clipped.push(p);
            if((dp>=0)!==(dq>=0))clipped.push(p.clone().lerp(q,dp/(dp-dq)));
          }
          polygon=clipped;
          if(!polygon.length)return;
        }
        polygon.forEach(visit);
      }
      stage.sceneRoot.traverseVisible(object=>{
        if(!object.isMesh)return;
        const geometry=object.geometry,position=geometry.attributes.position;
        if(!position)return;
        const materials=Array.isArray(object.material)?object.material:[object.material];
        const groups=geometry.groups.length?geometry.groups:[{start:0,count:geometry.index?.count??position.count,materialIndex:0}];
        const instance=new THREE.Matrix4(),matrix=new THREE.Matrix4();
        const repetitions=object.isInstancedMesh?object.count:1;
        for(let n=0;n<repetitions;n++){
          if(object.isInstancedMesh){object.getMatrixAt(n,instance);matrix.multiplyMatrices(object.matrixWorld,instance);}
          else matrix.copy(object.matrixWorld);
          for(const group of groups){
            const material=materials[group.materialIndex];
            if(!material || material.visible===false)continue;
            const planes=material.clippingPlanes||[];
            const end=Math.min(group.start+group.count,geometry.index?.count??position.count);
            for(let i=group.start;i+2<end;i+=3){
              const points=[i,i+1,i+2].map(j=>new THREE.Vector3()
                .fromBufferAttribute(position,geometry.index?geometry.index.getX(j):j)
                .applyMatrix4(matrix));
              triangle(...points,planes);
            }
          }
        }
      });
      if(!count)throw new Error('No visible model geometry measured.');
      return {minX,maxX,minY,maxY,count};
    }
    function measureCached(points,camera){
      const view=camera.matrixWorldInverse.elements;
      let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
      for(let i=0;i<points.length;i+=3){
        const x=points[i],y=points[i+1],z=points[i+2];
        const depth=-(view[2]*x+view[6]*y+view[10]*z+view[14]);
        if(depth<=0)throw new Error('Cached visible geometry behind camera.');
        const nx=(view[0]*x+view[4]*y+view[8]*z+view[12])/depth;
        const ny=(view[1]*x+view[5]*y+view[9]*z+view[13])/depth;
        minX=Math.min(minX,nx);maxX=Math.max(maxX,nx);
        minY=Math.min(minY,ny);maxY=Math.max(maxY,ny);
      }
      return {minX,maxX,minY,maxY,count:points.length/3};
    }
    for(const club of ['dortmund','elversberg']){
      const viewSource=structuredClone(source);
      if(mainStandBack && club==='elversberg'){
        // Counter-rotate the input to the unchanged study adapter. Its normal
        // 180° rotation then cancels this one. Only the isolated copy changes.
        const rotate=p=>[-p[0],-p[1],...p.slice(2)];
        viewSource.blocks.forEach(block=>{block.quad=block.quad.map(rotate);});
        viewSource.outline=viewSource.outline.map(rotate);
        viewSource.roof.segments.forEach(segment=>{segment.quad=segment.quad.map(rotate);});
        viewSource.mainStand='NORD';
        viewSource.farStand='SUED';
      }
      const handle=await mountStudyModel({host:document.getElementById('host'),club,source:viewSource,concept:'cutaway'});
      if(mainStandBack && club==='dortmund')handle.model.rotation.y+=Math.PI;
      const orientation=mainStandBack?{
        rearStand:club==='dortmund'?'WEST':'SUED',
        hiddenFrontStand:club==='dortmund'?'OST':'NORD',
        leftStand:club==='dortmund'?'SUED':'OST',
        rightStand:club==='dortmund'?'NORD':'WEST',
        modelTurnDegrees:180,roofSegmentsAdded:0,
      }:null;
      const lighting=createStudyLighting(handle,null);
      lighting.setState(false,false,false);
      const stage=handle.stage;
      applyStudyCamera(stage.camera,'cutaway',width,height);
      const baselineCorners=corners.map(([x,y])=>projectStudy(stage.camera,width,height,x,y));
      if(!fitted && mode==='middle'){
        const focal=original.zoom*.75;
        const nearY=(original.principal[1]-baselineCorners[2].y)/original.zoom;
        fitted={mode,focal,cx:width/2,cy:baselineCorners[2].y+focal*nearY,
          margin,fieldScale:.75,position:stage.camera.position.toArray(),
          tilt:original.tilt,field:[105,68],format:[width,height],baselineCorners,
          allowOuterFrameCrop:true};
      }
      if(!fitted){
        handle.setRoof(true);
        const points=[];
        measure(stage,points);
        const start=stage.camera.position.clone();
        const focal=original.zoom;
        function at(factor){
          stage.camera.position.copy(start).multiplyScalar(factor);
          stage.camera.updateMatrixWorld(true);
          return measureCached(points,stage.camera);
        }
        function fits(bounds){
          return focal*Math.max(Math.abs(bounds.minX),Math.abs(bounds.maxX))<=width/2-margin &&
            focal*(bounds.maxY-bounds.minY)<=height-2*margin;
        }
        let low=1,high=1;
        while(!fits(at(high))){high*=1.2;if(high>5)throw new Error('No close shared framing found.');}
        for(let step=0;step<28;step++){
          const middle=(low+high)/2;
          if(fits(at(middle)))high=middle;else low=middle;
        }
        const bounds=at(high);
        fitted={focal,cx:width/2,cy:(height+focal*(bounds.maxY+bounds.minY))/2,margin,
          retreatFactor:high,bounds,position:stage.camera.position.toArray(),
          baselinePosition:start.toArray(),tilt:original.tilt,field:[105,68],
          format:[width,height],baselineCorners};
      }
      // Exactly the SAME projection and pose for both clubs and roof states.
      stage.camera.position.fromArray(fitted.position);
      stage.camera.updateMatrixWorld(true);
      stage.camera.projectionMatrix.makePerspective(-fitted.cx/fitted.focal,
        (width-fitted.cx)/fitted.focal,fitted.cy/fitted.focal,
        -(height-fitted.cy)/fitted.focal,1,6000);
      stage.camera.projectionMatrixInverse.copy(stage.camera.projectionMatrix).invert();
      for(const roof of [true,false]){
        handle.setRoof(roof);
        stage.render();
        const bounds=measure(stage);
        const screen={left:fitted.cx+fitted.focal*bounds.minX,right:fitted.cx+fitted.focal*bounds.maxX,
          top:fitted.cy-fitted.focal*bounds.maxY,bottom:fitted.cy-fitted.focal*bounds.minY};
        if(mode==='full' && (screen.left<margin-.01 || screen.right>width-margin+.01 ||
           screen.top<margin-.01 || screen.bottom>height-margin+.01))
          throw new Error(`${club} roof=${roof} exceeds the shared safety margin: ${JSON.stringify(screen)}`);
        const fieldCorners=corners.map(([x,y])=>projectStudy(stage.camera,width,height,x,y));
        if(approved && (JSON.stringify(fieldCorners)!==JSON.stringify(approved.corners) ||
          JSON.stringify(stage.camera.projectionMatrix.toArray())!==JSON.stringify(approved.projection) ||
          JSON.stringify(stage.camera.matrixWorldInverse.toArray())!==JSON.stringify(approved.pose)))
          throw new Error('Main-stand rotation changed the approved field projection or camera pose.');
        if(fieldCorners.some(p=>!p.visible || p.x<margin || p.x>width-margin ||
          p.y<margin || p.y>height-margin))throw new Error('Playable field is cropped.');
        states.push({club,roof,screen,corners:fieldCorners,orientation,
          projection:stage.camera.projectionMatrix.toArray(),pose:stage.camera.matrixWorldInverse.toArray(),
          visibleRoofMeshes:handle.roofMeshes.filter(mesh=>mesh.visible).length,
          png:handle.canvas.toDataURL('image/png')});
      }
      lighting.dispose();handle.dispose();
    }
    if(states.some(state=>JSON.stringify(state.corners)!==JSON.stringify(states[0].corners) ||
      JSON.stringify(state.projection)!==JSON.stringify(states[0].projection) ||
      JSON.stringify(state.pose)!==JSON.stringify(states[0].pose)))
      throw new Error('Club/roof field projection parity failed.');
    if(states.some(state=>!state.roof&&state.visibleRoofMeshes!==0))
      throw new Error('Roof-off assembly still visible.');
    return {fitted,states};
   },{base,source,mode,mainStandBack,approved});
  if(errors.length)throw new Error(errors.join('\n'));
  for(const state of result.states){
    fs.writeFileSync(`${output}/${state.club}_${state.roof?'roof':'no_roof'}.png`,
      Buffer.from(state.png.split(',')[1],'base64'));
    delete state.png;
  }
  fs.writeFileSync(`${output}/verification.json`,JSON.stringify(result,null,2));
  console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
