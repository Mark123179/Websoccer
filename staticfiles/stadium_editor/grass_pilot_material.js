/** Approved grass study, shared by the isolated pilot and editor previews.
 * Canonical pitch coordinates, not per-stripe UVs.
 */
import * as THREE from 'three';

export const GRASS_PRESETS = Object.freeze({
  A1: [1, 1, 1], A2: [2, 1, 1], A3: [3, 1, 1], A4: [4, 1, 1],
  B1: [1, 2, 1], B2: [1, 3, 1], B3: [1, 4, 1],
  C1: [1, 1, 2], C2: [1, 1, 3],
  D1: [2, 2, 2], D2: [3, 3, 1], D3: [4, 4, 3],
});
const TONES = [[0, 1, 1], [-6, .96, 1.03], [-10, .90, 1.095], [-14, .72, 1.06]];
const WEAR = [[0, 0], [.6, 0], [1, 1]];

function toneMatrix(degrees, saturation, brightness) {
  const a = degrees * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
  const to = new THREE.Matrix3().set(.299,.587,.114,.596,-.274,-.322,.211,-.523,.312);
  const from = new THREE.Matrix3().set(1,.956,.621,1,-.272,-.647,1,-1.106,1.703);
  const rotation = new THREE.Matrix3().set(1,0,0,0,c*saturation,-s*saturation,0,s*saturation,c*saturation);
  return from.multiply(rotation).multiply(to).multiplyScalar(brightness);
}

// Original study's field-metre pattern, tint and wear calculations.
const FRAGMENT = `
varying vec2 vGrassUv;
uniform sampler2D uBasis;
uniform sampler2D uWear;
uniform int uPattern;
uniform mat3 uTone;
uniform float uMatt;
uniform float uEarth;
float grassHash(vec2 p) {return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float grassNoise(vec2 p) {
 vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
 return mix(mix(grassHash(i),grassHash(i+vec2(1,0)),f.x),
 mix(grassHash(i+vec2(0,1)),grassHash(i+vec2(1,1)),f.x),f.y);
}
float grassWave(float a,float w,vec2 m) {
 a+=(grassNoise(m*.9)-.5)*.06;
 float k=PI*.175/w;
 return smoothstep(-k,k,sin(PI*a))*2.0-1.0;
}
vec3 pilotGrass(vec2 uv) {
 vec2 m=uv*vec2(105.0,68.0);
 float s1=0.0,s2=0.0,s=0.0,amp=.085;
 if(uPattern==1){s1=grassWave(m.x/7.5,7.5,m);s=s1;}
 else if(uPattern==2){s2=grassWave(m.y/8.5,8.5,m);s=s2;}
 else if(uPattern==3){
  s1=grassWave(m.x/7.5,7.5,m);s2=grassWave(m.y/8.5,8.5,m);s=s1*s2;
 }else{
  vec2 d=vec2(m.x+m.y,m.x-m.y)/(7.5*1.41421356);
  s=grassWave(d.x,7.5,m)*grassWave(d.y,7.5,m);amp*=.6;
 }
 vec2 t1=m/8.0,t2=vec2(m.y,-m.x)/19.0,t1f=t1;
 if(s1<0.0||(uPattern==1&&s<0.0))t1f.y=-t1f.y;
 if(s2<0.0)t1f.x=-t1f.x;
 vec3 basis=mix(mix(texture2D(uBasis,t1).rgb,texture2D(uBasis,t1f).rgb,
 clamp(.5-.5*s,0.0,1.0)),texture2D(uBasis,t2).rgb,.4);
 basis*=1.0+.06*(grassNoise(m/12.0+3.7)-.5)*2.0;
 vec3 mask=texture2D(uWear,uv).rgb;
 float matt=mask.r*uMatt,earth=mask.g*uEarth;
 amp*=1.0-.85*matt;
 vec3 col=uTone*(basis*(1.0+amp*s));
 vec3 worn=col*vec3(1.35,.98,.70);
 worn=mix(worn,vec3(dot(worn,vec3(.2126,.7152,.0722))),.25);
 col=mix(col,worn,matt*.7);
 float lb=dot(basis,vec3(.2126,.7152,.0722))/
 dot(vec3(.0044,.0912,.0222),vec3(.2126,.7152,.0722));
 return mix(col,vec3(.070,.056,.040)*(.6+.8*lb),earth);
}`;

export async function createGrassPilotMaterial(stage, assets) {
  const loader = new THREE.TextureLoader();
  const results = await Promise.allSettled([
    loader.loadAsync(assets.basis), loader.loadAsync(assets.abnutzung),
  ]);
  if (results.some(result => result.status === 'rejected')) {
    results.forEach(result => { if (result.status === 'fulfilled') result.value.dispose(); });
    throw new Error('Die gelieferten Rasenlagen konnten nicht geladen werden.');
  }
  const [basis, wear] = results.map(result => result.value);
  basis.colorSpace = THREE.SRGBColorSpace;
  basis.wrapS = basis.wrapT = THREE.RepeatWrapping;
  basis.anisotropy = Math.min(4, stage.renderer.capabilities.getMaxAnisotropy());
  wear.colorSpace = THREE.NoColorSpace;
  const uniforms = {
    uBasis: {value: basis}, uWear: {value: wear}, uPattern: {value: 1},
    uTone: {value: toneMatrix(0,1,1)}, uMatt: {value: 0}, uEarth: {value: 0},
  };
  const material = stage.grassUnlit
    ? new THREE.MeshBasicMaterial({color: 0xffffff, side: THREE.DoubleSide})
    : new THREE.MeshLambertMaterial({color: 0xffffff, side: THREE.DoubleSide});
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = 'varying vec2 vGrassUv;\n' + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>',
      '#include <begin_vertex>\nvGrassUv=' + (stage.grassProjection ||
        'vec2((52.5-position.x)/105.0,(position.z+34.0)/68.0)') + ';');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <map_pars_fragment>', '#include <map_pars_fragment>\n' + FRAGMENT)
      .replace('#include <map_fragment>', 'diffuseColor.rgb *= pilotGrass(vGrassUv);');
  };
  material.customProgramCacheKey = () => 'blueprint-grass-v2:' + (stage.grassProjection || 'canonical');
  const original = stage.pitchTargets
    ? stage.pitchTargets.map(({mesh, slot}) => ({
      mesh, slot, material: slot === undefined ? mesh.material : mesh.material[slot],
    })) : [];
  if (!stage.pitchTargets) stage.sceneRoot.traverse(mesh => {
    if (mesh.isMesh && stage.pitchMaterials.has(mesh.material))
      original.push({mesh, material: mesh.material});
  });
  const assign = (row, next) => {
    if (row.slot === undefined) row.mesh.material = next;
    else row.mesh.material[row.slot] = next;
  };
  if (!original.length) {
    basis.dispose(); wear.dispose(); material.dispose();
    throw new Error('Das kanonische Spielfeld fehlt; keine Ersatzfläche erzeugt.');
  }
  function select(id) {
    if (id === 'bestand') {
      original.forEach(row => assign(row, row.material));
      return;
    }
    const preset = GRASS_PRESETS[id];
    if (!preset) throw new Error('Unbekannte Rasenvariante.');
    const [pattern, tone, condition] = preset;
    uniforms.uPattern.value = pattern;
    uniforms.uTone.value.copy(toneMatrix(...TONES[tone - 1]));
    [uniforms.uMatt.value, uniforms.uEarth.value] = WEAR[condition - 1];
    original.forEach(row => assign(row, material));
  }
  return {select, dispose() {
    select('bestand'); material.dispose(); basis.dispose(); wear.dispose();
  }};
}
