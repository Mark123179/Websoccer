import test from 'node:test';
import assert from 'node:assert/strict';
import {gzipSync} from 'node:zlib';
import * as THREE from './stage/vendor/three.module.js';
import {buildNaturalSurroundings} from './natural_surroundings.js';

const square = [[100, 200], [110, 200], [110, 208], [100, 208], [100, 200]];
const sourceTreeGeometry = new THREE.BufferGeometry();
sourceTreeGeometry.setAttribute('position', new THREE.Float32BufferAttribute([
  0, 0, 0, 1, 0, 0, 0, 1, 0,
], 3));
sourceTreeGeometry.setIndex([0, 1, 2]);
const treeGeometry = sourceTreeGeometry.toJSON();
const textureSpec = (prefix, sizeMeters = 4) => ({
  color: `${prefix}.webp`, normal: `${prefix}_normal.webp`,
  roughness: `${prefix}_roughness.webp`, sizeMeters,
});
const manifest = {
  schema: 'websoccer.natural-assets',
  version: 1,
  trees: ['oak_medium', 'oak_large', 'ash_medium', 'aspen_small'].map(id => ({
    id,
    levels: [0, 160, 330].map(distance => ({
      distance, branches: treeGeometry, leaves: treeGeometry,
    })),
  })),
  textures: {
    grass: textureSpec('grass', 3),
    asphalt: textureSpec('asphalt', 5),
    paving: textureSpec('paving', 2),
    brick: textureSpec('brick', 1.2),
    bark: textureSpec('bark', 1),
    leaves: {oak: 'oak.webp', ash: 'ash.webp', aspen: 'aspen.webp'},
  },
};
const packageFixture = () => ({
  schema: 'websoccer.natural-surroundings',
  version: 1,
  units: 'm',
  id: 'fixture',
  title: 'Mapped test ground',
  frame: {fieldC: [100, 200], axisTheta: Math.PI / 2},
  bounds: {min: [80, 180], max: [120, 220]},
  data: {
    roads: [{p: [[100, 200], [100, 210]], w: 2}],
    buildings: [square],
    buildingHeights: [12],
    buildingMaterials: ['brick'],
    green: [square],
    water: [],
    trees: [[100, 200]],
    shrubs: [],
    sources: {geography: 'OSM fixture extract', trees: 'mapped representatives'},
  },
});

function binaryLibraryFixture() {
  const binaryManifest = structuredClone(manifest);
  binaryManifest.geometryBuffer = 'trees.bin';
  const records = [];
  let offset = 0;
  for (const tree of binaryManifest.trees) {
    for (const level of tree.levels) {
      for (const part of ['branches', 'leaves']) {
        const base = offset;
        const record = {
          binary: true,
          attributes: {
            position: {byteOffset: base, count: 9, itemSize: 3, type: 'Float32Array'},
            normal: {byteOffset: base + 36, count: 9, itemSize: 3, type: 'Float32Array'},
            uv: {byteOffset: base + 72, count: 6, itemSize: 2, type: 'Float32Array'},
          },
          index: {byteOffset: base + 96, count: 3, type: 'Uint32Array'},
        };
        records.push({base, record});
        level[part] = record;
        offset += 108;
      }
    }
  }
  const buffer = new ArrayBuffer(offset);
  for (const {base} of records) {
    new Float32Array(buffer, base, 9).set([0, 0, 0, 1, 0, 0, 0, 1, 0]);
    new Float32Array(buffer, base + 36, 9).set([0, 0, 1, 0, 0, 1, 0, 0, 1]);
    new Float32Array(buffer, base + 72, 6).set([0, 0, 1, 0, 0, 1]);
    new Uint32Array(buffer, base + 96, 3).set([0, 1, 2]);
  }
  return {binaryManifest, buffer};
}

