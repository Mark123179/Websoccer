import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,statSync} from 'node:fs';
import * as THREE from './stage/vendor/three.module.js';
import {buildNaturalSurroundings} from './natural_surroundings.js';
import {buildMappedVegetationRepresentatives,buildParkingPoints,createImpostorMaterial} from './natural_surroundings_v2.js';

const packageSource=JSON.parse(readFileSync(new URL('../../blueprints/natural/dortmund.json',import.meta.url),'utf8'));
const manifest=JSON.parse(readFileSync(new URL('./natural_assets/library_v2.json',import.meta.url),'utf8'));
const bakeManifest=JSON.parse(readFileSync(new URL('./natural_assets/atlases/bake-manifest.json',import.meta.url),'utf8'));
const inSourcePolygon=(x,z,raw)=>{
  const ring=Array.isArray(raw)?raw:raw.poly||raw.p;let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const a=[ring[i][1],ring[i][0]],b=[ring[j][1],ring[j][0]];
    if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])inside=!inside;
  }
  return inside;
};

test('visualVersion 2 keeps pitch-frame coordinates direct, uses source atlases, and disposes cleanly',async()=>{
  const data=structuredClone(packageSource);
  data.data.parking=[];
  const expected=data.data.buildings[0][0];
  const oldFetch=globalThis.fetch,oldLoad=THREE.TextureLoader.prototype.loadAsync;
  const loaded=[],texturesByUrl=new Map();
  globalThis.fetch=async url=>({ok:true,status:200,json:async()=>manifest});
  THREE.TextureLoader.prototype.loadAsync=async function(url){
    const texture=new THREE.DataTexture(new Uint8Array([180,180,180,255]),1,1);
    texture.needsUpdate=true;loaded.push(String(url));texturesByUrl.set(String(url),texture);return texture;
  };
  try{
    const scene=await buildNaturalSurroundings(THREE,data,{
      assetBase:'https://local.test/natural_assets/',
      camera:{position:new THREE.Vector3(-300,150,0)},
    });
    const walls=scene.group.getObjectByName('NATURAL_BUILDING_WALLS');
    const positions=walls.geometry.attributes.position.array;
    const [fieldX,fieldY]=expected;
    assert.ok([...positions].some((value,index)=>index%3===0&&Math.abs(value-fieldY)<.001));
    assert.ok([...positions].some((value,index)=>index%3===2&&Math.abs(value-fieldX)<.001));
    assert.equal(scene.metrics.mappedTreeNodes,334);
    assert.equal(scene.metrics.trees,334+scene.metrics.forestRepresentatives);
    assert.equal(scene.metrics.treeImpostorInstances,scene.metrics.trees);
    assert.equal(scene.metrics.shrubImpostorInstances,scene.metrics.scrubRepresentatives);
    assert.equal(scene.metrics.treeMeshInstances,0);
    assert.equal(scene.metrics.mappedParkingLots,0);
    assert.ok(scene.group.getObjectByName('NATURAL_MAPPED_GREEN_AERIAL'));
    assert.ok(scene.group.getObjectByName('NATURAL_MAPPED_SPORTS_TARTAN'));
    const pitch=scene.group.getObjectByName('NATURAL_MAPPED_SPORTS_TURF');
    assert.equal(pitch.material.map,texturesByUrl.get('https://local.test/natural_assets/surfaces/grass_ground_color_2k.jpg'));
    assert.notEqual(pitch.material.color.getHexString(),'ffffff');
    assert.equal(scene.group.getObjectByName('NATURAL_GROUND_BASE').material.map,null);
    assert.ok(scene.group.getObjectByName('NATURAL_BUILDING_ROOFS'));
    assert.equal(scene.group.userData.sourceDetail.source,'OpenStreetMap, api.openstreetmap.org/api/0.6/map');
    assert.ok(loaded.some(url=>url.endsWith('aerial_grass_rock_color_2k.jpg')));
    assert.ok(loaded.some(url=>url.endsWith('grass_ground_color_2k.jpg')));
    assert.ok(loaded.some(url=>url.endsWith('forest_deciduous_shrub_2048.webp')));
    scene.updateLOD({position:new THREE.Vector3(-300,150,80)});
    const trees=scene.group.children.find(child=>child.name==='NATURAL_TREE_IMPOSTORS_realistic-oak-large');
    assert.ok(trees);
    assert.equal(trees.castShadow,true);
    assert.equal(trees.receiveShadow,true);
    assert.equal(trees.material.color.getHexString(),'000000');
    assert.equal(trees.material.emissive.getHexString(),'ffffff');
    assert.equal(trees.material.map,trees.material.emissiveMap);
    scene.dispose();scene.dispose();
    assert.equal(scene.group.children.length,0);
  }finally{
    globalThis.fetch=oldFetch;
    THREE.TextureLoader.prototype.loadAsync=oldLoad;
  }
});

test('tree impostors output baked albedo with shadow mask and alpha-tested cast shadows',()=>{
  const atlas=new THREE.DataTexture(new Uint8Array([30,47,18,255]),1,1);
  const view={value:17},foliage=createImpostorMaterial(THREE,atlas,view);
  const depth=createImpostorMaterial(THREE,atlas,view,true);
  const shader={uniforms:{},vertexShader:'#include <uv_vertex>',
    fragmentShader:'#include <map_fragment>\n#include <emissivemap_fragment>\nvec3 outgoingLight=vec3(1.0);\n#include <opaque_fragment>'};
  foliage.onBeforeCompile(shader);
  assert.match(shader.fragmentShader,/texture2D\(emissiveMap,\s*atlasUv\)/);
  assert.match(shader.fragmentShader,/outgoingLight \*=\s*mix\(0\.56,\s*1\.0,\s*getShadowMask\(\)\)/);
  assert.match(shader.fragmentShader,/texture2D\(map,\s*atlasUv\)/);
  assert.equal(depth.map,atlas);
  assert.equal(depth.alphaTest,.26);
  assert.equal(foliage.transparent,false);
  foliage.dispose();depth.dispose();atlas.dispose();
});

