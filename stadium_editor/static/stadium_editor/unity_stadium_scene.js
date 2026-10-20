import * as THREE from './stage/vendor/three.module.js';
import {applyStudyCamera} from './study_camera.js?v=3';
import {buildDortmundSurroundings} from './dortmund_surroundings.js?v=56';
import {validateCalibration, standForCenter, tickerQuaternion} from './unity_calibration.js?v=2';

/** Original source geometry, with its own club-scoped runtime presentation. */
export async function mountUnityStadium({element, presentation, tickerPreview = false, onOrbitChange}) {
  if (presentation.renderer !== 'unity-spatial')
    throw new Error('Unpassendes Original-Stadionmodell.');
  const response = await fetch(presentation.modelUrl);
  if (!response.ok) throw new Error('Original-Stadionmodell nicht verfügbar.');
  const manifest = await response.json();
  if (manifest.clubFmiId !== presentation.clubFmiId ||
      manifest.sourceSha256 !== presentation.sourceSha256)
    throw new Error('Modellquelle gehört nicht zum gewählten Verein.');
  const calibration = validateCalibration(manifest.calibration);
  const base = new URL('.', new URL(presentation.modelUrl, location.href));
  const binaryResponse = await fetch(new URL('geometry.bin', base));
  if (!binaryResponse.ok) throw new Error('Original-Stadiongeometrie fehlt.');
  const buffer = await binaryResponse.arrayBuffer();
  const renderer = new THREE.WebGLRenderer({antialias:true, alpha:false});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.6));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  renderer.localClippingEnabled = tickerPreview;
  renderer.domElement.setAttribute('aria-label', `${presentation.stadium} · Originalmodell und eigener Ortsplan`);
  element.replaceChildren(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#071316');
  scene.fog = new THREE.Fog('#071316', 850, 1800);
  const model = new THREE.Group();
  scene.add(model);
  const environment = buildDortmundSurroundings(THREE, presentation.surroundings,
    presentation.frame, calibration.surroundingsAxes);
  scene.add(environment.group);
  const hemisphere = new THREE.HemisphereLight(0xe7f1f2, 0x344045, 1.35);
  const sun = new THREE.DirectionalLight(0xfff3d4, 1.5);
  sun.position.set(-135, 210, 100);
  scene.add(hemisphere, sun);
  const camera = new THREE.PerspectiveCamera(42, 1, 1, 2400);
  const textures = new Map(), materials = [], geometries = [], roof = [], crowd = [];
  const loader = new THREE.TextureLoader();
  let disposed = false, day = true, floodlight = false, roofVisible = true;
  let {azimuth, elevation, distance} = calibration.orbitDefault;
  let cameraMode = 'orbit';
  const frontCut = new THREE.Plane(
    new THREE.Vector3(...calibration.tickerFrontCut.normal), calibration.tickerFrontCut.constant);
  const loadTexture = name => {
    if (!textures.has(name)) textures.set(name, loader.loadAsync(new URL(name,base).href).then(t => {
      t.colorSpace = THREE.SRGBColorSpace; t.flipY=false; return t;
    }));
    return textures.get(name);
  };
  try {
    // Bound download concurrency instead of opening all source texture requests at once.
    const names = [...manifest.textures];
    await Promise.all(Array.from({length:Math.min(8,names.length)},async()=>{
      while(names.length) await loadTexture(names.pop());
    }));
    for (const entry of manifest.meshes) {
      // Source-exported generic context is replaced by the club's mapped OSM context.
      if (calibration.skipMeshPrefixes.some(prefix => entry.name.startsWith(prefix))) continue;
      const position = new Float32Array(buffer,entry.positionOffset,entry.vertexCount*3);
      const uv = new Float32Array(buffer,entry.uvOffset,entry.vertexCount*2);
      for (const part of entry.parts) {
        let partUv = uv;
        if (part.uvProjection !== undefined) {
          const p = part.uvProjection;
          if (!Array.isArray(p) || p.length !== 8 || !p.every(Number.isFinite))
            throw new Error('Ungültige Boden-Texturprojektion.');
          partUv = new Float32Array(entry.vertexCount*2);
          for (let i=0;i<entry.vertexCount;i++) {
            const x=position[i*3], y=position[i*3+1], z=position[i*3+2];
            partUv[i*2]=p[0]*x+p[1]*y+p[2]*z+p[3];
            partUv[i*2+1]=p[4]*x+p[5]*y+p[6]*z+p[7];
          }
        }
        const material = new THREE.MeshStandardMaterial({
          color: new THREE.Color(...part.color), roughness:.85, metalness:0,
          map: part.texture ? await loadTexture(part.texture) : null,
          side: THREE.DoubleSide,
          transparent: part.transparent === true,
          alphaTest: part.alphaTest ?? 0,
          depthWrite: part.transparent !== true,
          clippingPlanes: tickerPreview && !entry.name.startsWith(calibration.pitchPrefix) ? [frontCut] : [],
        });
        materials.push(material);
        const indices = new Uint32Array(buffer,part.indexOffset,part.indexCount);
        const bodyIndices = [], roofIndices = [];
        for (let i=0;i<indices.length;i+=3) {
          // Never classify crowd surfaces as roof, even on an upper tier.
          const roofCandidate = !entry.name.startsWith(calibration.crowdPrefix) &&
            (!(calibration.roofMeshPrefixes||[]).length ||
             calibration.roofMeshPrefixes.some(prefix=>entry.name.startsWith(prefix)));
          const isRoof = roofCandidate &&
            indices.slice(i,i+3).every(index=>position[index*3+1]>=calibration.roofMinHeight);
          (isRoof ? roofIndices : bodyIndices).push(indices[i],indices[i+1],indices[i+2]);
        }
        for (const [list,isRoof] of [[bodyIndices,false],[roofIndices,true]]) {
          if (!list.length) continue;
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute('position',new THREE.BufferAttribute(position,3));
          geometry.setAttribute('uv',new THREE.BufferAttribute(partUv,2));
          geometry.setIndex(list); geometry.computeVertexNormals();
          const mesh = new THREE.Mesh(geometry,material);
          mesh.name = `SOURCE_${entry.name}_${isRoof?'roof':'body'}`;
          mesh.userData.sourcePathId = entry.pathId;
          model.add(mesh); geometries.push(geometry);
          if(isRoof) roof.push(mesh);
          if(entry.name.startsWith(calibration.crowdPrefix)) {
            geometry.computeBoundingBox();
            const center=geometry.boundingBox.getCenter(new THREE.Vector3());
            // Same right-handed native frame as the surrounding map adapter.
            mesh.userData.stand = standForCenter(center, calibration.standAxes);
            mesh.userData.sourceColor=material.color.clone();
            crowd.push(mesh);
          }
        }
      }
    }
    if(!roof.length) throw new Error('Original-Dachgeometrie fehlt.');
    const sources = manifest.fixtures.map(fixture=>{
      if(!Number.isFinite(fixture.meshDistance)||fixture.meshDistance>2 ||
         !fixture.position.every(Number.isFinite)||!fixture.direction.every(Number.isFinite))
        throw new Error('Leuchtennachweis ist ungültig.');
      const target = new THREE.Object3D();
      target.position.fromArray(fixture.position).addScaledVector(
        new THREE.Vector3(...fixture.direction),50);
      const light=new THREE.SpotLight(new THREE.Color(...fixture.color),0,fixture.range,
        THREE.MathUtils.degToRad(fixture.angle/2),.5,2);
      light.position.fromArray(fixture.position); light.target=target;
      light.userData.fixture=fixture;
      light.userData.onIntensity=fixture.intensity*8*Math.min(4,Math.sqrt(fixture.representedIds.length));
      scene.add(light,target);
      return light;
    });
    const pose = () => {
      if(tickerPreview) {
        applyStudyCamera(camera,'approved-elversberg',element.clientWidth,element.clientHeight);
        const q=tickerQuaternion(calibration.tickerRotationY);
        camera.position.applyQuaternion(q); camera.quaternion.premultiply(q);
        camera.updateMatrixWorld(true);
      } else if(cameraMode==='seat') {
        camera.position.fromArray(manifest.seatView.position).add(new THREE.Vector3(0,1.25,0));
        camera.lookAt(0,1,0);
      } else {
        camera.position.set(distance*Math.sin(azimuth)*Math.cos(elevation),
          12+distance*Math.sin(elevation),distance*Math.cos(azimuth)*Math.cos(elevation));
        camera.lookAt(0,12,0);
      }
    };
    const render = () => { if(!disposed) {pose();renderer.render(scene,camera);} };
    const resize = () => {
      const w=element.clientWidth,h=element.clientHeight;
      if(!w||!h||disposed) return;
      renderer.setSize(w,h,false); camera.aspect=w/h;camera.updateProjectionMatrix();render();
    };
    const observer=new ResizeObserver(resize);
    observer.observe(element);
    let dragging=false, previousX=0, previousY=0;
    const controls=renderer.domElement;
    const down=event=>{
      if(tickerPreview || cameraMode!=='orbit' || event.button!==0) return;
      dragging=true;previousX=event.clientX;previousY=event.clientY;
      controls.setPointerCapture(event.pointerId);event.stopPropagation();
    };
    const move=event=>{
      if(!dragging) return;
      azimuth+=(event.clientX-previousX)*.006;
      elevation=Math.max(.18,Math.min(1.35,elevation+(event.clientY-previousY)*.004));
      previousX=event.clientX;previousY=event.clientY;
      onOrbitChange?.({azimuth:THREE.MathUtils.radToDeg(azimuth),
        elevation:THREE.MathUtils.radToDeg(elevation)});
      event.stopPropagation();render();
    };
    const up=()=>{dragging=false;};
    const wheel=event=>{
      if(tickerPreview || cameraMode!=='orbit') return;
      event.preventDefault();event.stopPropagation();
      distance=Math.max(180,Math.min(1200,distance*Math.exp(event.deltaY*.0008)));
      render();
    };
    controls.addEventListener('pointerdown',down);controls.addEventListener('pointermove',move);
    controls.addEventListener('pointerup',up);controls.addEventListener('pointercancel',up);
    controls.addEventListener('wheel',wheel,{passive:false});
    const update = async (next={})=>{
      if(disposed) return;
      if(typeof next.day==='boolean') day=next.day;
      if(typeof next.floodlight==='boolean') floodlight=next.floodlight;
      if(typeof next.roofVisible==='boolean') roofVisible=next.roofVisible;
      if(next.camera) cameraMode=next.camera==='seat'?'seat':'orbit';
      if(Number.isFinite(next.exposure))
        renderer.toneMappingExposure=Math.max(.25,Math.min(3,next.exposure));
      if(next.orbit) {
        azimuth=THREE.MathUtils.degToRad(Number(next.orbit.azimuth));
        elevation=THREE.MathUtils.degToRad(Math.max(10,Math.min(80,Number(next.orbit.elevation))));
      }
      let colors=next.designColors;
      if(next.scene) {
        const totals={};
        for(const block of next.scene.blocks || []) {
          const table=totals[block.stand] ||= {};
          for(const [count,index] of block.rle || []) if(index>0)
            table[index]=(table[index]||0)+count;
        }
        colors=Object.fromEntries(Object.entries(totals).flatMap(([stand,table])=>{
          const keys=Object.keys(table);
          return keys.length ? [[stand,next.scene.palette[keys.sort((a,b)=>table[b]-table[a])[0]]]] : [];
        }));
      }
      if(colors) crowd.forEach(mesh=>{
        mesh.material.color.copy(mesh.userData.sourceColor);
        if(/^#[0-9a-f]{6}$/i.test(colors[mesh.userData.stand]||''))
          mesh.material.color.set(colors[mesh.userData.stand]);
      });
      hemisphere.intensity=day?1.35:.08; sun.intensity=day?1.5:0;
      scene.background.set(day?'#071316':'#02070b');scene.fog.color.copy(scene.background);
      sources.forEach(light=>{light.intensity=floodlight?light.userData.onIntensity:0;});
      roof.forEach(mesh=>{mesh.visible=roofVisible;});
      render();
    };
    resize();
    await update({designColors:presentation.designColors});
    return {
      kind:'three', stage:{renderer,render,camera,scene,model}, update,
      setActive(){}, setTickerRoofVisible(value){return update({roofVisible:value});},
      lightingEvidence:()=>manifest.fixtures,
      dispose(){
        if(disposed) return; disposed=true;observer.disconnect();
        controls.removeEventListener('pointerdown',down);controls.removeEventListener('pointermove',move);
        controls.removeEventListener('pointerup',up);controls.removeEventListener('pointercancel',up);
        controls.removeEventListener('wheel',wheel);
        geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());
        textures.forEach(p=>p.then(t=>t.dispose()));environment.dispose();renderer.dispose();
        renderer.domElement.remove();
      },
    };
  } catch(error) {
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());
    textures.forEach(p=>p.then(t=>t.dispose()));environment.dispose();renderer.dispose();
    renderer.domElement.remove(); throw error;
  }
}
