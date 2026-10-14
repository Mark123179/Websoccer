import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings} from '../static/stadium_editor/dortmund_surroundings.js';
import {validateSurroundingsGround, groundPolygonRelation}
  from '../static/stadium_editor/surroundings_ground.js';

const hole = [[-10,-10],[10,-10],[10,10],[-10,10]];
const terrain = {groundLevel: 7.7, groundCutout: hole};
// Default editor mapping: editor [z,-x] -> model [x,z].
const editor = points => points.map(([x,z]) => [z,-x]);
const square = (x, z, size = 2) => [[x,z],[x+size,z],[x+size,z+size],[x,z+size]];

test('legacy geometry, objects and signed-zero defaults remain identical without terrain', () => {
  const a = buildDortmundSurroundings(THREE);
  const b = buildDortmundSurroundings(THREE, {groundLevel: 0});
  try {
    assert.equal(a.group.position.y, 0);
    assert.equal(a.group.children[0].geometry.type, 'PlaneGeometry');
    assert.deepEqual(Array.from(a.group.children[0].geometry.attributes.position.array),
      Array.from(b.group.children[0].geometry.attributes.position.array));
    assert.equal(a.group.children[0].position.y, -.35);
    assert.equal(Object.hasOwn(a.group.userData, 'terrain'), false);
  } finally { a.dispose(); b.dispose(); }
});

test('only environment rises; inside surfaces are omitted in rendering, never from source', () => {
  const input = {...terrain, green: [editor(square(-2,-2)), editor(square(20,20))],
    water: [editor(square(1,1))], buildings: [editor(square(30,30))],
    buildingHeights: [12], trees: [editor([[40,40]])[0]],
    roads: [{p: editor([[50,50],[60,50]]), w: 2}]};
  const before = JSON.stringify(input);
  const env = buildDortmundSurroundings(THREE, input);
  try {
    assert.equal(env.group.position.y, 7.7);
    assert.deepEqual(env.group.userData.terrain.omitted, {green: [0], water: [0]});
    assert.equal(env.group.userData.counts.green, 2, 'source counts stay available');
    assert.equal(env.group.getObjectByName('ENV_WATER'), undefined);
    assert.ok(env.group.getObjectByName('ENV_GREEN'));
    env.group.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(env.group.getObjectByName('ENV_BUILDINGS'));
    assert.ok(Math.abs(box.max.y - 19.7) < 1e-5);
    assert.equal(JSON.stringify(input), before);
    const ground = env.group.getObjectByName('ENV_GROUND');
    assert.equal(ground.geometry.type, 'ShapeGeometry');
    // The triangulated ground must have no triangle centroid inside the hole.
    const pos = ground.geometry.attributes.position, idx = ground.geometry.index;
    for (let i=0; i<(idx?.count ?? pos.count); i+=3) {
      const v = [0,1,2].map(j => idx ? idx.getX(i+j) : i+j);
      const x = v.reduce((sum,k)=>sum+pos.getX(k),0)/3;
      const z = -v.reduce((sum,k)=>sum+pos.getY(k),0)/3;
      assert.ok(!(Math.abs(x)<10 && Math.abs(z)<10));
    }
  } finally { env.dispose(); }
});

test('invalid declarations fail instead of defaulting to an uncut elevated plane', () => {
  for (const input of [
    {groundCutout: hole}, {groundLevel: null}, {groundLevel: true},
    {groundLevel: '7.7'}, {groundLevel: NaN}, {groundLevel: Infinity},
    {groundLevel: 31}, {groundLevel: 7.7},
    {...terrain, groundCutout: [[0,0],[1,1],[2,2]]},
    {...terrain, groundCutout: [[0,0],[1,1],[0,1],[1,0]]},
    {...terrain, groundCutout: [[0,0],[1,0],[1,1],[0,0],[0,1]]},
    {...terrain, groundCutout: [[0,0],[2,0],[1,0],[1,1],[0,1]]},
    {...terrain, groundCutout: [[0,0],[true,1],[1,0]]},
    {...terrain, groundCutout: [[0,0],[Infinity,1],[1,0]]},
  ]) assert.throws(() => validateSurroundingsGround(input), /ground/);
  assert.deepEqual(validateSurroundingsGround({...terrain, groundCutout: [...hole,hole[0]]}),
    {level: 7.7, cutout: hole});
  assert.deepEqual(validateSurroundingsGround({...terrain, groundCutout: [...hole].reverse()}).cutout,
    [...hole].reverse());
});

test('crossings and enclosing polygons fail even when every source vertex is outside', () => {
  const crossing = [[-30,-1],[30,-1],[30,1],[-30,1]];
  const enclosing = [[-30,-30],[30,-30],[30,30],[-30,30]];
  for (const poly of [crossing, enclosing]) {
    assert.equal(groundPolygonRelation(poly,hole), 'overlap');
    assert.throws(() => buildDortmundSurroundings(THREE,
      {...terrain,green:[editor(poly)]}), /kreuzt/);
  }
  assert.throws(() => buildDortmundSurroundings(THREE,
    {...terrain,water:[editor(square(9,0))]}), /kreuzt/);
});

test('buildings, road width/segments and trees are never silently deleted', () => {
  assert.throws(() => buildDortmundSurroundings(THREE,
    {...terrain,buildings:[editor(square(0,0))]}), /buildings\[0\]/);
  assert.throws(() => buildDortmundSurroundings(THREE,
    {...terrain,roads:[{p:editor([[-30,0],[30,0]]),w:1}]}), /roads\[0\]/);
  assert.throws(() => buildDortmundSurroundings(THREE,
    {...terrain,roads:[{p:editor([[-30,11],[30,11]]),w:2}]}), /roads\[0\]/);
  assert.throws(() => buildDortmundSurroundings(THREE,
    {...terrain,trees:[editor([[0,0]])[0]]}), /Baum/);
});

test('cutout is in model coordinates, independent of editor rotation and reflected axes', () => {
  const point = [53,-28], frame = {fieldC:[50,-30],axisTheta:Math.PI/2};
  const input = {...terrain,green:[[point,[54,-28],[54,-27],[53,-27]]]};
  const before=JSON.stringify(input);
  const env=buildDortmundSurroundings(THREE,input,frame,{NORD:'-z',WEST:'-x'});
  assert.deepEqual(env.group.userData.terrain.omitted.green,[0]);
  assert.equal(JSON.stringify(input),before);
  env.dispose();
});