async function withMockAssets(callback, {
  manifestValue = manifest, failTexture, geometryBuffer,
} = {}) {
  const oldFetch = globalThis.fetch;
  const oldLoad = THREE.TextureLoader.prototype.loadAsync;
  const urls = [];
  const textures = [];
  globalThis.fetch = async url => {
    urls.push(String(url));
    if (String(url).endsWith('/trees.bin')) {
      return {
        ok: Boolean(geometryBuffer), status: geometryBuffer ? 200 : 404,
        arrayBuffer: async () => geometryBuffer,
      };
    }
    return {ok: true, status: 200, json: async () => manifestValue};
  };
  THREE.TextureLoader.prototype.loadAsync = async function (url) {
    urls.push(String(url));
    if (failTexture && String(url).includes(failTexture)) throw new Error('test load error');
    const texture = new THREE.DataTexture(new Uint8Array([190, 185, 170, 255]), 1, 1);
    texture.needsUpdate = true;
    textures.push(texture);
    return texture;
  };
  try { return await callback({urls, textures}); }
  finally {
    globalThis.fetch = oldFetch;
    THREE.TextureLoader.prototype.loadAsync = oldLoad;
  }
}

test('renders transformed mapped geometry, metadata-selected brick, and calibrated road width', async () => {
  await withMockAssets(async ({urls}) => {
    const packageData = packageFixture();
    const before = JSON.stringify(packageData);
    const environment = await buildNaturalSurroundings(THREE, packageData, {
      assetBase: 'https://local.test/stadium_editor/natural_assets/',
      camera: {position: new THREE.Vector3(0, 25, 0)},
    });
    assert.equal(JSON.stringify(packageData), before, 'source package remains untouched');
    assert.ok(urls.includes('https://local.test/stadium_editor/natural_assets/library.json'));
    assert.ok(urls.every(url => !url.includes('openstreetmap.org')));
    const walls = environment.group.getObjectByName('NATURAL_BUILDING_WALLS_BRICK');
    assert.ok(walls);
    walls.geometry.computeBoundingBox();
    assert.ok(Math.abs(walls.geometry.boundingBox.min.x) < 1e-5);
    assert.ok(Math.abs(walls.geometry.boundingBox.max.x - 10) < 1e-5);
    assert.ok(Math.abs(walls.geometry.boundingBox.max.y - 12) < 1e-5);
    const road = environment.group.getObjectByName('NATURAL_MAPPED_ROADS');
    road.geometry.computeBoundingBox();
    assert.ok(Math.abs(road.geometry.boundingBox.min.x + 2.5) < 1e-5);
    assert.ok(Math.abs(road.geometry.boundingBox.max.x - 2.5) < 1e-5);
    assert.equal(environment.metrics.roadHalfWidthScale, 1.25);
    assert.ok(environment.group.getObjectByName('NATURAL_BUILDING_WALLS_BRICK'));
    const foliageLeaves = environment.group.children.find(child =>
      child.name?.includes('_LEAVES') && child.isInstancedMesh);
    assert.equal(foliageLeaves.material.roughness, 0.94);
    assert.equal(environment.group.getObjectByName('NATURAL_MAPPED_GREEN').material.roughness, 1);
    assert.ok(environment.group.getObjectByName('NATURAL_MAPPED_GREEN').material.roughnessMap);
    assert.ok(environment.group.getObjectByName('NATURAL_GROUND'));
    assert.ok(environment.group.getObjectByName('NATURAL_MAPPED_GREEN'));
    assert.equal(environment.group.getObjectByName('NATURAL_MAPPED_WATER'), undefined);
    environment.dispose();
    const neutralData = packageFixture();
    neutralData.data.buildingMaterials = ['neutral'];
    const neutralEnvironment = await buildNaturalSurroundings(THREE, neutralData, {
      assetBase: 'https://local.test/stadium_editor/natural_assets/',
    });
    const neutralWalls = neutralEnvironment.group.getObjectByName('NATURAL_BUILDING_WALLS_NEUTRAL');
    assert.ok(neutralWalls.material.map, 'neutral facade detail has a pale diffuse map');
    assert.equal(neutralWalls.material.map.image.data[(20 * 64 + 0) * 4], 198);
    neutralEnvironment.dispose();
  });
});

