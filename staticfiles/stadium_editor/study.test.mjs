import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import * as THREE from './stage/vendor/three.module.js';
import {applyStudyCamera, projectStudy, dortmundAdapter} from './study_camera.js';
import {selectDeclaredSources, createStudyLighting} from './study_lighting.js';
import {createStudyShadowProbe} from './study_shadows.js';

test('shared field has identical projection, full visibility and responsive scaling', () => {
  for (const concept of ['perspective','cutaway']) for (const width of [1880,700,330]) {
    const a=new THREE.PerspectiveCamera(),b=new THREE.PerspectiveCamera(),height=width/2;
    applyStudyCamera(a,concept,width,height);applyStudyCamera(b,concept,width,height);
    for(const [x,y] of [[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34],[0,0],[16,10]]) {
      const p=projectStudy(a,width,height,x,y),q=projectStudy(b,width,height,x,y);
      assert.deepEqual(p,q);assert.ok(p.x>=0&&p.x<=width&&p.y>=0&&p.y<=height);
    }
  }
});
test('Unity original pitch dimensions map to canonical field without a reflection', () => {
  const adapter=dortmundAdapter();adapter.updateMatrixWorld(true);
  assert.ok(adapter.matrixWorld.determinant()>0);
  for(const [x,z] of [[34.080013275146484,52.95001220703125],[-34.080013275146484,-52.95001220703125]]) {
    const p=adapter.localToWorld(new THREE.Vector3(x,0,z));
    assert.ok(Math.abs(Math.abs(p.x)-52.5)<1e-8);
    assert.ok(Math.abs(Math.abs(p.z)-34)<1e-8);
  }
});
const evidence=JSON.parse(fs.readFileSync(new URL('./study_assets/dortmund_lights.json',import.meta.url)));
test('selected runtime lights are actual declared fixtures, never centroids', () => {
  const selected=selectDeclaredSources(evidence.verifiedFixtures);
  assert.ok(selected.length>0&&selected.length<=12);
  const ids=new Set(evidence.verifiedFixtures.map(f=>f.id)),covered=[];
  for(const f of selected) {
    const original=evidence.verifiedFixtures.find(v=>v.id===f.id);
    assert.deepEqual(f.position,original.position);assert.deepEqual(f.direction,original.direction);
    assert.ok(f.meshDistance<=1&&f.reachesPitch&&f.sourceEnabled);
    f.representedIds.forEach(id=>{assert.ok(ids.has(id));covered.push(id);});
  }
  assert.equal(new Set(covered).size,ids.size);
});
test('missing or unverified lamp evidence never creates generic fallback lights', () => {
  assert.deepEqual(selectDeclaredSources([]),[]);
  assert.throws(()=>selectDeclaredSources([{...evidence.verifiedFixtures[0],verified:false}]));
});
test('source origins follow model transforms; field stays fixed and roof hiding keeps lamps', () => {
  const model=dortmundAdapter(),root=new THREE.Scene(),camera=new THREE.PerspectiveCamera();
  applyStudyCamera(camera,'cutaway',1880,940);
  const baseline=projectStudy(camera,1880,940,32,12);
  const handle={model,stage:{sceneRoot:root,renderer:{}}};
  const lighting=createStudyLighting(handle,evidence);
  lighting.setState(true,true,true);
  const before=lighting.sources.map(light=>({
    position:light.position.clone(),target:light.target.position.clone(),
  }));
  model.rotation.y+=Math.PI;
  lighting.setState(true,true,true);
  lighting.sources.forEach((light,i)=>{
    const turn=v=>new THREE.Vector3(-v.x,v.y,-v.z);
    assert.ok(light.position.distanceTo(turn(before[i].position))<1e-8);
    assert.ok(light.target.position.distanceTo(turn(before[i].target))<1e-8);
    assert.ok(light.position.distanceTo(before[i].position)>1);
  });
  model.scale.multiplyScalar(1.2);
  model.position.set(4,0,7);
  model.visible=false;
  lighting.setState(true,true,true);
  for(const source of lighting.sources) {
    const expected=model.localToWorld(new THREE.Vector3(...source.userData.fixture.position));
    assert.ok(source.position.distanceTo(expected)<1e-8);
    assert.ok(source.intensity>0);
  }
  assert.deepEqual(projectStudy(camera,1880,940,32,12),baseline);
  lighting.setState(false,false,false);
  assert.ok(lighting.sources.every(source=>source.intensity===0));
  lighting.setState(false,false,true);
  assert.ok(lighting.sources.every(source=>source.intensity>0));
  lighting.dispose();
});
test('alignment audit checks loaded lamp material/vertices and rejects stale origins or targets', () => {
  const fixture={...evidence.verifiedFixtures[0],position:[10,20,30],direction:[-1,-1,0],
    meshDistance:.2};
  const model=dortmundAdapter(),root=new THREE.Scene();
  root.add(model);
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute([10,20.2,30],3));
  geometry.setIndex([0]);geometry.addGroup(0,1,0);
  const material=new THREE.MeshStandardMaterial();
  material.userData.sourceMaterial=fixture.nearestLampMesh.material;
  const mesh=new THREE.Mesh(geometry,material);
  mesh.userData.sourcePathId=fixture.nearestLampMesh.meshPathId;
  model.add(mesh);
  const lighting=createStudyLighting({model,allMeshes:[mesh],
    stage:{sceneRoot:root,renderer:{}}},{verifiedFixtures:[fixture]});
  lighting.setState(true,true);
  assert.equal(lighting.inspectAlignment().length,1);
  model.rotation.y+=Math.PI;
  assert.throws(()=>lighting.inspectAlignment(),/ausrichtung/);
  lighting.setState(true,false);
  assert.equal(lighting.inspectAlignment()[0].originError,0);
  lighting.sources[0].target.position.x+=2;
  assert.throws(()=>lighting.inspectAlignment(),/ausrichtung/);
  lighting.setState(true,false);
  material.userData.sourceMaterial='unverified';
  assert.throws(()=>lighting.inspectAlignment(),/ausrichtung/);
  lighting.dispose();geometry.dispose();material.dispose();
});
test('isolated shadows use existing roofs and declared lights; caster control preserves visibility and restores defaults', () => {
  const root=new THREE.Scene(),roof=new THREE.Mesh(new THREE.BoxGeometry(),
    new THREE.MeshStandardMaterial({side:THREE.DoubleSide}));
  root.add(roof);
  const light=new THREE.SpotLight();light.distance=150;light.userData.sourceId='declared';
  const handle={roofMeshes:[roof],stage:{sceneRoot:root,
    renderer:{shadowMap:{enabled:false,type:THREE.BasicShadowMap}}}};
  let audits=0;
  const lighting={sources:[light],inspectAlignment(){audits++;}};
  const probe=createStudyShadowProbe(handle,lighting);
  assert.equal(audits,1);
  assert.equal(light.castShadow,false);
  probe.setState(true);
  assert.equal(probe.inspect().visibleRoofCasters,1);
  assert.equal(light.castShadow,true);
  assert.equal(roof.material.clipShadows,true);
  assert.equal(roof.material.shadowSide,THREE.DoubleSide);
  assert.equal(light.shadow.mapSize.x,2048);
  assert.equal(light.shadow.camera.far,150);
  probe.setState(true,false);
  assert.equal(probe.inspect().visibleRoofCasters,0);
  assert.equal(roof.visible,true);
  assert.equal(light.castShadow,true);
  roof.visible=false;
  probe.setState(true);
  assert.equal(probe.inspect().visibleRoofCasters,0);
  probe.dispose();
  assert.equal(handle.stage.renderer.shadowMap.enabled,false);
  assert.equal(handle.stage.renderer.shadowMap.type,THREE.BasicShadowMap);
  assert.equal(roof.castShadow,false);
  assert.equal(roof.receiveShadow,false);
  assert.equal(roof.material.clipShadows,false);
  assert.equal(roof.material.shadowSide,null);
  assert.equal(light.castShadow,false);
  assert.throws(()=>createStudyShadowProbe(handle,{sources:[]}),/deklarierte/);
  roof.geometry.dispose();roof.material.dispose();
});
