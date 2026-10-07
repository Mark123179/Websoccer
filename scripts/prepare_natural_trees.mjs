// Offline only. Read the pinned, MIT-licensed EZ-Tree source without installing it.
// Usage: node --experimental-vm-modules scripts/prepare_natural_trees.mjs SOURCE_DIR OUTPUT
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {gzipSync} from 'node:zlib';
import * as THREE from '../stadium_editor/static/stadium_editor/stage/vendor/three.module.js';

const [sourceDir, output] = process.argv.slice(2);
if (!sourceDir || !output) throw new Error('SOURCE_DIR and OUTPUT are required.');
const cache = new Map();
async function moduleFor(file) {
  if (cache.has(file)) return cache.get(file);
  let module;
  if (file === 'three') {
    module = new vm.SyntheticModule(Object.keys(THREE), function () {
      for (const key of Object.keys(THREE)) this.setExport(key, THREE[key]);
    });
  } else if (file.endsWith('.json')) {
    const value = JSON.parse(fs.readFileSync(file, 'utf8'));
    module = new vm.SyntheticModule(['default'], function () { this.setExport('default', value); });
  } else {
    module = new vm.SourceTextModule(fs.readFileSync(file, 'utf8'), {identifier: file});
  }
  cache.set(file, module);
  await module.link(async (specifier, parent) => {
    if (specifier === 'three') return moduleFor('three');
    let target = path.resolve(path.dirname(parent.identifier), specifier);
    if (!path.extname(target)) target += '.js';
    return moduleFor(target);
  });
  return module;
}
const module = await moduleFor(path.resolve(sourceDir, 'src/lib/tree.js'));
await module.evaluate();
const trees = [];
const binaryChunks = [];
let binaryOffset = 0;
function packGeometry(geometry) {
  const result = {binary: true, attributes: {}};
  for (const [key, attribute] of Object.entries(geometry.attributes)) {
    const bytes = Buffer.from(new Float32Array(attribute.array).buffer);
    result.attributes[key] = {byteOffset: binaryOffset, count: attribute.array.length,
      itemSize: attribute.itemSize, type: 'Float32Array'};
    binaryChunks.push(bytes); binaryOffset += bytes.length;
  }
  const index = geometry.index;
  const bytes = Buffer.from(new Uint32Array(index.array).buffer);
  result.index = {byteOffset: binaryOffset, count: index.array.length, type: 'Uint32Array'};
  binaryChunks.push(bytes); binaryOffset += bytes.length;
  return result;
}
for (const id of ['oak_medium', 'oak_large', 'ash_medium', 'aspen_small']) {
  const tree = new module.namespace.Tree();
  // Keep the supplied skeleton and seed; only tessellation/leaf density varies.
  tree.options.copy(JSON.parse(fs.readFileSync(path.join(sourceDir, 'src/lib/presets', `${id}.json`))));
  const levels = [
    {distance: 0, detail: {sectionStride: 2, segmentFactor: .6, leafStride: 1}},
    {distance: 160, detail: {sectionStride: 3, segmentFactor: .45, leafStride: 2, leafScale: 1.15}},
    {distance: 330, detail: {sectionStride: 4, segmentFactor: .35, leafStride: 4, leafScale: 1.25}},
  ].map(({distance, detail}) => {
    const geometry = tree.createGeometry(detail);
    const result = {distance, branches: packGeometry(geometry.branches), leaves: packGeometry(geometry.leaves)};
    for (const key of ['branches', 'leaves']) {
      geometry[key].dispose();
    }
    return result;
  });
  trees.push({id, leaf: tree.options.leaves.type, levels});
  console.log(id, levels.map(l => ({
    distance: l.distance,
    triangles: (l.branches.index.count + l.leaves.index.count) / 3,
  })));
}
fs.mkdirSync(path.dirname(output), {recursive: true});
fs.writeFileSync(path.join(path.dirname(output), 'trees.bin.gz'), gzipSync(Buffer.concat(binaryChunks), {level: 9}));
fs.rmSync(path.join(path.dirname(output), 'trees.bin'), {force: true});
fs.writeFileSync(output, JSON.stringify({
  schema: 'websoccer.natural-assets', version: 1,
  geometryBuffer: 'trees.bin.gz', geometryCompression: 'gzip', trees,
}));
