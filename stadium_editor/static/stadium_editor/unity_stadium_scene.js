import * as THREE from './stage/vendor/three.module.js';
import './source_seats.js?v=2';
import {applyStudyCamera} from './study_camera.js?v=3';
import {buildDortmundSurroundings} from './dortmund_surroundings.js?v=58';
import {validateCalibration, standForCenter, tickerQuaternion} from './unity_calibration.js?v=2';
import {mountBridgeHeightNotice} from './bridge_height_evidence.js?v=1';
import {mountHeidenheimFloodlightVisuals} from './heidenheim_floodlight_visuals.js?v=2';
import {
  createTransitionController, isConfirmedAllianzFacadeMaterial, isConfirmedAllianzLowerFacade,
  buildAllianzLowerFacadeClosure,
  projectFacadeUv, runtimeFixtureIntensity, sourceMaterialFinish, splitFacadeTriangles,
  splitLowerFacadeTriangles, supportsAllianzPresentation,
} from './allianz_presentation.js?v=11';

/** Original source geometry, with its own club-scoped runtime presentation. */
export async function mountUnityStadium({
  element, presentation, tickerPreview = false, onOrbitChange, initialState = {},
}) {
  if (presentation.renderer !== 'unity-spatial')
    throw new Error('Unpassendes Original-Stadionmodell.');
  const response = await fetch(presentation.modelUrl);
  if (!response.ok) throw new Error('Original-Stadionmodell nicht verfügbar.');
  const manifest = await response.json();
  if (manifest.clubFmiId !== presentation.clubFmiId ||
      manifest.sourceSha256 !== presentation.sourceSha256)
    throw new Error('Modellquelle gehört nicht zum gewählten Verein.');
  const calibration = validateCalibration(manifest.calibration);
  const allianz = supportsAllianzPresentation(presentation, manifest);
  if(presentation.seatDesign && !allianz)
    throw new Error('FCB-Sitzbemalung passt nicht zum freigegebenen Originalmodell.');
  const base = new URL('.', new URL(presentation.modelUrl, location.href));
  const seatSource = allianz ? await globalThis.StadiumSourceSeats.load(presentation) : null;
  let buffer;
  if(seatSource)buffer=seatSource.buffer;
  else {
    const binaryResponse = await fetch(new URL('geometry.bin', base));
    if (!binaryResponse.ok) throw new Error('Original-Stadiongeometrie fehlt.');
    buffer = await binaryResponse.arrayBuffer();
  }
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
  const removeBridgeNotice = mountBridgeHeightNotice(element,
    environment.group.userData.bridgeHeightEvidence || [], environment.group.userData.bridgeHeightNotice);
  const hemisphere = new THREE.HemisphereLight(0xe7f1f2, 0x344045, 1.35);
  const sun = new THREE.DirectionalLight(0xfff3d4, 1.5);
  sun.position.set(-135, 210, 100);
  scene.add(hemisphere, sun);
  const nightFill = allianz ? new THREE.DirectionalLight(0xb7cce0, 0) : null;
  if (nightFill) {
    nightFill.position.set(70, 95, -110);
    scene.add(nightFill);
  }
  let skyTexture = null, skyCanvas = null, skyContext = null, facadeTexture = null;
  const facadeMaterials = [];
  if (allianz) {
    skyCanvas = document.createElement('canvas');
    skyCanvas.width = 512;
    skyCanvas.height = 256;
    skyContext = skyCanvas.getContext('2d');
    skyTexture = new THREE.CanvasTexture(skyCanvas);
    skyTexture.mapping = THREE.EquirectangularReflectionMapping;
    skyTexture.colorSpace = THREE.SRGBColorSpace;
    scene.background = skyTexture;
    const membraneCanvas = document.createElement('canvas');
    membraneCanvas.width = 1024;
    membraneCanvas.height = 512;
    const membraneContext = membraneCanvas.getContext('2d');
    membraneContext.fillStyle = '#f2f3ef';
    membraneContext.fillRect(0, 0, membraneCanvas.width, membraneCanvas.height);
    membraneContext.strokeStyle = 'rgba(86,96,100,.14)';
    membraneContext.lineWidth = 1;
    const cellWidth = 32, cellHeight = 28;
    for (let y = -cellHeight; y < membraneCanvas.height + cellHeight; y += cellHeight) {
      const offset = (Math.round(y / cellHeight) % 2) * cellWidth / 2;
      for (let x = -cellWidth; x < membraneCanvas.width + cellWidth; x += cellWidth) {
        const cx = x + offset;
        membraneContext.beginPath();
        membraneContext.moveTo(cx + cellWidth / 2, y);
        membraneContext.lineTo(cx + cellWidth, y + cellHeight / 2);
        membraneContext.lineTo(cx + cellWidth / 2, y + cellHeight);
        membraneContext.lineTo(cx, y + cellHeight / 2);
        membraneContext.closePath();
        membraneContext.stroke();
      }
    }
    facadeTexture = new THREE.CanvasTexture(membraneCanvas);
    facadeTexture.colorSpace = THREE.SRGBColorSpace;
  }
  const camera = new THREE.PerspectiveCamera(42, 1, 1, 2400);
  const textures = new Map(), materials = [], geometries = [], roof = [], crowd = [];
  const lowerFacadeSourceProfiles = [];
  const loader = new THREE.TextureLoader();
  let disposed = false, day = allianz ? initialState.day !== false : true;
  let floodlight = Boolean(initialState.floodlight), roofVisible = initialState.roofVisible !== false;
  let floodlightVisuals;
  let presentationTransition = null;
  let exposureMultiplier = 1;
  let renderTransitionFrame = () => {};
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
  const paintSky = night => {
    if (!skyContext || !skyTexture) return;
    const mixColor = (dayColor, nightColor) => {
      const a = dayColor.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16));
      const b = nightColor.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16));
      return `rgb(${a.map((value, index) => Math.round(value + (b[index] - value) * night)).join(',')})`;
    };
    const gradient = skyContext.createLinearGradient(0, 0, 0, skyCanvas.height);
    gradient.addColorStop(0, mixColor('#6ca8d7', '#06162d'));
    gradient.addColorStop(.43, mixColor('#a8c9da', '#102b45'));
    gradient.addColorStop(.54, mixColor('#d8d5c7', '#294455'));
    gradient.addColorStop(1, mixColor('#a5c4d2', '#0a1d32'));
    skyContext.fillStyle = gradient;
    skyContext.fillRect(0, 0, skyCanvas.width, skyCanvas.height);
    const glow = skyContext.createRadialGradient(330, 137, 2, 330, 137, 170);
    glow.addColorStop(0, `rgba(255,221,174,${.24 * (1 - night)})`);
    glow.addColorStop(1, 'rgba(255,221,174,0)');
    skyContext.fillStyle = glow;
    skyContext.fillRect(150, 0, 360, 256);
    skyTexture.needsUpdate = true;
  };
  const applyAllianzMood = blend => {
    if (!allianz) return;
    const night = 1 - blend;
    paintSky(night);
    hemisphere.intensity = 1.35 + (.46 - 1.35) * night;
    hemisphere.color.set('#dcecf2').lerp(new THREE.Color('#8da4bb'), night);
    hemisphere.groundColor.set('#344045').lerp(new THREE.Color('#263542'), night);
    sun.intensity = 1.5 * blend;
    if (nightFill) nightFill.intensity = .32 * night;
    renderer.toneMappingExposure = (1.08 + (.9 - 1.08) * night) * exposureMultiplier;
    scene.fog.color.set('#b3c5c8').lerp(new THREE.Color('#102638'), night);
    for (const material of facadeMaterials)
      material.emissiveIntensity = .82 * night;
  };
  if (allianz) {
    presentationTransition = createTransitionController({
      initial: {day: initialState.day === false ? 0 : 1},
      apply: state => applyAllianzMood(state.day),
      onFrame: () => renderTransitionFrame(),
      durationMs: 1500,
      reducedMotion: () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true,
    });
  }
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
        material.name = part.material || `source:${entry.name}`;
        const sourceFinish = allianz ? sourceMaterialFinish(part.material) : null;
        if (sourceFinish) {
          material.roughness = sourceFinish.roughness;
          material.metalness = sourceFinish.metalness;
          material.userData.sourceRole = sourceFinish.role;
        }
        const isLowerFacade = allianz && isConfirmedAllianzLowerFacade(entry, part);
        if (isLowerFacade) lowerFacadeSourceProfiles.push(position);
        const isFacadeSource = isLowerFacade || (allianz && isConfirmedAllianzFacadeMaterial(entry, part));
        let facadeMaterial = null, facadeInteriorMaterial = null;
        if (isFacadeSource) {
          if (!isLowerFacade) {
            material.roughness = .58;
            material.metalness = .04;
          }
          facadeMaterial = material.clone();
          facadeMaterial.name = 'Allianz membrane · approximate seams';
          if (!isLowerFacade) {
            facadeMaterial.color.set('#f4f5f1');
            facadeMaterial.roughness = .4;
            facadeMaterial.metalness = .08;
          }
          facadeMaterial.side = THREE.FrontSide;
          facadeMaterial.map = facadeTexture;
          facadeMaterial.emissiveMap = facadeTexture;
          facadeMaterial.emissive.set('#f01836');
          facadeMaterial.emissiveIntensity = 0;
          facadeMaterial.userData.sourceRole = 'confirmed existing cover shell · schematic finish';
          facadeInteriorMaterial = material.clone();
          facadeInteriorMaterial.name = 'Allianz membrane · neutral interior';
          facadeInteriorMaterial.side = THREE.BackSide;
          if (!isLowerFacade) {
            facadeInteriorMaterial.roughness = .58;
            facadeInteriorMaterial.metalness = .04;
          }
          materials.push(facadeMaterial);
          materials.push(facadeInteriorMaterial);
          facadeMaterials.push(facadeMaterial);
        }
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
        let bodyGeometryIndices = bodyIndices, roofGeometryIndices = roofIndices, facadeIndices = [];
        if (isLowerFacade) {
          const split = splitLowerFacadeTriangles(position, bodyIndices);
          facadeIndices = split.facadeIndices;
          bodyGeometryIndices = split.remainingIndices;
        } else if (isFacadeSource) {
          const split = splitFacadeTriangles(position, roofIndices);
          facadeIndices = split.facadeIndices;
          roofGeometryIndices = split.remainingIndices;
        }
        if (isFacadeSource && facadeIndices.length) {
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute('position',new THREE.BufferAttribute(position,3));
          geometry.setAttribute('uv',new THREE.BufferAttribute(isLowerFacade
            ? projectFacadeUv(position,29.1,34.52) : projectFacadeUv(position),2));
          const shellIndices = [...bodyGeometryIndices,...roofGeometryIndices];
          geometry.setIndex([...shellIndices,...facadeIndices,...facadeIndices]);
          if (shellIndices.length) geometry.addGroup(0,shellIndices.length,0);
          geometry.addGroup(shellIndices.length,facadeIndices.length,1);
          geometry.addGroup(shellIndices.length + facadeIndices.length,facadeIndices.length,2);
          geometry.computeVertexNormals();
          const mesh = new THREE.Mesh(geometry,[material,facadeMaterial,facadeInteriorMaterial]);
          mesh.name = `SOURCE_${entry.name}_${isLowerFacade?'body':'roof'}`;
          mesh.userData.sourcePathId = entry.pathId;
          model.add(mesh); geometries.push(geometry);
          if (!isLowerFacade) roof.push(mesh);
          if(entry.name.startsWith(calibration.crowdPrefix)) {
            geometry.computeBoundingBox();
            const center=geometry.boundingBox.getCenter(new THREE.Vector3());
            // Same right-handed native frame as the surrounding map adapter.
            mesh.userData.stand = standForCenter(center, calibration.standAxes);
            mesh.userData.sourceColor=material.color.clone();
            crowd.push(mesh);
          }
        } else {
          for (const [list,isRoof] of [[bodyIndices,false],[roofGeometryIndices,true]]) {
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
    }
    if (allianz && lowerFacadeSourceProfiles.length) {
      const closure = buildAllianzLowerFacadeClosure(lowerFacadeSourceProfiles);
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(closure.positions, 3));
      geometry.setAttribute('uv', new THREE.BufferAttribute(closure.uvs, 2));
      geometry.setIndex(new THREE.BufferAttribute(closure.indices, 1));
      geometry.computeVertexNormals();
      const closureMaterial = new THREE.MeshStandardMaterial({
        color: '#f4f5f1', roughness: .4, metalness: .08,
        map: facadeTexture, emissiveMap: facadeTexture,
        emissive: '#f01836', emissiveIntensity: 0, side: THREE.DoubleSide,
      });
      closureMaterial.name = 'Allianz lower facade · source-aligned reconstruction';
      closureMaterial.userData.sourceRole = 'approximate closure between source wall bands';
      materials.push(closureMaterial);
      facadeMaterials.push(closureMaterial);
      const mesh = new THREE.Mesh(geometry, closureMaterial);
      mesh.name = 'DERIVED_Allianz_lower_facade_closure';
      mesh.userData.reconstruction = true;
      mesh.userData.sourceRole = 'radial interpolation of confirmed lower-wall source profiles';
      mesh.userData.sourceProfile = closure.sourceProfile;
      model.add(mesh);
      geometries.push(geometry);
    }
    if(!roof.length) throw new Error('Original-Dachgeometrie fehlt.');
    if (allianz) applyAllianzMood(presentationTransition.current.day);
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
       light.userData.onIntensity=runtimeFixtureIntensity(fixture, allianz);
      scene.add(light,target);
      return light;
    });
    floodlightVisuals = mountHeidenheimFloodlightVisuals(scene, manifest, buffer);
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
    // The controller is created before render to snap the initial sky/lights.
    // Install the live renderer callback only once it exists; transitions then
    // render on demand, with no perpetual animation loop.
    renderTransitionFrame = render;
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
    let seatGeometryKey=null, seatSourceRing=null;
    let seatCoverage=null;
    // The source footprint and schematic 2D blueprint have different radial
    // extents. Both directions use the same source-derived registration.
    if(allianz)seatSourceRing=seatSource.index.ring;
    const applySeatDesign = design => {
      if(!allianz || !design)return;
      const custom=design.mode==='custom';
      const blocks=(design.blocks || []).map((b,i)=>({...b,_index:i}));
      const key=JSON.stringify(blocks.map(b=>[b.id,b.quad,b.rows,b.seats]));
      const registration=custom ? globalThis.StadiumSourceSeats.registration(
        blocks,presentation.frame,calibration.surroundingsAxes) : null;
      const palette=(design.palette || []).map(hex=>new THREE.Color(hex));
      const neutral=new THREE.Color('#606a74');
      let covered=0,total=0;
      for(const mesh of crowd) {
        const material=mesh.material;
        if(!Object.hasOwn(mesh.userData,'sourceMap'))mesh.userData.sourceMap=material.map;
        const changed=material.vertexColors!==custom;
        material.map=custom ? null : mesh.userData.sourceMap;
        material.vertexColors=custom;
        material.color.copy(custom ? new THREE.Color('#ffffff') : mesh.userData.sourceColor);
        if(custom) {
          const positions=mesh.geometry.getAttribute('position');
          if(!mesh.userData.seatAddresses || key!==seatGeometryKey) {
            const addresses=new Int32Array(positions.count*2).fill(-1);
            const tier=globalThis.StadiumSourceSeats.tierOf(mesh.name.replace(/^SOURCE_/,''));
            for(let i=0;i<positions.count;i++){
              const point=globalThis.StadiumSourceSeats.warp(
                [positions.getX(i),positions.getZ(i)],tier,seatSourceRing,registration.ring);
              const hit=point && registration.lookup(...point,tier);
              if(hit){addresses[i*2]=hit.block._index;addresses[i*2+1]=hit.index;}
            }
            mesh.userData.seatAddresses=addresses;
          }
          let colors=mesh.geometry.getAttribute('color');
          if(!colors){colors=new THREE.BufferAttribute(new Float32Array(positions.count*3),3);mesh.geometry.setAttribute('color',colors);}
          const addresses=mesh.userData.seatAddresses;
          for(let i=0;i<positions.count;i++){
            const bi=addresses[i*2],si=addresses[i*2+1];
            total++;
            if(bi>=0)covered++;
            const ci=bi<0 ? 0 : registration.blocks[bi].values[si];
            const c=ci>0 && palette[ci] ? palette[ci] : neutral;
            colors.setXYZ(i,c.r,c.g,c.b);
          }
          colors.needsUpdate=true;
        }
        if(changed)material.needsUpdate=true;
      }
      if(custom)seatCoverage={covered,total};
      seatGeometryKey=key;
    };
    const update = async (next={})=>{
      if(disposed) return;
      if(typeof next.day==='boolean') day=next.day;
      if(typeof next.floodlight==='boolean') floodlight=next.floodlight;
      if(typeof next.roofVisible==='boolean') roofVisible=next.roofVisible;
      if(next.camera) cameraMode=next.camera==='seat'?'seat':'orbit';
      if(Number.isFinite(next.exposure)) {
        if (allianz) {
          exposureMultiplier=Math.max(.25,Math.min(3,next.exposure));
          applyAllianzMood(presentationTransition.current.day);
        } else renderer.toneMappingExposure=Math.max(.25,Math.min(3,next.exposure));
      }
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
      if(allianz) {
        if(next.seatDesign)applySeatDesign(next.seatDesign);
      } else if(colors) crowd.forEach(mesh=>{
        mesh.material.color.copy(mesh.userData.sourceColor);
        if(/^#[0-9a-f]{6}$/i.test(colors[mesh.userData.stand]||''))
          mesh.material.color.set(colors[mesh.userData.stand]);
      });
      if(allianz) presentationTransition?.set({day:day?1:0});
      else {
        hemisphere.intensity=day?1.35:.08; sun.intensity=day?1.5:0;
        scene.background.set(day?'#071316':'#02070b');scene.fog.color.copy(scene.background);
      }
      sources.forEach(light=>{light.intensity=floodlight?light.userData.onIntensity:0;});
      floodlightVisuals.update({enabled:floodlight, day});
      roof.forEach(mesh=>{mesh.visible=roofVisible;});
      render();
    };
    resize();
    await update({designColors:presentation.designColors,seatDesign:presentation.seatDesign});
    return {
      kind:'three', stage:{renderer,render,camera,scene,model}, update,
      seatCoverage:()=>seatCoverage,
      setActive(){}, setTickerRoofVisible(value){return update({roofVisible:value});},
      lightingEvidence:()=>manifest.fixtures,
      dispose(){
        if(disposed) return; disposed=true;observer.disconnect();
        presentationTransition?.dispose();
        floodlightVisuals.dispose();
        controls.removeEventListener('pointerdown',down);controls.removeEventListener('pointermove',move);
        controls.removeEventListener('pointerup',up);controls.removeEventListener('pointercancel',up);
        controls.removeEventListener('wheel',wheel);
        geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());
        textures.forEach(p=>p.then(t=>t.dispose()));
        skyTexture?.dispose();facadeTexture?.dispose();environment.dispose();renderer.dispose();
        removeBridgeNotice();
        renderer.domElement.remove();
      },
    };
  } catch(error) {
    presentationTransition?.dispose();
    floodlightVisuals?.dispose();
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());
    textures.forEach(p=>p.then(t=>t.dispose()));
    skyTexture?.dispose();facadeTexture?.dispose();environment.dispose();renderer.dispose();
    removeBridgeNotice();
    renderer.domElement.remove(); throw error;
  }
}
