import assert from 'node:assert/strict';
import test from 'node:test';
import {canonicalGrassUv} from './grass_surface_study.js';
import {PITCH, buildPitchLayout} from './stage/pitch_geometry.js';
import {inspectGrassSamples, GRASS_REFERENCES} from './grass_surface_diagnostic.js';
import {checkGrassRender} from '../../../scripts/check_grass_render.mjs';

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

test('pixel oracle rejects missing, invisible and non-finite reference samples', () => {
  const valid = GRASS_REFERENCES.map(([, , color]) => ({
    visible: true, rgb: color.slice(1).match(/../g).map(hex => parseInt(hex, 16)),
  }));
  assert.equal(inspectGrassSamples(valid).ok, true);
  assert.throws(() => inspectGrassSamples(valid.slice(1)), /Unvollständig/);
  for (const invalid of [
    {...valid[0], visible: false}, {...valid[0], rgb: [NaN, 88, 54]},
    {...valid[0], rgb: [180, 88]}, {...valid[0], rgb: [0, 0, 0]},
  ]) {
    assert.equal(inspectGrassSamples([invalid, ...valid.slice(1)]).ok, false);
  }
});

test('rendered texture orientation and sRGB survive both stadium frames; controls fail',
  {timeout: 240000}, async () => {
    const {states} = await checkGrassRender();
    assert.equal(states.length, 10);
  });
