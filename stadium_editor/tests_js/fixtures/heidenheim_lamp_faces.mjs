// Eight original front-face triangles only. No textures or full stadium asset.
// This small deterministic fixture is independent of ignored study outputs.
const faces = [
  [14, [[-44.22186279296875,34.80000305175781,60.827510833740234],[-39.41341781616211,39.90005111694336,62.80752944946289],[-40.82763671875,34.80000305175781,64.22174072265625]], [[0,.5],[.5,1],[.5,.500244140625]]],
  [15, [[-39.41341781616211,39.90005111694336,62.80752944946289],[-44.22186279296875,34.80000305175781,60.827510833740234],[-42.807647705078125,39.90005111694336,59.41330337524414]], [[.5,1],[0,.5],[0,1]]],
  [100, [[44.221858978271484,34.800010681152344,-60.827510833740234],[39.413414001464844,39.900054931640625,-62.80752944946289],[40.827632904052734,34.800010681152344,-64.22174072265625]], [[0,.5],[.5,1],[.5,.500244140625]]],
  [101, [[39.413414001464844,39.900054931640625,-62.80752944946289],[44.221858978271484,34.800010681152344,-60.827510833740234],[42.807640075683594,39.900054931640625,-59.41330337524414]], [[.5,1],[0,.5],[0,1]]],
  [228, [[44.2216796875,34.800010681152344,60.82764434814453],[39.41322708129883,39.900054931640625,62.807655334472656],[42.80746841430664,39.900054931640625,59.41343307495117]], [[0,.5],[.5,1],[0,1]]],
  [229, [[39.41322708129883,39.900054931640625,62.807655334472656],[44.2216796875,34.800010681152344,60.82764434814453],[40.82743835449219,34.800010681152344,64.22186279296875]], [[.5,1],[0,.5],[.5,.500244140625]]],
  [280, [[-44.22168731689453,34.80000305175781,-60.82764434814453],[-39.41323471069336,39.90005111694336,-62.807655334472656],[-42.807472229003906,39.90005111694336,-59.41343307495117]], [[0,.5],[.5,1],[0,1]]],
  [281, [[-39.41323471069336,39.90005111694336,-62.807655334472656],[-44.22168731689453,34.80000305175781,-60.82764434814453],[-40.82743835449219,34.80000305175781,-64.22186279296875]], [[.5,1],[0,.5],[.5,.500244140625]]],
];

export function lampFacesFixture(sourceManifest) {
  const manifest = structuredClone(sourceManifest);
  const mesh = manifest.meshes.find(m => m.name === 'center2_9');
  const part = mesh.parts.find(p => p.material === 'terrain_grass_artificial_02_gray_clean_newyork_color 4');
  const positions = new Float32Array(faces.flatMap(f => f[1].flat()));
  const uv = new Float32Array(faces.flatMap(f => f[2].flat()));
  const indices = new Uint32Array(282 * 3);
  faces.forEach(([triangle], i) => indices.set([i * 3, i * 3 + 1, i * 3 + 2], triangle * 3));
  const buffer = new ArrayBuffer(positions.byteLength + uv.byteLength + indices.byteLength);
  new Float32Array(buffer, 0, positions.length).set(positions);
  new Float32Array(buffer, positions.byteLength, uv.length).set(uv);
  new Uint32Array(buffer, positions.byteLength + uv.byteLength, indices.length).set(indices);
  Object.assign(mesh, {positionOffset: 0, uvOffset: positions.byteLength, vertexCount: 24, parts: [part]});
  Object.assign(part, {indexOffset: positions.byteLength + uv.byteLength, indexCount: indices.length});
  manifest.meshes = [mesh];
  return {manifest, buffer};
}
