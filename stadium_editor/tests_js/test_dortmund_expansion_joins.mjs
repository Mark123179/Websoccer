import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildConcept, cornerEavePoints} from '../static/stadium_editor/dortmund_concept.js';

class BufferAttribute {
  constructor(array, itemSize) {
    this.array = Float32Array.from(array);
    this.itemSize = itemSize;
    this.count = this.array.length / itemSize;
  }
  getX(index) { return this.array[index * this.itemSize]; }
  getY(index) { return this.array[index * this.itemSize + 1]; }
  getZ(index) { return this.array[index * this.itemSize + 2]; }
  setXYZ(index, x, y, z) {
    this.array.set([x, y, z], index * this.itemSize);
  }
}

class BufferGeometry {
  constructor() { this.attributes = {}; }
  setAttribute(name, attribute) { this.attributes[name] = attribute; }
  setIndex(index) { this.index = index; }
  computeVertexNormals() {}
  computeBoundingSphere() {}
  dispose() { this.disposed = true; }
  clone() {
    const copy = new BufferGeometry();
    for (const [name, attribute] of Object.entries(this.attributes))
      copy.setAttribute(name, new BufferAttribute(attribute.array, attribute.itemSize));
    copy.index = this.index && [...this.index];
    return copy;
  }
}

class Vector3 {
  constructor(x = 0, y = 0, z = 0) { this.set(x, y, z); }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
  copy(value) { return this.set(value.x, value.y, value.z); }
  clone() { return new Vector3(this.x, this.y, this.z); }
  add(value) { this.x += value.x; this.y += value.y; this.z += value.z; return this; }
  sub(value) { this.x -= value.x; this.y -= value.y; this.z -= value.z; return this; }
  subVectors(a, b) { return this.set(a.x - b.x, a.y - b.y, a.z - b.z); }
  multiplyScalar(scale) { this.x *= scale; this.y *= scale; this.z *= scale; return this; }
  length() { return Math.hypot(this.x, this.y, this.z); }
  normalize() { return this.multiplyScalar(1 / (this.length() || 1)); }
}

class Group {
  constructor() { this.children = []; }
  add(...objects) { this.children.push(...objects); }
  traverse(callback) { this.children.forEach(callback); }
}

class Mesh {
  constructor(geometry, material) {
    this.geometry = geometry;
    this.material = material;
    this.position = new Vector3();
    this.quaternion = {setFromUnitVectors() {}};
  }
}

class Material {
  constructor(properties = {}) { Object.assign(this, properties); }
  clone() { return new Material({...this}); }
  dispose() { this.disposed = true; }
}

class InstancedMesh extends Mesh {
  constructor(geometry, material, count) {
    super(geometry, material);
    this.count = count;
    this.instanceMatrix = {needsUpdate: false};
    this.instances = [];
  }
  setMatrixAt(index, matrix) { this.instances[index] = matrix.position; }
  computeBoundingSphere() {}
}

class Object3D {
  constructor() {
    this.position = new Vector3();
    this.rotation = {set() {}};
    this.matrix = {};
  }
  updateMatrix() { this.matrix = {position: this.position.clone()}; }
}

const THREE = {
  Group,
  BufferGeometry,
  Float32BufferAttribute: BufferAttribute,
  Mesh,
  BoxGeometry: class extends BufferGeometry {},
  MeshStandardMaterial: Material,
  Vector3,
  InstancedMesh,
  Object3D,
  DoubleSide: 2,
};

const point = (geometry, index) => {
  const p = geometry.attributes.position;
  return [p.getX(index), p.getY(index), p.getZ(index)];
};
const pointsOf = mesh => Array.from({length: mesh.geometry.attributes.position.count},
  (_, index) => point(mesh.geometry, index));
const meshNamed = (group, name) => {
  const mesh = group.children.find(child => child.name === name);
  assert.ok(mesh, `missing geometry ${name}`);
  return mesh;
};
const samePoint = (a, b) => assert.deepEqual(a, b);
const activeGeometry = weights => buildConcept(THREE, weights).group;

test('single-side expansion closes both terrace and roof at its free ends', () => {
  const group = activeGeometry({SUED: 1});
  const facade = meshNamed(group, 'NEW_PLUS_X_FACADE');
  for (const sign of [-1, 1]) {
    const wall = meshNamed(group, `NEW_PLUS_X_END_WALL_${sign}`);
    const roof = meshNamed(group, `NEW_PLUS_X_END_ROOF_JUNCTION_${sign}`);
    const eave = meshNamed(group, `NEW_PLUS_X_END_EAVE_CAP_${sign}`);
    const wallPoints = pointsOf(wall), facadePoints = pointsOf(facade);
    samePoint(wallPoints[1], sign === 1 ? facadePoints[1] : facadePoints[0]);
    samePoint(wallPoints[2], sign === 1 ? facadePoints[2] : facadePoints[3]);
    const roofPoints = pointsOf(roof), eavePoints = pointsOf(eave);
    samePoint(roofPoints[1], wallPoints[2]);
    samePoint(roofPoints[2], eavePoints[2]);
    samePoint(eavePoints[0], wallPoints[2]);
    samePoint(eavePoints[2], roofPoints[2]);
    assert.ok(eavePoints.slice(0, 3).every(p => p.every(Number.isFinite)));
  }
});

