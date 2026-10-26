import assert from 'node:assert/strict';
import test from 'node:test';
import {canonicalGrassUv} from './grass_surface_study.js';
import {PITCH, buildPitchLayout} from './stage/pitch_geometry.js';

test('full-field UVs retain canonical 105 by 68 metres and orientation',()=>{
  assert.deepEqual(PITCH,{length:105,width:68});
  assert.deepEqual(canonicalGrassUv(52.5,-34),[0,0]);
  assert.deepEqual(canonicalGrassUv(-52.5,34),[1,1]);
  assert.deepEqual(canonicalGrassUv(0,0),[.5,.5]);
});
test('shared stripe boundaries have continuous UVs, never per-stripe repeats',()=>{
  const layout=buildPitchLayout(0);
  for(let i=0;i<layout.stripes.length-1;i++){
    const a=layout.stripes[i].quad[1],b=layout.stripes[i+1].quad[0];
    assert.deepEqual(canonicalGrassUv(...a),canonicalGrassUv(...b));
  }
  assert.equal(layout.lines.length,17);
  assert.equal(layout.radius,9.15);
});
