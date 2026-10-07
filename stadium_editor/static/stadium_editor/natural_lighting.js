import {RGBELoader} from './stage/vendor/addons/loaders/RGBELoader.js';
import {buildFloodlightPlan} from './stage/stadium_lighting.js?v=1';

function sunnyDirection(texture, THREE) {
  const {data, width, height} = texture.image || {};
  if (!data || !width || !height) return new THREE.Vector3(-.45, .76, .46).normalize();
  let best = -Infinity, px = Math.floor(width * .5), py = Math.floor(height * .28);
  const stride = data.length / (width * height) >= 4 ? 4 : 3;
  for (let y = 1; y < height * .48; y += 1) for (let x = 0; x < width; x += 1) {
    const at = (y * width + x) * stride;
    const luminance = .2126 * data[at] + .7152 * data[at + 1] + .0722 * data[at + 2];
    if (luminance > best) { best = luminance; px = x; py = y; }
  }
  const longitude = (px / width - .5) * Math.PI * 2;
  const latitude = (.5 - py / height) * Math.PI;
  return new THREE.Vector3(
    Math.cos(longitude) * Math.cos(latitude),
    Math.sin(latitude),
    Math.sin(longitude) * Math.cos(latitude),
  ).normalize();
}

function perimeterBlocks(bounds, spacing = 9) {
  const result = [];
  const edges = [
    [[bounds.min.x,bounds.min.z],[bounds.max.x,bounds.min.z]],
    [[bounds.max.x,bounds.min.z],[bounds.max.x,bounds.max.z]],
    [[bounds.max.x,bounds.max.z],[bounds.min.x,bounds.max.z]],
    [[bounds.min.x,bounds.max.z],[bounds.min.x,bounds.min.z]],
  ];
  edges.forEach(([[ax,az],[bx,bz]], edge) => {
    const length = Math.hypot(bx-ax,bz-az), count = Math.max(1,Math.ceil(length/spacing));
    for(let i=0;i<count;i++) {
      const t0=i/count,t1=(i+1)/count;
      const left=[ax+(bx-ax)*t0,az+(bz-az)*t0],right=[ax+(bx-ax)*t1,az+(bz-az)*t1];
      result.push({id:`roof-${edge}-${i}`,stand:['north','east','south','west'][edge],order:i,
        quad:[[left[0],left[1]],[right[0],right[1]],[right[0],right[1]],[left[0],left[1]]],
        z1:bounds.max.y+1.8});
    }
  });
  return result;
}

