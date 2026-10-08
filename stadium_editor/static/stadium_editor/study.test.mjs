import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import * as THREE from './stage/vendor/three.module.js';
import {applyStudyCamera, projectStudy, dortmundAdapter} from './study_camera.js';
import {selectDeclaredSources, createStudyLighting} from './study_lighting.js';

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
