import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings} from '../static/stadium_editor/dortmund_surroundings.js';
import {inspectSurroundings} from '../surroundings_preflight.mjs';

const editor = p => p.map(([x,z])=>[z,-x]);
const rect = (x,z,w,h) => editor([[x,z],[x+w,z],[x+w,z+h],[x,z+h]]);
function fixture() {
  const part = (lodId,poly,baseNHN,height) => ({
    lodId,file:'official.gml',polygons:[poly],baseNHN,height,roofNHN:baseNHN+height,
    srsName:'urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH',
    sourceAttributes:{DatenquelleDachhoehe:'1000',DatenquelleBodenhoehe:'1100'},
  });
  return {
    groundLevel:2.1,groundCutout:[[-10,-10],[10,-10],[10,10],[-10,10]],
    groundElevation:{origin:[-600,-600],step:100,cols:13,rows:13,
      values:Array.from({length:169},(_,i)=>-2+(i%13)*.2),source:'Test DGM'},
    buildings:[rect(100,100,30,20),rect(200,100,20,20)],
    buildingHeights:[6,8],buildingIds:['way/test','way/other'],
    heightEvidence:{terrainReferenceNHN:60,buildings:[
      {index:0,osm:'way/test',status:'unmeasured_retained_envelope'}]},
    buildingParts:{version:1,verticalDatum:'DHHN2016 / NHN (EPSG:7837)',
      referenceNHN:60,source:'Documented LoD2',groups:[{
        buildingIndex:0,osm:'way/test',residualStatus:'unmeasured_retained_envelope',
        parts:[part('a',rect(100,100,10,20),62,8),part('b',rect(110,100,10,20),63,11)],
        residualPolygons:[rect(120,100,10,20)],
      }]},
  };
}

function slopedFixture() {
  const data=fixture(),part=data.buildingParts.groups[0].parts[0];
  const ring=part.polygons[0].map(([x,y])=>[x,y,68+(-y-100)/5]);
  ring.push([...ring[0]]);
  part.roofMinNHN=68;
  part.roofSurfaces=[{lodId:part.lodId,file:part.file,surfaceId:'roof-a',polygonId:'polygon-a',
    sourceRingsUTM:[ring.map(([x,y,z])=>[350000+x,5640000+y,z])],polygons:[ring]}];
  return data;
}

test('surveyed slopes and eaves replace only the declared component envelope',()=>{
  const data=slopedFixture(),before=JSON.stringify(data);
  assert.equal(inspectSurroundings(data).ok,true);
  const env=buildDortmundSurroundings(THREE,data);
  try {
    const roof=env.group.getObjectByName('ENV_BUILDING_ROOFS').geometry.getAttribute('position');
    const wall=env.group.getObjectByName('ENV_BUILDINGS').geometry.getAttribute('position');
    let count=0;
    for(let i=0;i<roof.count;i+=3){
      const x=(roof.getX(i)+roof.getX(i+1)+roof.getX(i+2))/3;
      if(x<=100||x>=110)continue;
      for(let j=i;j<i+3;j++)assert.ok(Math.abs(roof.getY(j)+2.1-(8+(roof.getX(j)-100)/5))<1e-5);
      count++;
    }
    assert.equal(count,2);
    for(let i=0;i<wall.count;i+=3){
      const x=(wall.getX(i)+wall.getX(i+1)+wall.getX(i+2))/3;
      if(x<=100||x>=110)continue;
      for(let j=i;j<i+3;j++){
        const y=wall.getY(j)+2.1;
        assert.ok(Math.abs(y-2)<1e-5||Math.abs(y-(8+(wall.getX(j)-100)/5))<1e-5);
      }
    }
    assert.equal(JSON.stringify(data),before);
  }finally{env.dispose();}
});

test('invalid surveyed roof packages fail in both renderer and package preflight',()=>{
  const changes=[
    p=>p.roofSurfaces=[],
    p=>p.roofSurfaces[0].lodId='wrong',
    p=>p.roofSurfaces[0].file='wrong.gml',
    p=>p.roofSurfaces[0].surfaceId='',
    p=>p.roofSurfaces.push(structuredClone(p.roofSurfaces[0])),
    p=>p.roofSurfaces[0].polygons=[],
    p=>p.roofSurfaces[0].polygons[0][1][2]=NaN,
    p=>p.roofSurfaces[0].polygons[0][1][2]-=.5,
    p=>p.roofSurfaces[0].polygons[0][1][0]+=1,
    p=>p.roofSurfaces[0].polygons[0][0][0]+=1,
    p=>p.roofSurfaces[0].sourceRingsUTM[0][1][2]-=.5,
    p=>p.roofSurfaces[0].polygons.push(structuredClone(p.roofSurfaces[0].polygons[0])),
    p=>p.roofMinNHN=71,
  ];
  for(const change of changes){
    const data=slopedFixture();change(data.buildingParts.groups[0].parts[0]);
    assert.equal(inspectSurroundings(data).ok,false,String(change));
    assert.throws(()=>buildDortmundSurroundings(THREE,data),/buildingParts/);
  }
});