export async function configureNaturalLighting(THREE, scene, renderer, assetBase,
  {profile = 'day', bounds = new THREE.Box3(new THREE.Vector3(-180,0,-150),
    new THREE.Vector3(180,70,150)), roofBounds = bounds,
  onProfileChange = () => {}} = {}) {
  const root = assetBase instanceof URL ? new URL(assetBase.href) : new URL(assetBase, import.meta.url);
  if (!root.pathname.endsWith('/')) root.pathname += '/';
  let disposed=false, generation=0, environment=null, hdri=null;
  const generator=new THREE.PMREMGenerator(renderer);
  const sky=new THREE.Group();
  const sun=new THREE.DirectionalLight(0xfff5dc,0);
  sun.target.position.set(0,0,0);
  const ambient=new THREE.HemisphereLight(0xe3edf0,0x52564a,0);
  const floodFill=new THREE.HemisphereLight(0xe6e9eb,0x343638,0);
  sky.add(sun,sun.target,ambient,floodFill);
  scene.add(sky);
  const shadowCenter=bounds.getCenter(new THREE.Vector3());
  shadowCenter.y=0;
  const shadowSize=bounds.getSize(new THREE.Vector3());
  const shadowRadius=Math.max(180,Math.hypot(shadowSize.x,shadowSize.z)*.51);
  const spots=[];
  const stagePlan=buildFloodlightPlan({
    standsBounds:[roofBounds.min.x,roofBounds.min.z,roofBounds.max.x,roofBounds.max.z],
    blocks:perimeterBlocks(roofBounds,9),
    steckbrief:{floodlights:{type:'rim'}},
  });
  stagePlan.sources.forEach(fixture=>{
    const origin=new THREE.Vector3(fixture.position[0],fixture.position[2],fixture.position[1]);
    const targetPosition=new THREE.Vector3(fixture.target[0],3,fixture.target[1]);
    const target=new THREE.Object3D(); target.position.copy(targetPosition); scene.add(target);
    const reach=origin.distanceTo(targetPosition)*1.35;
    const spot=new THREE.SpotLight(0xffedce,0,reach,.72,.72,1);
    spot.position.copy(origin); spot.target=target;
    spot.userData.onIntensity=460; spot.castShadow=false; scene.add(spot);
    spots.push({spot,target});
  });
  const fixtures=new THREE.Group();
  const fixtureGeometry=new THREE.SphereGeometry(.48,8,6);
  const fixtureMaterial=new THREE.MeshBasicMaterial({color:'#fff0ca',toneMapped:false});
  const lamps=new THREE.InstancedMesh(fixtureGeometry,fixtureMaterial,stagePlan.fixtures.length);
  stagePlan.fixtures.forEach((fixture,index)=>{
    const matrix=new THREE.Matrix4().makeTranslation(
      fixture.position[0],fixture.position[2],fixture.position[1]);
    lamps.setMatrixAt(index,matrix);
  });
  lamps.instanceMatrix.needsUpdate=true;fixtures.add(lamps);
  scene.add(fixtures);
  const setProfile=async next=>{
    if(next!=='day'&&next!=='night') throw new Error('Unknown natural lighting profile.');
    const token=++generation;
    let loaded;
    try {
      loaded=await new RGBELoader().loadAsync(new URL(
        next==='day'?'hdri/kloofendal_48d_partly_cloudy_puresky_2k.hdr':
          'hdri/kloppenheim_07_puresky_2k.hdr',root).href);
      loaded.mapping=THREE.EquirectangularReflectionMapping;
      const baked=generator.fromEquirectangular(loaded);
      if(disposed||token!==generation){baked.dispose();loaded.dispose();return;}
      environment?.dispose(); hdri?.dispose();
      hdri=loaded; environment=baked;
      scene.background=hdri; scene.environment=environment.texture;
      scene.environmentIntensity=next==='day'?.62:.23;
      scene.fog=new THREE.Fog(next==='day'?'#c0d1d6':'#15191b',
        next==='day'?680:620,next==='day'?1500:1280);
      renderer.toneMappingExposure=next==='day'?.98:.72;
      ambient.intensity=next==='day'?.47:.12;
      floodFill.intensity=next==='night'?.30:0;
      sun.intensity=next==='day'?2.15:0;
      if(next==='day') {
        sun.position.copy(shadowCenter).add(sunnyDirection(hdri,THREE).multiplyScalar(shadowRadius*2));
        sun.target.position.copy(shadowCenter);
      }
      const mobile=(window.matchMedia?.('(max-width: 767px)').matches) ||
        (window.devicePixelRatio||1)>2;
      sun.castShadow=next==='day';
      sun.shadow.mapSize.set(mobile?2048:4096,mobile?2048:4096);
      sun.shadow.camera.left=-shadowRadius; sun.shadow.camera.right=shadowRadius;
      sun.shadow.camera.top=shadowRadius; sun.shadow.camera.bottom=-shadowRadius;
      sun.shadow.camera.near=1; sun.shadow.camera.far=shadowRadius*4;
      sun.shadow.bias=-.00016; sun.shadow.normalBias=.035; sun.shadow.radius=3.5;
      sun.shadow.camera.updateProjectionMatrix();
      spots.forEach(({spot})=>{spot.intensity=next==='night'?spot.userData.onIntensity:0;});
      fixtures.visible=next==='night';
      profile=next;
      onProfileChange(next);
    } catch(error) {
      loaded?.dispose();
      if(next==='day') throw new Error(`Daylight HDRI failed to load locally: ${error.message}`);
      throw new Error(`Floodlight-night HDRI failed to load locally: ${error.message}`);
    }
  };
  try { await setProfile(profile); }
  catch(error) {
    generator.dispose();
    scene.remove(sky,fixtures); spots.forEach(({spot,target})=>scene.remove(spot,spot.target,target));
    fixtureGeometry.dispose();fixtureMaterial.dispose();throw error;
  }
  return {
    setProfile,
    get profile(){return profile;},
    dispose(){
      if(disposed)return;
      disposed=true;generation++;environment?.dispose();hdri?.dispose();
      generator.dispose();
      scene.environment=null;scene.background=null;scene.remove(sky,fixtures);
      spots.forEach(({spot,target})=>scene.remove(spot,target));
      fixtureGeometry.dispose();fixtureMaterial.dispose();
    },
  };
}