test('mapped vegetation is deterministic, contained to forest/scrub, and clear',()=>{
  const data=structuredClone(packageSource.data),originalTrees=structuredClone(data.trees);
  const first=buildMappedVegetationRepresentatives(data);
  const second=buildMappedVegetationRepresentatives(data);
  assert.deepEqual(first,second);
  assert.deepEqual(data.trees,originalTrees);
  assert.equal(data.trees.length,334);
  assert.ok(first.forest.length>0,'the mapped forest includes visible source representatives');
  assert.ok(first.scrub.length>0,'the mapped scrub includes source shrubs');
  assert.equal(first.forest.length,4);
  assert.equal(first.scrub.length,26);
  assert.ok(first.forest.every(point=>Math.hypot(point.x,point.z)<=440));
  assert.ok(first.scrub.every(point=>Math.hypot(point.x,point.z)<=440));
  first.forest.forEach(point=>assert.ok(data.forest.some(poly=>inSourcePolygon(point.x,point.z,poly))));
  first.scrub.forEach(point=>assert.ok(data.scrub.some(poly=>inSourcePolygon(point.x,point.z,poly))));
  for(const point of [...first.forest,...first.scrub]){
    assert.ok(!data.grassTagged.filter(item=>['grass','grassland'].includes(item.kind))
      .some(poly=>inSourcePolygon(point.x,point.z,poly)));
    assert.ok(!data.sports.some(poly=>inSourcePolygon(point.x,point.z,poly)));
    assert.ok(!data.buildings.some(poly=>inSourcePolygon(point.x,point.z,poly)));
    assert.ok(!data.trees.some(([x,z])=>Math.hypot(point.x-z,point.z-x)<2.5));
  }
  const combined=[...first.forest,...first.scrub];
  for(let i=0;i<combined.length;i++)for(let j=i+1;j<combined.length;j++)
    assert.ok(Math.hypot(combined[i].x-combined[j].x,combined[i].z-combined[j].z)>=2.5);
  assert.equal(manifest.shrubs[0].source,'various_forest_assets_pack/DeciduousShrub_27');
});

test('cars fill only explicit surface lots at a seeded 70% of valid 2.5×5m bays',()=>{
  const data=structuredClone(packageSource.data);
  const vegetation=buildMappedVegetationRepresentatives(data);
  const first=buildParkingPoints(data,vegetation);
  const second=buildParkingPoints(data,vegetation);
  assert.deepEqual(first,second);
  assert.equal(first.lots,data.parking.filter(item=>item.parking==='surface').length);
  assert.equal(first.lots,14);
  assert.equal(first.rejectedNonSurfaceLots,data.parking.length-first.lots);
  assert.equal(first.rejectedNonSurfaceLots,6);
  assert.ok(first.eligibleBays>0);
  assert.equal(first.eligibleBays,1419);
  assert.equal(first.points.length,975);
  assert.ok(first.points.length/first.eligibleBays>=.6);
  assert.ok(first.points.length/first.eligibleBays<=.8);
  assert.ok(Math.abs(first.points.length/first.eligibleBays-.6871)<.0001);
  assert.ok(first.points.every(point=>{
    const feature=data.parking.find(item=>item.id===point.parkingId);
    return feature?.parking==='surface'&&
      [[point.x-1.2,point.z-2.3],[point.x+1.2,point.z-2.3],
        [point.x-1.2,point.z+2.3],[point.x+1.2,point.z+2.3]]
        .every(([x,z])=>inSourcePolygon(x,z,feature.poly))&&
      [...data.trees.map(([x,z])=>[z,x]),...vegetation.forest.map(item=>[item.x,item.z]),
        ...vegetation.scrub.map(item=>[item.x,item.z])]
        .every(([x,z])=>Math.hypot(point.x-x,point.z-z)>=2.5);
  }));
});

test('tree and shrub alpha WebP atlases preserve the 2048 8×8 grid',()=>{
  assert.equal(bakeManifest.atlasSize,2048);
  assert.equal(bakeManifest.viewLayout,'8x8 hemi-octahedron');
  assert.equal(bakeManifest.results.length,6);
  for(const result of bakeManifest.results){
    assert.equal(result.width,2048);
    assert.equal(result.height,2048);
    assert.equal(result.views,64);
    assert.equal(result.format,'RGBA WebP alpha');
    const path=new URL(`./natural_assets/atlases/${result.file}`,import.meta.url);
    const bytes=readFileSync(path);
    assert.equal(bytes.toString('ascii',0,4),'RIFF');
    assert.equal(bytes.toString('ascii',8,12),'WEBP');
    assert.equal(bytes.toString('ascii',12,16),'VP8X');
    assert.ok(bytes[20]&0x10,'the WebP extended-header alpha flag is required');
    assert.equal(statSync(path).size,result.bytes);
  }
});

test('version-2 package refuses unverified model mirroring and invalid source polygons',async()=>{
  const invalid=structuredClone(packageSource);
  invalid.model.mirror=true;
  await assert.rejects(()=>buildNaturalSurroundings(THREE,invalid,{
    assetBase:'https://local.test/natural_assets/',
  }),/has not been verified/);
  const bad=structuredClone(packageSource);
  bad.data.trees[0]=[NaN,1];
  await assert.rejects(()=>buildNaturalSurroundings(THREE,bad,{
    assetBase:'https://local.test/natural_assets/',
  }),/trees\[0\] is invalid/);
});