test('loads shared packed tree geometry once and validates scalar-count binary views', async () => {
  const {binaryManifest, buffer} = binaryLibraryFixture();
  await withMockAssets(async ({urls}) => {
    const environment = await buildNaturalSurroundings(THREE, packageFixture(), {
      assetBase: 'https://local.test/natural_assets/',
      camera: {position: new THREE.Vector3(0, 20, 0)},
    });
    assert.equal(urls.filter(url => url.endsWith('/trees.bin')).length, 1);
    assert.equal(environment.metrics.geometryBufferBytes, buffer.byteLength);
    assert.deepEqual(environment.metrics.triangleCountsByLOD, {0: 8, 160: 8, 330: 8});
    const mesh = environment.group.children.find(child =>
      child.name?.includes('_LOD0_BRANCHES') && child.isInstancedMesh);
    assert.ok(mesh.geometry.getAttribute('normal'));
    assert.equal(mesh.geometry.index.count, 3);
    environment.dispose();
  }, {manifestValue: binaryManifest, geometryBuffer: buffer});

  const {binaryManifest: invalidManifest, buffer: invalidBuffer} = binaryLibraryFixture();
  invalidManifest.trees[0].levels[0].branches.attributes.position.byteOffset = 1;
  await withMockAssets(async () => {
    await assert.rejects(() => buildNaturalSurroundings(THREE, packageFixture(), {
      assetBase: 'https://local.test/natural_assets/',
    }), /misaligned or outside trees\.bin/);
  }, {manifestValue: invalidManifest, geometryBuffer: invalidBuffer});
});

test('updates per-instance tree LOD from mapped position without duplicating placement', async () => {
  await withMockAssets(async () => {
    const environment = await buildNaturalSurroundings(THREE, packageFixture(), {
      assetBase: 'https://local.test/natural_assets/',
      camera: {position: new THREE.Vector3(0, 20, 0)},
    });
    const countsByLOD = () => [0, 1, 2].map(lod =>
      environment.group.children.filter(child =>
        child.name?.includes(`_LOD${lod}_`) && child.isInstancedMesh)
        .reduce((total, child) => total + child.count, 0) / 2);
    assert.deepEqual(countsByLOD(), [1, 0, 0]);
    environment.updateLOD({position: new THREE.Vector3(0, 200, 0)});
    assert.deepEqual(countsByLOD(), [0, 1, 0]);
    environment.updateLOD({position: new THREE.Vector3(0, 400, 0)});
    assert.deepEqual(countsByLOD(), [0, 0, 1]);
    environment.dispose();
  });
});

test('gzip geometry works with raw static bytes and HTTP-decoded bytes', async () => {
  const {binaryManifest, buffer} = binaryLibraryFixture();
  binaryManifest.geometryCompression = 'gzip';
  for (const packed of [false, true]) {
    const body = packed ? Uint8Array.from(gzipSync(new Uint8Array(buffer))).buffer : buffer;
    await withMockAssets(async () => {
      const environment = await buildNaturalSurroundings(THREE, packageFixture(), {
        assetBase: 'https://local.test/natural_assets/',
      });
      assert.equal(environment.metrics.geometryBufferBytes, buffer.byteLength);
      environment.dispose();
    }, {manifestValue: binaryManifest, geometryBuffer: body});
  }
});

test('camera frustum omits offscreen tree instances without altering mapped data', async () => {
  await withMockAssets(async () => {
    const camera = new THREE.PerspectiveCamera(40, 1.8, .1, 1000);
    camera.position.set(0, 5, 20); camera.lookAt(0, 0, 0);
    const packageData = packageFixture();
    const environment = await buildNaturalSurroundings(THREE, packageData, {
      assetBase: 'https://local.test/natural_assets/', camera,
    });
    const count = () => environment.group.children.filter(
      c => c.name.includes('NATURAL_TREES') && c.name.endsWith('LEAVES')).reduce((n,c) => n+c.count,0);
    assert.equal(count(), 1);
    camera.lookAt(0, 5, 100); environment.updateLOD(camera);
    assert.equal(count(), 0);
    assert.equal(packageData.data.trees.length, 1);
    environment.dispose();
  });
});

