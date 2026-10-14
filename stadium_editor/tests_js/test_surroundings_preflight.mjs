import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings, editorPointToDortmund}
  from '../static/stadium_editor/dortmund_surroundings.js';
import {inspectSurroundings} from '../surroundings_preflight.mjs';

const hole = [[-10,-10],[10,-10],[10,10],[-10,10]];
const terrain = {groundLevel:7.7, groundCutout:hole};
const editor = points => points.map(([x,z]) => [z,-x]);
const square = (x,z,size=2) => [[x,z],[x+size,z],[x+size,z+size],[x,z+size]];

test('all conflicts reported with original indices, without source mutation', () => {
  const data = {...terrain,
    green: [editor(square(20,20)), editor([[-30,-1],[30,-1],[30,1],[-30,1]])],
    water: [editor(square(-30,-30,60))],
    roads: [{p:editor([[-30,11],[30,11]]),w:2}],
    buildings: [editor(square(30,30)), editor(square(0,0))],
    trees: editor([[30,30],[0,0],[10,0]])};
  const before = structuredClone(data);
  const report = inspectSurroundings(data);
  assert.equal(report.ok, false);
  assert.deepEqual(report.findings.map(f=>f.path),
    ['green[1]','water[0]','roads[0]','buildings[1]','trees[1]','trees[2]']);
  assert.match(report.findings[3].message, /buildings\[1\]/);
  assert.deepEqual(data, before);
});

test('inside surfaces are informational, source arrays and closed cutout remain intact', () => {
  const data = {...terrain, groundCutout:[...hole,hole[0]],
    green:[editor(square(0,0))],water:[editor(square(1,1))]};
  const before = structuredClone(data), report = inspectSurroundings(data);
  assert.equal(report.ok, true);
  assert.deepEqual(report.findings.map(f=>[f.severity,f.path,f.code]), [
    ['info','green[0]','surface_inside_cutout'],['info','water[0]','surface_inside_cutout'],
  ]);
  assert.deepEqual(data,before);
});

test('every source object has production-renderer parity including drawn joins and invalid shapes', () => {
  const cases = [
    {green:[editor(square(20,20))]},
    {green:[editor(square(0,0))]},
    {green:[editor(square(9,0))]},
    {water:[[[1,2],[3,4]]]},
    {roads:[{p:editor([[-30,11],[30,11]]),w:2}]},
    // Single point: renderer draws a join even without a line segment.
    {roads:[{p:editor([[11,0]]),w:2}]},
    {roads:[{p:editor([[-30,13],[30,13]]),w:2}]},
    {roads:[{p:editor([[30,30],[30,30]]),w:0}]},
    {buildings:[editor(square(0,0))]},
    {buildings:[editor(square(30,30))],buildingHeights:[-1]},
    {trees:editor([[0,0]])},
    {trees:editor([[30,30]])},
  ];
  for (const feature of cases) {
    const data = {...terrain,...feature};
    let accepted = true, env;
    try { env = buildDortmundSurroundings(THREE,data); }
    catch { accepted = false; }
    finally { env?.dispose(); }
    assert.equal(inspectSurroundings(data).ok, accepted, JSON.stringify(feature));
  }
});

test('rotated translated frame and all valid reflected axes use the same transform', () => {
  const frame = {fieldC:[50,-30],axisTheta:Math.PI/3};
  for (const NORD of ['+x','-x','+z','-z'])
    for (const WEST of ['+x','-x','+z','-z']) {
      if (NORD.at(-1) === WEST.at(-1)) continue;
      const axes = {NORD,WEST}, tree = [53,-28];
      const model = editorPointToDortmund(tree,frame,axes);
      assert.ok(Math.abs(model[0])<10 && Math.abs(model[1])<10);
      assert.equal(inspectSurroundings({...terrain,trees:[tree]},frame,axes).ok,false);
      assert.equal(inspectSurroundings({...terrain,trees:[[200,200]]},frame,axes).ok,true);
    }
});

test('no declaration preserves baseline and does not invent terrain', () => {
  const data = {green:[editor(square(0,0))],buildings:[editor(square(0,0))],trees:[[0,0]]};
  assert.deepEqual(inspectSurroundings(data),{ok:true,terrainDeclared:false,findings:[]});
  assert.equal(inspectSurroundings({...data,groundLevel:0}).ok,true);
});

test('terrain, axes, frame, feature types fail explicitly', () => {
  for (const data of [{groundLevel:true},{groundLevel:NaN},{groundLevel:Infinity},
    {groundLevel:31},{groundCutout:hole},
    {...terrain,groundCutout:[[0,0],[1,1],[0,1],[1,0]]}])
    assert.equal(inspectSurroundings(data).findings[0].code,'invalid_terrain');
  assert.equal(inspectSurroundings({}, {}, null).ok,false);
  assert.equal(inspectSurroundings({}, {fieldC:[0,NaN]}).ok,false);
  assert.equal(inspectSurroundings({}, null).ok,false);
  assert.equal(inspectSurroundings({green:{}}).findings[0].path,'green');
  assert.equal(inspectSurroundings({trees:[[null,0]]}).findings[0].path,'trees[0]');
});
