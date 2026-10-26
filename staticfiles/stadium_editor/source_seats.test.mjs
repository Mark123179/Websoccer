import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import './source_seats.js';

const seats=globalThis.StadiumSourceSeats;
const frame={fieldC:[0,0],axisTheta:0};
const axes={NORD:'+z',WEST:'-x'};

test('native/editor registration is reversible and keeps separate tiers',()=>{
  const blocks=['UNTER','MITTEL','OBER'].map((tier,i)=>({
    id:i,tier,rows:2,seats:4,quad:[[7,15],[13,15],[13,10],[7,10]],
    rle:[[5,0],[3,1]],
  }));
  const reg=seats.registration(blocks,frame,axes);
  for(const block of reg.blocks){
    for(let r=0;r<2;r++)for(let s=0;s<4;s++){
      const p=seats.quadPoint(block.nativeQuad,(s+.5)/4,(r+.5)/2);
      const match=reg.lookup(...p,block.tier);
      assert.equal(match.block.id,block.id);
      assert.equal(match.index,r*4+s);
    }
  }
  assert.equal(reg.lookup(...seats.quadPoint(reg.blocks[0].nativeQuad,.1,.1),'OBER').block.id,2);
  assert.deepEqual([...reg.blocks[0].values],[0,0,0,0,0,1,1,1]);
});

test('real FCB source/blueprint calibration maps all three original tiers',()=>{
  // Optional local source assets are ignored in Git. On CI the smaller
  // synthetic test above remains deterministic.
  const geometryPath='/tmp/fcb-seat-geometry.json';
  const sourcePath='generated-artifacts/allianzarena-bodendetails-korrigiert/bayern/stadium-models/915/7bc8ec0fcf20c166/geometry.bin';
  let geometry,raw;
  try{geometry=JSON.parse(readFileSync(geometryPath));raw=readFileSync(sourcePath);}
  catch{return;}
  const manifest=JSON.parse(readFileSync('stadium_editor/blueprints/v2/models/915.json'));
  const index=seats.sourceIndex(manifest,raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength));
  const reg=seats.registration(geometry.blocks,geometry.meta,manifest.calibration.surroundingsAxes);
  for(const tier of ['UNTER','MITTEL','OBER']){
    let matched=0,total=0;
    for(const block of reg.blocks.filter(b=>b.tier===tier))
      for(let r=0;r<block.rows;r+=2)for(let s=0;s<block.seats;s+=2){
        total++;
        const p=seats.quadPoint(block.nativeQuad,(s+.5)/block.seats,(r+.5)/block.rows);
        const source=seats.warp(p,tier,reg.ring,index.ring);
        if(source && index.sample(...source,tier))matched++;
      }
    assert.ok(matched/total>.90,`${tier}: ${matched}/${total} source seats mapped`);
  }
});