test('isolated side geometry and seats stay within the source end-stand footprint', () => {
  const group = activeGeometry({SUED: 1});
  const surfaceNames = /^(NEW_PLUS_X_ROW_|NEW_PLUS_X_FACADE$|NEW_PLUS_X_(PLINTH|CONCOURSE|BELT|UPPER_BELT)$|NEW_PLUS_X_ROOF_JUNCTION|NEW_PLUS_X_EAVE|NEW_PLUS_X_END_)/;
  const surfaces = group.children.filter(child => surfaceNames.test(child.name));
  assert.ok(surfaces.length > 0);
  const lateral = surfaces.flatMap(pointsOf).map(point => point[2]);
  for (const mesh of group.children.filter(child => child.name.startsWith('CONCEPT_SEAT_')))
    lateral.push(...mesh.instances.map(position => position.z));
  assert.ok(lateral.length > 0);
  assert.ok(Math.min(...lateral) >= -115 - 1e-5);
  assert.ok(Math.max(...lateral) <= 115 + 1e-5);
  assert.ok(group.children.every(child =>
    !/^(NEW_PLUS_Z_|NEW_MINUS_Z_)/.test(child.name)),
  'no geometry should be emitted on absent neighboring stands');
});

test('each isolated side receives two end caps; Rundum stays open-ended only at corners', () => {
  for (const [stand, meshKey] of Object.entries({
    SUED: 'PLUS_X', NORD: 'MINUS_X', OST: 'PLUS_Z', WEST: 'MINUS_Z',
  })) {
    const group = activeGeometry({[stand]: 1});
    for (const sign of [-1, 1]) {
      meshNamed(group, `NEW_${meshKey}_END_WALL_${sign}`);
      meshNamed(group, `NEW_${meshKey}_END_ROOF_JUNCTION_${sign}`);
      meshNamed(group, `NEW_${meshKey}_END_EAVE_CAP_${sign}`);
    }
  }
  const rundum = activeGeometry({SUED: 1, NORD: 1, OST: 1, WEST: 1});
  assert.equal(rundum.children.filter(child => /_END_WALL_/.test(child.name)).length, 0);
});

test('complete Rundum keeps its existing broad stand and facade outline', () => {
  const group = activeGeometry({SUED: 1, NORD: 1, OST: 1, WEST: 1});
  const facade = pointsOf(meshNamed(group, 'NEW_PLUS_X_FACADE'));
  samePoint(facade[0], [110, 0, -137]);
  samePoint(facade[1], [110, 0, 137]);
  const row = pointsOf(meshNamed(group, 'NEW_PLUS_X_ROW_0'));
  samePoint(row[0], [91, 38, -115]);
  samePoint(row[1], [91, 38, 115]);
});

test('adjacent sides share exact roof/eave corner endpoints', () => {
  const group = activeGeometry({SUED: 1, NORD: 1, OST: 1, WEST: 1});
  assert.equal(group.children.filter(child => child.name.startsWith('NEW_CORNER_EAVE_')).length, 4);
  const southEast = meshNamed(group, 'NEW_CORNER_EAVE_SUED_OST');
  const vertices = pointsOf(southEast);
  const expected = cornerEavePoints(1, 1,
    {outer: 128, crown: 69, progress: 1,
      spanAt: (_sign, progress) => 115 + 36 * progress, overhangAt: () => 2},
    {outer: 151, crown: 69, progress: 1,
      spanAt: (_sign, progress) => 91 + 37 * progress, overhangAt: () => 2});
  assert.deepEqual(vertices, expected);
  // The two eave sheets' exposed edges are precisely the return's outer edges.
  samePoint(vertices[0], [126, 77, 151]);
  samePoint(vertices[1], [130, 76, 153]);
  samePoint(vertices[2], [130, 76, 153]);
  samePoint(vertices[3], [128, 77, 149]);
});

test('unequal neighboring strengths stop the longer side at the shorter source-aligned cap', () => {
  const group = activeGeometry({SUED: 6 / 7, OST: 3 / 7});
  const northEdgeWall = meshNamed(group, 'NEW_PLUS_X_END_WALL_1');
  const zLimit = 115 + 36 * (3 / 7);
  for (const point of pointsOf(northEdgeWall))
    assert.ok(Math.abs(point[2] - zLimit) < 1e-5 || Math.abs(point[2] - 115) < 1e-5);
  const highestSouthRow = meshNamed(group, 'NEW_PLUS_X_ROW_5');
  assert.ok(pointsOf(highestSouthRow).every(point => point[2] <= zLimit + 1e-5));
});

test('mockup declares corner returns and clones Unity geometry before deformation', () => {
  const source = readFileSync(new URL(
    '../../artifacts/mockup-sandbox/src/components/mockups/dortmund-120/_ExpansionArchitecture.ts',
    import.meta.url), 'utf8');
  assert.match(source, /object\.geometry\.clone\(\)/);
  assert.match(source, /object\.geometry = geometry;/);
  assert.match(source, /NEW_CORNER_EAVE_\$\{xSign\}_\$\{zSign\}/);
  assert.match(source, /NEW_CORNER_EAVE_PLUS_X_\$\{sign\}/);
  assert.match(source, /derivedGeometries\.forEach\(\(geometry: any\) => geometry\.dispose\(\)\)/);
});

test('source materials remain private to mockup cutaways', () => {
  const source = readFileSync(new URL(
    '../../artifacts/mockup-sandbox/src/components/mockups/dortmund-120/_ExpansionArchitecture.ts',
    import.meta.url), 'utf8');
  assert.match(source, /original\.clone\(\)/);
  assert.match(source, /object\.material = Array\.isArray\(object\.material\) \? cutaway : cutaway\[0\]/);
});