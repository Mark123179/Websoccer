import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {elevationSampler, drapeTriangles, drapeLines}
  from '../static/stadium_editor/measured_ground.js';
import {buildDortmundSurroundings}
  from '../static/stadium_editor/dortmund_surroundings.js';
import {inspectSurroundings} from '../surroundings_preflight.mjs';

const grid = {origin:[-600,-600],step:100,cols:13,rows:13,
  values:Array.from({length:169},(_,k)=>-2+(k%13)*.1+Math.floor(k/13)*.2),
  source:'Test-only surveyed plane'};
const hole = [[-10,-10],[10,-10],[10,10],[-10,10]];
const data = {groundLevel:2.1,groundCutout:hole,groundElevation:grid};
const editor = points => points.map(([x,z])=>[z,-x]);
const square = (x,z,n=10) => [[x,z],[x+n,z],[x+n,z+n],[x,z+n]];
const area = vertices => {
  let result=0;
  for(let i=0;i<vertices.length;i+=9)
    result+=Math.abs((vertices[i+3]-vertices[i])*(vertices[i+8]-vertices[i+2])-
      (vertices[i+5]-vertices[i+2])*(vertices[i+6]-vertices[i]))/2;
  return result;
};

test('grid is opt-in, bounded, attributed and never extrapolated',()=>{
  assert.equal(elevationSampler(null)(999999,999999),0);
  const sample=elevationSampler(grid);
  assert.ok(Math.abs(sample(0,0)+.2)<1e-9);
  assert.throws(()=>sample(601,0),/Abdeckung/);
  for(const bad of [null,{...grid,source:''},{...grid,cols:258},
    {...grid,step:0},{...grid,values:[0]},{...grid,values:grid.values.map((n,i)=>i? n:NaN)}])
    assert.equal(inspectSurroundings({...data,groundElevation:bad}).ok,false);
  assert.equal(inspectSurroundings({groundElevation:grid}).ok,false);
  assert.equal(inspectSurroundings({...data,trees:editor([[590,0]])}).ok,false,
    'coverage includes the renderer ground margin, not only source vertices');
});

test('draped triangles preserve full source area and use the exact grid cell planes',()=>{
  const varied={...grid,values:grid.values.map((n,k)=>n+(k%3)*.7)};
  const sample=elevationSampler(varied);
  const source=[-250,0,-125, 220,0,-125, 30,0,320];
  const before=JSON.stringify(source);
  const draped=drapeTriangles(source,varied,sample);
  assert.ok(draped.length>source.length);
  assert.ok(Math.abs(area(draped)-area(source))<1e-6);
  assert.equal(JSON.stringify(source),before);
  for(let i=0;i<draped.length;i+=9) {
    const x=(draped[i]+draped[i+3]+draped[i+6])/3;
    const z=(draped[i+2]+draped[i+5]+draped[i+8])/3;
    const y=(draped[i+1]+draped[i+4]+draped[i+7])/3;
    assert.ok(Math.abs(y-sample(x,z))<1e-6,'every interior point stays on its terrain plane');
  }
  const lines=drapeLines([-250,1,-125,220,1,320],varied,sample);
  for(let i=0;i<lines.length;i+=6){
    const x=(lines[i]+lines[i+3])/2,z=(lines[i+2]+lines[i+5])/2;
    assert.ok(Math.abs((lines[i+1]+lines[i+4])/2-1-sample(x,z))<1e-6);
  }
});

test('real renderer keeps cutout open and every OSM surface on terrain without source edits',()=>{
  const input={...data,green:[editor(square(100,100,40))],
    roads:[{p:editor([[100,160],[170,170]]),w:2}],
    buildings:[editor(square(200,100,20))],buildingHeights:[8],trees:editor([[150,120]])};
  const before=JSON.stringify(input),env=buildDortmundSurroundings(THREE,input);
  try {
    assert.equal(inspectSurroundings(input).ok,true);
    const sample=elevationSampler(grid);
    for(const name of ['ENV_GROUND','ENV_GREEN','ENV_ROADS']){
      const position=env.group.getObjectByName(name).geometry.getAttribute('position');
      const expected=name==='ENV_GROUND'?-.35:name==='ENV_GREEN'?-.18:-.12;
      for(let i=0;i<position.count;i++)
        assert.ok(Math.abs(position.getY(i)-sample(position.getX(i),position.getZ(i))-expected)<1e-5);
      if(name==='ENV_GROUND')for(let i=0;i<position.count;i+=3){
        const x=(position.getX(i)+position.getX(i+1)+position.getX(i+2))/3;
        const z=(position.getZ(i)+position.getZ(i+1)+position.getZ(i+2))/3;
        assert.ok(!(x>-10&&x<10&&z>-10&&z<10),'no triangle in bowl');
      }
    }
    const matrix=new THREE.Matrix4();
    env.group.getObjectByName('ENV_TREE_TRUNKS').getMatrixAt(0,matrix);
    assert.ok(Math.abs(matrix.elements[13]-1.02-sample(150,120))<1e-6);
    assert.equal(JSON.stringify(input),before);
  }finally{env.dispose();}
});