test('a rotated and translated second package renders the identical physical surroundings', async () => {
  await withMockAssets(async () => {
    const first = packageFixture(), second = structuredClone(first);
    // Optional editor-axis AABB is an extract envelope, not a mapped feature.
    // Compare the same actual geometry rather than two different envelopes.
    delete first.bounds; delete second.bounds;
    second.id = 'second-fixture'; second.title = 'Second calibration fixture';
    second.frame = {fieldC: [-48, 73], axisTheta: .37};
    const convert = ([x, y]) => {
      const dx = x - first.frame.fieldC[0], dy = y - first.frame.fieldC[1];
      const u = dx * Math.cos(first.frame.axisTheta) + dy * Math.sin(first.frame.axisTheta);
      const v = -dx * Math.sin(first.frame.axisTheta) + dy * Math.cos(first.frame.axisTheta);
      return [second.frame.fieldC[0] + u * Math.cos(.37) - v * Math.sin(.37),
        second.frame.fieldC[1] + u * Math.sin(.37) + v * Math.cos(.37)];
    };
    for (const key of ['buildings', 'green', 'water']) second.data[key] = second.data[key].map(poly => poly.map(convert));
    second.data.trees = second.data.trees.map(convert);
    second.data.roads = second.data.roads.map(road => ({...road,p:road.p.map(convert)}));
    const args = {assetBase:'https://local.test/natural_assets/'};
    const a = await buildNaturalSurroundings(THREE,first,args), b = await buildNaturalSurroundings(THREE,second,args);
    for (const mesh of a.group.children.filter(c => c.isMesh && !c.isInstancedMesh)) {
      const other = b.group.getObjectByName(mesh.name);
      const one = mesh.geometry.attributes.position.array, two = other.geometry.attributes.position.array;
      assert.equal(one.length,two.length);
      one.forEach((value,i)=>assert.ok(Math.abs(value-two[i])<.001,`${mesh.name} calibration differed`));
    }
    a.dispose();b.dispose();
  });
});

test('rejects invalid source coordinates and missing local assets explicitly', async () => {
  const invalid = packageFixture();
  invalid.data.trees[0] = [NaN, 0];
  await assert.rejects(() => buildNaturalSurroundings(THREE, invalid, {
    assetBase: 'https://local.test/natural_assets/',
  }), /trees\[0\].*finite/);
  await withMockAssets(async () => {
    await assert.rejects(() => buildNaturalSurroundings(THREE, packageFixture(), {
      assetBase: 'https://local.test/natural_assets/',
    }), /unsupported asset library schema/);
  }, {manifestValue: {schema: 'wrong', version: 1}});
});

test('asset loading errors reject and release every texture that did load', async () => {
  await withMockAssets(async ({textures}) => {
    let disposedCount = 0;
    const original = THREE.DataTexture.prototype.dispose;
    THREE.DataTexture.prototype.dispose = function () {
      disposedCount++;
      return original.call(this);
    };
    try {
      await assert.rejects(() => buildNaturalSurroundings(THREE, packageFixture(), {
        assetBase: 'https://local.test/natural_assets/',
      }), /local texture .* failed to load/);
      assert.ok(textures.length > 0);
      assert.equal(disposedCount, textures.length);
    } finally {
      THREE.DataTexture.prototype.dispose = original;
    }
  }, {failTexture: 'brick.webp'});
});

test('dispose is idempotent and removes the natural group from its parent', async () => {
  await withMockAssets(async () => {
    const environment = await buildNaturalSurroundings(THREE, packageFixture(), {
      assetBase: 'https://local.test/natural_assets/',
    });
    const scene = new THREE.Scene();
    scene.add(environment.group);
    let disposed = 0;
    const resources = new Set();
    environment.group.traverse(object => {
      if (object.geometry) resources.add(object.geometry);
      if (object.material) {
        for (const material of Array.isArray(object.material) ? object.material : [object.material])
          resources.add(material);
      }
      if (object.isInstancedMesh) resources.add(object);
    });
    resources.forEach(resource => resource.addEventListener('dispose', () => disposed++));
    environment.dispose();
    environment.dispose();
    assert.equal(scene.children.length, 0);
    assert.equal(disposed, resources.size);
  });
});