test('gable ridge is not extended to the ground as an invented internal wall',()=>{
  const data=slopedFixture(),part=data.buildingParts.groups[0].parts[0];
  part.roofSurfaces=[100,105].map((x,i)=>{
    const ring=rect(x,100,5,20).map(([a,b])=>[a,b,70-Math.abs(-b-105)*.4]);
    ring.push([...ring[0]]);
    return {lodId:part.lodId,file:part.file,surfaceId:`roof-${i}`,polygonId:`poly-${i}`,
      sourceRingsUTM:[ring.map(([a,b,c])=>[350000+a,5640000+b,c])],polygons:[ring]};
  });
  assert.equal(inspectSurroundings(data).ok,true);
  const env=buildDortmundSurroundings(THREE,data);
  try{
    const walls=env.group.getObjectByName('ENV_BUILDINGS').geometry.getAttribute('position');
    for(let i=0;i<walls.count;i+=3){
      const xs=[0,1,2].map(j=>walls.getX(i+j));
      assert.ok(!xs.every(x=>Math.abs(x-105)<1e-5),'no wall under the ridge');
    }
  }finally{env.dispose();}
});
test('real renderer uses independent NHN bases/roofs and retains residual + other OSM buildings',()=>{
  const data=fixture(),before=JSON.stringify(data);
  assert.equal(inspectSurroundings(data).ok,true);
  const env=buildDortmundSurroundings(THREE,data);
  try {
    const roofs=env.group.getObjectByName('ENV_BUILDING_ROOFS').geometry.getAttribute('position');
    const walls=env.group.getObjectByName('ENV_BUILDINGS').geometry.getAttribute('position');
    const groups=env.group.userData.buildingParts.groups;
    assert.equal(groups[0].components,2);
    for (const [x0,x1,top] of [[100,110,10],[110,120,14]]) {
      let checked=0;
      // Rectangle roof vertices sit on edges, so check triangle centroids.
      for(let i=0;i<roofs.count;i+=3){
        const x=(roofs.getX(i)+roofs.getX(i+1)+roofs.getX(i+2))/3;
        if(x>x0&&x<x1) {
          assert.ok(Math.abs(roofs.getY(i)+2.1-top)<1e-5);
          checked++;
        }
      }
      assert.ok(checked>0);
    }
    const ys=Array.from({length:walls.count},(_,i)=>walls.getY(i)+2.1);
    assert.ok(ys.some(y=>Math.abs(y-2)<1e-5),'first base is 62 NHN minus reference 60');
    assert.ok(ys.some(y=>Math.abs(y-3)<1e-5),'second base is 63 NHN minus reference 60');
    assert.ok(Array.from({length:roofs.count},(_,i)=>roofs.getX(i)).some(x=>x===130),
      'unmeasured residual remains rendered');
    assert.ok(Array.from({length:roofs.count},(_,i)=>roofs.getX(i)).some(x=>x===220),
      'unrelated OSM building remains rendered');
    assert.equal(JSON.stringify(data),before);
  } finally {env.dispose();}
});

test('malformed, ambiguous and incomplete component contracts fail closed in renderer AND preflight',()=>{
  const changes=[
    d=>d.buildingParts.referenceNHN++,
    d=>d.buildingParts.verticalDatum='ellipsoid',
    d=>d.buildingParts.groups[0].osm='way/wrong',
    d=>d.buildingParts.groups[0].buildingIndex=1,
    d=>d.buildingParts.groups.push(structuredClone(d.buildingParts.groups[0])),
    d=>d.buildingParts.groups[0].parts[1].lodId='a',
    d=>d.buildingParts.groups[0].parts[0].baseNHN=NaN,
    d=>d.buildingParts.groups[0].parts[0].roofNHN++,
    d=>d.buildingParts.groups[0].parts[0].sourceAttributes.DatenquelleDachhoehe='3000',
    d=>d.buildingParts.groups[0].parts[0].srsName='EPSG:25832',
    d=>d.buildingParts.groups[0].parts[1].polygons=[rect(100,100,10,20)],
    d=>d.buildingParts.groups[0].residualPolygons=[],
    d=>d.buildingParts.groups[0].residualPolygons=[rect(120,100,11,20)],
    d=>d.buildingParts.groups[0].parts[0].polygons=[rect(0,0,20,20)],
    d=>d.buildingParts.groups[0].parts[0].polygons=[editor([[100,100],[110,120],[100,120],[110,100]])],
    d=>d.heightEvidence.buildings[0].status='official_laser_height',
    d=>delete d.groundElevation,
  ];
  for(const change of changes){
    const data=fixture();change(data);
    assert.equal(inspectSurroundings(data).ok,false,String(change));
    assert.throws(()=>buildDortmundSurroundings(THREE,data),/buildingParts|ground/);
  }
});

test('omitting the explicit contract leaves the existing renderer unchanged',()=>{
  const data=fixture();delete data.buildingParts;
  const env=buildDortmundSurroundings(THREE,data);
  try {assert.equal(env.group.userData.buildingParts,undefined);}
  finally {env.dispose();}
});
