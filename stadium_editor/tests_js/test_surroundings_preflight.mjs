import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings, editorPointToDortmund, createSurroundingsChecks}
  from '../static/stadium_editor/dortmund_surroundings.js';
import {inspectSurroundings, readPreflightInput} from '../surroundings_preflight.mjs';
import {surroundingsCatalog, appendLateConflicts}
  from './fixtures/surroundings_catalog.mjs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {Readable} from 'node:stream';

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

// Keep the original isolation strategy as a test oracle, never in production.
function rendererFindings(data, frame = {}, axes) {
  const findings = [];
  for (const layer of ['green','water','roads','buildings','trees']) {
    for (let index = 0; index < (data[layer] || []).length; index++) {
      let env;
      try {
        env = buildDortmundSurroundings(THREE, {...terrain,
          [layer]:[data[layer][index]],
          ...(layer === 'buildings' ? {buildingHeights:[data.buildingHeights?.[index]]} : {}),
        }, frame, axes);
        if (env.group.userData.terrain?.omitted[layer]?.length)
          findings.push({severity:'info',path:`${layer}[${index}]`,code:'surface_inside_cutout',
            message:'Fläche liegt vollständig in groundCutout und wird nur beim Rendern ausgeblendet; Quelle bleibt unverändert.'});
      } catch (error) {
        findings.push({severity:'error',path:`${layer}[${index}]`,code:'renderer_rejected',
          message:error.message.replaceAll(`${layer}[0]`, `${layer}[${index}]`)});
      } finally { env?.dispose(); }
    }
  }
  return findings;
}

test('complete findings match renderer oracle at boundaries, joins and malformed late objects', () => {
  const data = {...terrain,
    green:[editor(square(10,0)),editor(square(0,0)),editor(square(9,0)),
      editor([[-30,-1],[30,-1],[30,1],[-30,1]]),[[0,0],[1,1],[2,2]]],
    water:[editor(square(-30,-30,60)),editor(square(20,20)),null],
    roads:[
      {p:editor([[-30,12.5],[30,12.5]]),w:2}, // strip exactly touches boundary
      {p:editor([[12.5,0]]),w:2}, // single-point join exactly touches boundary
      {p:editor([[12.5+1e-6,0]]),w:2},
      {p:editor([[12.5,0],[12.5,0]]),w:2}, // zero-length strip still has joins
      {p:editor([[30,30],[11,11],[30,-30]]),w:2}, // bend join hits the hole
      {p:[],w:2}, {p:[],w:0},null,
    ],
    buildings:[editor(square(10,0)),editor(square(20,20)),editor(square(30,30))],
    buildingHeights:[9,null,-1],
    trees:editor([[10,0],[10+1e-6,0],[0,0],[30,30]])};
  const before = structuredClone(data);
  assert.deepEqual(inspectSurroundings(data).findings,rendererFindings(data));
  assert.deepEqual(data,before);
});

test('catalog parity compares full messages across all eight axes and nonzero frame', () => {
  const data = {...appendLateConflicts(surroundingsCatalog({
    trees:20,surfaces:4,roads:3,buildings:3})), ...terrain};
  const frame = {fieldC:[50,-30],axisTheta:Math.PI/3};
  for (const NORD of ['+x','-x','+z','-z'])
    for (const WEST of ['+x','-x','+z','-z']) {
      if (NORD.at(-1) === WEST.at(-1)) continue;
      const axes = {NORD,WEST};
      assert.deepEqual(inspectSurroundings(data,frame,axes).findings,
        rendererFindings(data,frame,axes));
    }
});

test('shared checks need only the production triangulator, never a geometry or material', () => {
  const cpuOnly = new Proxy(THREE, {get(target,key) {
    assert.ok(['Vector2','ShapeUtils'].includes(key),`Unexpected 3D allocation: ${String(key)}`);
    return target[key];
  }});
  const checks = createSurroundingsChecks(cpuOnly,terrain);
  checks.surface(editor(square(30,30)),'green',0);
  checks.building(editor(square(30,30)),9,0);
  for (const footprint of checks.roadFootprints(checks.road({p:editor([[30,30],[40,40]]),w:2}))) {
    assert.ok(footprint.points.length);
  }
  checks.tree([100,100]);
});

test('renderer buffers retain the pre-extraction byte fingerprints', () => {
  // Goldens recorded from the original renderer, including instance matrices,
  // road fans' final 2π vertex, positions, normals, UVs and triangle indices.
  const cases = [
    [{},'ca286b7f194f37ae3807ae42d4f02ed190d69185d9e693bbc798df8d99ce92e6'],
    [{fieldC:[50,-30],axisTheta:Math.PI/3},
      '3294fbaf807727167cb40cc67cfb256cda8658d23d2f57d85a5acffc8043c018'],
  ];
  const data = surroundingsCatalog({trees:8,surfaces:10,roads:3,buildings:3});
  for (const [frame, expected] of cases) {
    const env = buildDortmundSurroundings(THREE,data,frame);
    const hash = createHash('sha256');
    const bytes = array => hash.update(Buffer.from(array.buffer,array.byteOffset,array.byteLength));
    try {
      env.group.traverse(object => {
        hash.update(object.name);
        if (object.geometry) {
          for (const key of Object.keys(object.geometry.attributes).sort()) {
            hash.update(key);
            bytes(object.geometry.attributes[key].array);
          }
          if (object.geometry.index) bytes(object.geometry.index.array);
        }
        if (object.instanceMatrix) bytes(object.instanceMatrix.array);
      });
      assert.equal(hash.digest('hex'),expected);
    } finally { env.dispose(); }
  }
});

test('large catalog reaches every final object with bounded heap and elapsed time', {timeout:60000}, () => {
  const script = fileURLToPath(new URL('../../scripts/benchmark_surroundings_preflight.mjs',import.meta.url));
  const result = spawnSync(process.execPath,['--max-old-space-size=256',script,'--large','--max-cutout'],
    {encoding:'utf8',timeout:55000,maxBuffer:1024*1024});
  assert.equal(result.status,0,result.stderr || result.error?.message);
  const stats = JSON.parse(result.stdout);
  assert.equal(stats.counts.trees,100001);
  assert.equal(stats.counts.green,10001);
  assert.equal(stats.cutoutVertices,256);
  assert.equal(stats.findings.length,5);
  assert.ok(stats.elapsedMs < 55000,JSON.stringify(stats));
  assert.ok(stats.peakRssMiB < 512,JSON.stringify(stats));
});

test('stdin byte limit counts UTF-8 correctly and fails without a partial report', async () => {
  const input = Buffer.from('{"name":"Bäume"}');
  const chunks = () => Readable.from([input.subarray(0,11),input.subarray(11)]);
  assert.equal(await readPreflightInput(chunks(),input.length),input.toString());
  await assert.rejects(readPreflightInput(chunks(),input.length-1),/Prüfpaket zu groß/);
});
