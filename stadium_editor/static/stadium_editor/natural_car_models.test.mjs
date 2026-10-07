import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from './stage/vendor/three.module.js';
import {createCarResourceDisposer,createCarShadowProxyGeometry} from './natural_car_models.js';

test('car disposal owns source textures, shared resources, and late-loaded textures once', async () => {
  const count = {geometry: 0, clone: 0, material: 0, proxyMaterial: 0, texture: 0, late: 0};
  const geometry = {dispose() { count.geometry++; }};
  const clone = {dispose() { count.clone++; }};
  const lateTexture = {isTexture: true, dispose() { count.late++; }};
  const texture = {isTexture: true, dispose() { count.texture++; }};
  const material = {map: texture, dispose() { count.material++; }};
  const proxyMaterial={dispose(){count.proxyMaterial++;}};
  const registry = new Set();
  const removed = [];
  const mesh = {geometry: clone, material};
  const gltf = {scene: {traverse(callback) {
    callback({geometry, material});
    callback({geometry, material});
  }}};
  const dispose = createCarResourceDisposer({gltf, destination: {remove: value => removed.push(value)},
    records: [{mesh}], clonedGeometries: new Set([clone, clone]),
    clonedMaterials:new Set([proxyMaterial]),textureRegistry: registry});
  await Promise.resolve();
  registry.add(lateTexture);
  registry.add(texture);
  dispose();
  dispose();
  assert.deepEqual(count, {geometry: 1, clone: 1, material: 1, proxyMaterial:1, texture: 1, late: 1});
  assert.deepEqual(removed, [mesh]);
  assert.equal(registry.size, 0);
});

test('vehicle shadow proxies are low-poly and retain normalized source dimensions',()=>{
  const sourceSize=new THREE.Vector3(4.45,1.63,1.92);
  const proxy=createCarShadowProxyGeometry(THREE,sourceSize);
  proxy.computeBoundingBox();
  assert.equal(proxy.index.count/3,12);
  assert.ok(Math.abs(proxy.boundingBox.max.x-proxy.boundingBox.min.x-sourceSize.x)<1e-5);
  assert.ok(Math.abs(proxy.boundingBox.max.z-proxy.boundingBox.min.z-sourceSize.z)<1e-5);
  assert.ok(Math.abs(proxy.boundingBox.max.y-proxy.boundingBox.min.y-.42)<1e-5);
  proxy.dispose();
});
