const PACKAGE_SCHEMA = 'websoccer.natural-surroundings';
const ASSET_SCHEMA = 'websoccer.natural-assets';
const TREE_VARIANTS = ['oak_medium', 'oak_large', 'ash_medium', 'aspen_small'];
const LOD_DISTANCES = [0, 160, 330];

const fail = message => { throw new Error(`Natural surroundings: ${message}`); };
const finite = value => typeof value === 'number' && Number.isFinite(value);
const isPoint = value => Array.isArray(value) && value.length === 2 && value.every(finite);
const closePoint = (a, b) => a[0] === b[0] && a[1] === b[1];

function validatePackage(packageData) {
  if (!packageData || packageData.schema !== PACKAGE_SCHEMA || packageData.version !== 1)
    fail('unsupported package schema or version.');
  if (packageData.units !== 'm') fail('package units must be meters.');
  if (typeof packageData.id !== 'string' || !packageData.id.trim() ||
      typeof packageData.title !== 'string' || !packageData.title.trim())
    fail('package id and title are required.');
  const frame = packageData.frame;
  if (!frame || !isPoint(frame.fieldC) || !finite(frame.axisTheta))
    fail('frame.fieldC and frame.axisTheta must contain finite coordinates.');
  const data = packageData.data;
  if (!data || typeof data !== 'object') fail('package data is missing.');
  for (const key of ['roads', 'buildings', 'buildingHeights', 'green', 'water', 'trees']) {
    if (!Array.isArray(data[key])) fail(`data.${key} must be an array.`);
  }
  if (data.buildingHeights.length !== data.buildings.length)
    fail('each building needs a matching buildingHeights entry.');
  if (data.buildingMaterials !== undefined &&
      (!Array.isArray(data.buildingMaterials) || data.buildingMaterials.length !== data.buildings.length))
    fail('buildingMaterials must match the buildings array.');
  if (data.shrubs !== undefined && (!Array.isArray(data.shrubs) || data.shrubs.length))
    fail('mapped shrubs are explicitly unsupported by this renderer; no positions are inferred.');
  for (const key of ['geography', 'trees']) {
    if (typeof data.sources?.[key] !== 'string' || !data.sources[key].trim())
      fail(`data.sources.${key} is required.`);
  }
  const polygon = (raw, name) => {
    if (!Array.isArray(raw) || raw.length < 3 || raw.some(point => !isPoint(point)))
      fail(`${name} must be a polygon with at least three finite points.`);
    let area = 0;
    for (let i = 0; i < raw.length; i++) {
      const a = raw[i], b = raw[(i + 1) % raw.length];
      area += a[0] * b[1] - b[0] * a[1];
    }
    if (Math.abs(area) < 1e-8) fail(`${name} must enclose a positive area.`);
  };
  data.green.forEach((item, i) => polygon(item, `green[${i}]`));
  data.water.forEach((item, i) => polygon(item, `water[${i}]`));
  data.buildings.forEach((item, i) => {
    polygon(item, `buildings[${i}]`);
    if (!finite(data.buildingHeights[i]) || data.buildingHeights[i] <= 0)
      fail(`buildingHeights[${i}] must be positive.`);
    const material = data.buildingMaterials?.[i];
    if (material !== undefined && material !== 'brick' && material !== 'neutral')
      fail(`buildingMaterials[${i}] must be "brick" or "neutral".`);
  });
  data.roads.forEach((road, i) => {
    if (!road || !Array.isArray(road.p) || road.p.length < 2 || road.p.some(point => !isPoint(point)))
      fail(`roads[${i}] needs at least two finite points.`);
    if (!finite(road.w) || road.w <= 0) fail(`roads[${i}].w must be positive.`);
    if (!road.p.some((point, index) =>
      index > 0 && (point[0] !== road.p[index - 1][0] || point[1] !== road.p[index - 1][1])))
      fail(`roads[${i}] must have a positive-length segment.`);
  });
  data.trees.forEach((point, i) => {
    if (!isPoint(point)) fail(`trees[${i}] must be a finite coordinate pair.`);
  });
  if (packageData.bounds !== undefined) {
    const bounds = packageData.bounds;
    if (!bounds || !isPoint(bounds.min) || !isPoint(bounds.max) ||
        bounds.max[0] <= bounds.min[0] || bounds.max[1] <= bounds.min[1])
      fail('bounds must contain finite min/max coordinate pairs with positive dimensions.');
  }
}

function editorPointToScene(point, frame) {
  const dx = point[0] - frame.fieldC[0], dy = point[1] - frame.fieldC[1];
  const cosine = Math.cos(frame.axisTheta), sine = Math.sin(frame.axisTheta);
  const u = dx * cosine + dy * sine;
  const v = -dx * sine + dy * cosine;
  return [-v, u];
}

function assetRoot(assetBase) {
  if (!assetBase) fail('assetBase is required.');
  const base = assetBase instanceof URL ? new URL(assetBase.href) : new URL(assetBase, import.meta.url);
  if (!base.pathname.endsWith('/')) base.pathname += '/';
  return base;
}

function assetURL(root, filename) {
  if (typeof filename !== 'string' || !filename.trim() ||
      filename.startsWith('/') || filename.split('/').includes('..') ||
      /^[a-z][a-z\d+.-]*:/i.test(filename))
    fail(`asset path "${filename}" must be relative to natural_assets/.`);
  const url = new URL(filename, root);
  if (url.origin !== root.origin || !url.pathname.startsWith(root.pathname))
    fail(`asset path "${filename}" escaped natural_assets/.`);
  return url;
}

async function getAssetManifest(root) {
  let response;
  try { response = await fetch(assetURL(root, 'library.json')); }
  catch (_) { fail('could not request local natural_assets/library.json.'); }
  if (!response?.ok) fail(`asset library request failed (${response?.status ?? 'no response'}).`);
  let manifest;
  try { manifest = await response.json(); }
  catch (_) { fail('asset library is not valid JSON.'); }
  if (manifest?.schema !== ASSET_SCHEMA || manifest.version !== 1)
    fail('unsupported asset library schema or version.');
  if (!Array.isArray(manifest.trees) || !manifest.textures)
    fail('asset library is missing trees or textures.');
  if (manifest.geometryBuffer !== undefined) assetURL(root, manifest.geometryBuffer);
  for (const variant of TREE_VARIANTS) {
    const item = manifest.trees.find(tree => tree.id === variant);
    if (!item || !Array.isArray(item.levels) || item.levels.length !== 3)
      fail(`asset library is missing all three LODs for ${variant}.`);
    for (let i = 0; i < LOD_DISTANCES.length; i++) {
      if (item.levels[i]?.distance !== LOD_DISTANCES[i] ||
          !item.levels[i].branches || !item.levels[i].leaves)
        fail(`${variant} must supply branch and leaf geometry at ${LOD_DISTANCES[i]}m.`);
    }
  }
  for (const key of ['grass', 'asphalt', 'paving', 'brick', 'bark']) {
    const texture = manifest.textures[key];
    if (!texture || typeof texture.color !== 'string' || !texture.color ||
        typeof texture.normal !== 'string' || !texture.normal ||
        typeof texture.roughness !== 'string' || !texture.roughness ||
        !finite(texture.sizeMeters) || texture.sizeMeters <= 0)
      fail(`texture metadata for ${key} is incomplete or invalid.`);
    assetURL(root, texture.color);
    assetURL(root, texture.normal);
    assetURL(root, texture.roughness);
  }
  for (const key of ['oak', 'ash', 'aspen']) {
    if (typeof manifest.textures.leaves?.[key] !== 'string' || !manifest.textures.leaves[key])
      fail(`leaf texture for ${key} is missing.`);
    assetURL(root, manifest.textures.leaves[key]);
  }
  return manifest;
}

function createWindowDetail(THREE, {forEmissive = false} = {}) {
  // One low-contrast facade module; UVs scale in meters, so it never reads as
  // a row of glowing graphics when viewed from the match camera.
  const size = 64, pixels = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const window = x >= 13 && x <= 23 && y >= 13 && y <= 47;
    const i = (y * size + x) * 4;
    const tone = window
      ? (forEmissive ? [40, 43, 41] : [58, 65, 65])
      : (forEmissive ? [0, 0, 0] : [198, 193, 181]);
    pixels[i] = tone[0]; pixels[i + 1] = tone[1]; pixels[i + 2] = tone[2]; pixels[i + 3] = 255;
  }
  const texture = new THREE.DataTexture(pixels, size, size, THREE.RGBAFormat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

function makeSurfaceGeometry(THREE, polygons, y, tileSize, frame) {
  const positions = [], uvs = [], indices = [];
  for (const raw of polygons) {
    const points = raw.map(point => editorPointToScene(point, frame));
    if (points.length > 1 && closePoint(points[0], points[points.length - 1])) points.pop();
    const contour = points.map(([x, z]) => new THREE.Vector2(x, z));
    const faces = THREE.ShapeUtils.triangulateShape(contour, []);
    if (!faces.length) fail('a mapped surface could not be triangulated.');
    const offset = positions.length / 3;
    points.forEach(([x, z]) => {
      positions.push(x, y, z);
      uvs.push(x / tileSize, z / tileSize);
    });
    for (const [a, b, c] of faces) indices.push(offset + a, offset + c, offset + b);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return geometry;
}

function boundsFromData(packageData) {
  const frame = packageData.frame, all = [];
  const collect = polygon => polygon.forEach(point => all.push(editorPointToScene(point, frame)));
  packageData.data.green.forEach(collect);
  packageData.data.water.forEach(collect);
  packageData.data.buildings.forEach(collect);
  packageData.data.roads.forEach(road => road.p.forEach(point =>
    all.push(editorPointToScene(point, frame))));
  packageData.data.trees.forEach(point => all.push(editorPointToScene(point, frame)));
  if (packageData.bounds) {
    [[packageData.bounds.min[0], packageData.bounds.min[1]],
      [packageData.bounds.max[0], packageData.bounds.min[1]],
      [packageData.bounds.max[0], packageData.bounds.max[1]],
      [packageData.bounds.min[0], packageData.bounds.max[1]]]
      .forEach(point => all.push(editorPointToScene(point, frame)));
  }
  if (!all.length) return {minX: -20, maxX: 20, minZ: -20, maxZ: 20};
  const result = {minX: Infinity, maxX: -Infinity, minZ: Infinity, maxZ: -Infinity};
  for (const [x, z] of all) {
    result.minX = Math.min(result.minX, x); result.maxX = Math.max(result.maxX, x);
    result.minZ = Math.min(result.minZ, z); result.maxZ = Math.max(result.maxZ, z);
  }
  return result;
}

/**
 * Render a locally packaged, mapped stadium environment.
 *
 * Road polygons retain the established renderer footprint calibration:
 * each source width w becomes a strip with half-width w * 1.25.
 */
export async function buildNaturalSurroundings(THREE, packageData, {assetBase, camera} = {}) {
  validatePackage(packageData);
  const root = assetRoot(assetBase);
  const group = new THREE.Group();
  group.name = 'NATURAL_STADIUM_SURROUNDINGS';
  group.userData.packageId = packageData.id;
  group.userData.sources = {...packageData.data.sources};
  const owned = new Set();
  let disposed = false;
  const own = value => { if (value) owned.add(value); return value; };
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    group.removeFromParent();
    for (const resource of owned) resource.dispose?.();
    owned.clear();
    group.clear();
  };
  try {
    const manifest = await getAssetManifest(root);
    let geometryBuffer = null;
    if (manifest.geometryBuffer !== undefined) {
      let response;
      try { response = await fetch(assetURL(root, manifest.geometryBuffer)); }
      catch (_) { fail('could not request local tree geometry buffer.'); }
      if (!response?.ok) fail(`tree geometry buffer request failed (${response?.status ?? 'no response'}).`);
      try {
        geometryBuffer = await response.arrayBuffer();
        if (manifest.geometryCompression === 'gzip') {
          // Django/production servers may already send Content-Encoding:gzip;
          // fetch then returns decoded bytes. Only inflate an actual gzip body.
          const signature = new Uint8Array(geometryBuffer, 0, Math.min(2, geometryBuffer.byteLength));
          if (signature[0] === 0x1f && signature[1] === 0x8b) {
            if (typeof DecompressionStream === 'undefined')
              fail('this browser cannot decompress the prepared tree library.');
            const stream = new Blob([geometryBuffer]).stream().pipeThrough(new DecompressionStream('gzip'));
            geometryBuffer = await new Response(stream).arrayBuffer();
          }
        } else if (manifest.geometryCompression !== undefined) fail('unsupported tree compression.');
      }
      catch (_) { fail('tree geometry buffer could not be read.'); }
      if (!(geometryBuffer instanceof ArrayBuffer) || geometryBuffer.byteLength === 0)
        fail('tree geometry buffer is empty or invalid.');
    }
    const textureLoader = new THREE.TextureLoader();
    const textureSpecs = {
      grass: manifest.textures.grass,
      asphalt: manifest.textures.asphalt,
      paving: manifest.textures.paving,
      brick: manifest.textures.brick,
      bark: manifest.textures.bark,
    };
    const textureEntries = [
      ...Object.entries(textureSpecs).flatMap(([key, spec]) =>
        [['map', key, spec.color], ['normalMap', `${key}Normal`, spec.normal],
          ['roughnessMap', `${key}Roughness`, spec.roughness]]),
      ...Object.entries(manifest.textures.leaves).map(([kind, filename]) =>
        ['leaf', kind, filename]),
    ];
    const loaded = await Promise.allSettled(textureEntries.map(async ([kind, key, filename]) => {
      let texture;
      try { texture = await textureLoader.loadAsync(assetURL(root, filename).href); }
      catch (_) { throw new Error(`Natural surroundings: local texture "${filename}" failed to load.`); }
      own(texture);
      if (kind !== 'leaf') {
        texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
        texture.colorSpace = kind === 'map' ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        // Generated surface UVs are already expressed in physical tile units.
        texture.repeat.set(1, 1);
        texture.needsUpdate = true;
      } else {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
        texture.needsUpdate = true;
      }
      return [kind === 'leaf' ? `leaf:${key}` : key, texture];
    }));
    const textureError = loaded.find(result => result.status === 'rejected');
    if (textureError) throw textureError.reason;
    const textures = Object.fromEntries(loaded.map(result => result.value));

    const geometryLoader = new THREE.BufferGeometryLoader();
    const treeGeometries = {};
    const triangleCountsByLOD = {0: 0, 160: 0, 330: 0};
    const parseTreeGeometry = serialized => {
      if (serialized?.binary === true) {
        if (!geometryBuffer) fail('tree geometry references a missing manifest.geometryBuffer.');
        const geometry = own(new THREE.BufferGeometry());
        const constructors = {Float32Array, Uint32Array};
        const makeView = (descriptor, expectedType, attributeName) => {
          if (!descriptor || descriptor.type !== expectedType ||
              !Number.isInteger(descriptor.byteOffset) || descriptor.byteOffset < 0 ||
              !Number.isInteger(descriptor.count) || descriptor.count <= 0)
            fail(`binary tree ${attributeName} descriptor is malformed.`);
          const Type = constructors[descriptor.type];
          const itemSize = descriptor.itemSize ?? 1;
          if (!Number.isInteger(itemSize) || itemSize <= 0 || descriptor.count % itemSize !== 0)
            fail(`binary tree ${attributeName} count or itemSize is invalid.`);
          const bytes = Type.BYTES_PER_ELEMENT;
          if (descriptor.byteOffset % bytes !== 0 ||
              descriptor.byteOffset + descriptor.count * bytes > geometryBuffer.byteLength)
            fail(`binary tree ${attributeName} view is misaligned or outside trees.bin.`);
          const view = new Type(geometryBuffer, descriptor.byteOffset, descriptor.count);
          if (expectedType === 'Float32Array' && !view.every(finite))
            fail(`binary tree ${attributeName} contains non-finite values.`);
          return {view, itemSize};
        };
        for (const [name, expectedItemSize] of [['position', 3], ['normal', 3], ['uv', 2]]) {
          const descriptor = serialized.attributes?.[name];
          const result = makeView(descriptor, 'Float32Array', name);
          if (result.itemSize !== expectedItemSize)
            fail(`binary tree ${name} itemSize must be ${expectedItemSize}.`);
          geometry.setAttribute(name, new THREE.BufferAttribute(result.view, result.itemSize));
        }
        const vertexCount = geometry.getAttribute('position').count;
        if (geometry.getAttribute('normal').count !== vertexCount ||
            geometry.getAttribute('uv').count !== vertexCount)
          fail('binary tree attributes do not have matching vertex counts.');
        const index = makeView(serialized.index, 'Uint32Array', 'index');
        if (index.itemSize !== 1 || index.view.length % 3 !== 0 ||
            !index.view.every(value => value < vertexCount))
          fail('binary tree index buffer is invalid.');
        geometry.setIndex(new THREE.BufferAttribute(index.view, 1));
        return own(geometry);
      }
      const json = serialized?.data ? serialized : {
        metadata: {version: 4.6, type: 'BufferGeometry', generator: 'BufferGeometry.toJSON'},
        type: 'BufferGeometry', data: serialized,
      };
      if (!json.data?.attributes?.position)
        fail('tree asset geometry must contain BufferGeometry.toJSON() position data.');
      for (const attribute of Object.values(json.data.attributes)) {
        if (!attribute || !Number.isInteger(attribute.itemSize) || attribute.itemSize < 1 ||
            !Array.isArray(attribute.array) || !attribute.array.length ||
            attribute.array.length % attribute.itemSize !== 0 ||
            !attribute.array.every(finite))
          fail('tree asset geometry contains malformed or non-finite attributes.');
      }
      const vertexCount = json.data.attributes.position.array.length / 3;
      if (json.data.index && (!Array.isArray(json.data.index.array) ||
          !json.data.index.array.length ||
          !json.data.index.array.every(index =>
            Number.isInteger(index) && index >= 0 && index < vertexCount)))
        fail('tree asset geometry contains a malformed index buffer.');
      return own(geometryLoader.parse(json));
    };
    for (const variant of TREE_VARIANTS) {
      const entry = manifest.trees.find(tree => tree.id === variant);
      treeGeometries[variant] = entry.levels.map((level, lodIndex) => {
        const branches = parseTreeGeometry(level.branches);
        const leaves = parseTreeGeometry(level.leaves);
        for (const geometry of [branches, leaves]) {
          if (!geometry.getAttribute('position')) fail(`${variant} asset geometry has no positions.`);
          if (!geometry.getAttribute('normal')) geometry.computeVertexNormals();
          geometry.computeBoundingSphere();
          triangleCountsByLOD[LOD_DISTANCES[lodIndex]] +=
            (geometry.index?.count ?? geometry.getAttribute('position').count) / 3;
        }
        return {branches, leaves};
      });
    }

    const mats = {};
    for (const key of Object.keys(textureSpecs)) {
      mats[key] = own(new THREE.MeshStandardMaterial({
        color: '#ffffff', map: textures[key], normalMap: textures[`${key}Normal`],
        roughness: 1, roughnessMap: textures[`${key}Roughness`], metalness: 0,
        side: THREE.DoubleSide,
      }));
    }
    const neutralWindowMap = own(createWindowDetail(THREE));
    neutralWindowMap.repeat.set(1, 3.8 / 3.1);
    neutralWindowMap.needsUpdate = true;
    const brickWindowMap = own(createWindowDetail(THREE, {forEmissive: true}));
    brickWindowMap.repeat.set(manifest.textures.brick.sizeMeters / 3.8,
      manifest.textures.brick.sizeMeters / 3.1);
    brickWindowMap.needsUpdate = true;
    const wallMaterials = {
      brick: own(new THREE.MeshStandardMaterial({
        color: '#d2c6b5', map: textures.brick, normalMap: textures.brickNormal,
        roughness: 1, roughnessMap: textures.brickRoughness, metalness: 0,
        side: THREE.DoubleSide,
        emissive: '#827d70', emissiveMap: brickWindowMap, emissiveIntensity: 0.09,
      })),
      neutral: own(new THREE.MeshStandardMaterial({
        color: '#ffffff', map: neutralWindowMap, roughness: 0.88,
        metalness: 0, side: THREE.DoubleSide,
      })),
    };
    const addMesh = (name, geometry, material) => {
      own(geometry);
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = name;
      group.add(mesh);
      return mesh;
    };
    const extents = boundsFromData(packageData);
    const padding = 24;
    const width = Math.max(40, extents.maxX - extents.minX + padding * 2);
    const depth = Math.max(40, extents.maxZ - extents.minZ + padding * 2);
    const centerX = (extents.maxX + extents.minX) / 2;
    const centerZ = (extents.maxZ + extents.minZ) / 2;
    const groundGeometry = own(new THREE.PlaneGeometry(width, depth, 1, 1));
    const ground = new THREE.Mesh(groundGeometry, mats.paving);
    ground.name = 'NATURAL_GROUND';
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(centerX, -0.38, centerZ);
    groundGeometry.setAttribute('uv', new THREE.Float32BufferAttribute([
      -width / 2 / manifest.textures.paving.sizeMeters, -depth / 2 / manifest.textures.paving.sizeMeters,
      width / 2 / manifest.textures.paving.sizeMeters, -depth / 2 / manifest.textures.paving.sizeMeters,
      -width / 2 / manifest.textures.paving.sizeMeters, depth / 2 / manifest.textures.paving.sizeMeters,
      width / 2 / manifest.textures.paving.sizeMeters, depth / 2 / manifest.textures.paving.sizeMeters,
    ], 2));
    groundGeometry.computeVertexNormals();
    group.add(ground);

    const data = packageData.data;
    if (data.green.length)
      addMesh('NATURAL_MAPPED_GREEN', makeSurfaceGeometry(
        THREE, data.green, -0.24, manifest.textures.grass.sizeMeters, packageData.frame), mats.grass);
    if (data.water.length) {
      const waterMaterial = own(new THREE.MeshStandardMaterial({
        color: '#6c898d', map: textures.paving, normalMap: textures.pavingNormal,
        roughness: 1, roughnessMap: textures.pavingRoughness,
        metalness: 0, side: THREE.DoubleSide,
      }));
      addMesh('NATURAL_MAPPED_WATER', makeSurfaceGeometry(
        THREE, data.water, -0.20, manifest.textures.paving.sizeMeters, packageData.frame), waterMaterial);
    }
    if (data.roads.length) {
      const roadPositions = [], roadUvs = [], roadIndices = [];
      const addTriangle = (a, b, c, tileSize) => {
        const base = roadPositions.length / 3;
        [a, b, c].forEach(([x, y, z]) => {
          roadPositions.push(x, y, z);
          roadUvs.push(x / tileSize, z / tileSize);
        });
        roadIndices.push(base, base + 2, base + 1);
      };
      for (const road of data.roads) {
        const points = road.p.map(point => editorPointToScene(point, packageData.frame));
        const half = road.w * 1.25;
        for (let i = 1; i < points.length; i++) {
          const [ax, az] = points[i - 1], [bx, bz] = points[i];
          const length = Math.hypot(bx - ax, bz - az);
          if (!length) continue;
          const nx = -(bz - az) / length * half, nz = (bx - ax) / length * half;
          const a = [ax + nx, -0.27, az + nz], b = [bx + nx, -0.27, bz + nz];
          const c = [bx - nx, -0.27, bz - nz], d = [ax - nx, -0.27, az - nz];
          addTriangle(a, b, c, manifest.textures.asphalt.sizeMeters);
          addTriangle(a, c, d, manifest.textures.asphalt.sizeMeters);
          // Rounded joins preserve the former renderer's mapped street footprint.
          for (let step = 0; step < 12; step++) {
            const angleA = step * Math.PI / 6, angleB = (step + 1) * Math.PI / 6;
            addTriangle([ax, -0.27, az],
              [ax + Math.cos(angleA) * half, -0.27, az + Math.sin(angleA) * half],
              [ax + Math.cos(angleB) * half, -0.27, az + Math.sin(angleB) * half],
              manifest.textures.asphalt.sizeMeters);
          }
        }
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(roadPositions, 3));
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute(roadUvs, 2));
      geometry.setIndex(roadIndices);
      geometry.computeVertexNormals();
      geometry.computeBoundingSphere();
      addMesh('NATURAL_MAPPED_ROADS', geometry, mats.asphalt);
    }

    const buildingGroups = {brick: {p: [], uv: [], i: []}, neutral: {p: [], uv: [], i: []}};
    const roofPolygons = [];
    data.buildings.forEach((raw, buildingIndex) => {
      const source = raw.slice();
      if (source.length > 1 && closePoint(source[0], source[source.length - 1])) source.pop();
      const points = source.map(point => editorPointToScene(point, packageData.frame));
      const height = data.buildingHeights[buildingIndex];
      const detail = buildingGroups[data.buildingMaterials?.[buildingIndex] || 'neutral'];
      const roofs = points.map(([x, z]) => [x, z]);
      roofPolygons.push({points: roofs, height});
      for (let edge = 0; edge < points.length; edge++) {
        const [ax, az] = points[edge], [bx, bz] = points[(edge + 1) % points.length];
        const length = Math.hypot(bx - ax, bz - az);
        if (length === 0) continue;
        const base = detail.p.length / 3;
        detail.p.push(ax, -0.05, az, bx, -0.05, bz, bx, height, bz, ax, height, az);
        const wallTile = data.buildingMaterials?.[buildingIndex] === 'brick'
          ? manifest.textures.brick.sizeMeters : 3.8;
        detail.uv.push(0, 0, length / wallTile, 0,
          length / wallTile, height / wallTile, 0, height / wallTile);
        detail.i.push(base, base + 1, base + 2, base, base + 2, base + 3);
      }
    });
    for (const key of ['neutral', 'brick']) {
      const bucket = buildingGroups[key];
      if (!bucket.p.length) continue;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(bucket.p, 3));
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute(bucket.uv, 2));
      geometry.setIndex(bucket.i);
      geometry.computeVertexNormals();
      geometry.computeBoundingSphere();
      addMesh(`NATURAL_BUILDING_WALLS_${key.toUpperCase()}`, geometry, wallMaterials[key]);
    }
    if (roofPolygons.length) {
      const roofPositions = [], roofUvs = [], roofIndices = [];
      for (const {points, height} of roofPolygons) {
        const contour = points.map(([x, z]) => new THREE.Vector2(x, z));
        const faces = THREE.ShapeUtils.triangulateShape(contour, []);
        const offset = roofPositions.length / 3;
        points.forEach(([x, z]) => {
          roofPositions.push(x, height, z);
          roofUvs.push(x / manifest.textures.paving.sizeMeters, z / manifest.textures.paving.sizeMeters);
        });
        faces.forEach(([a, b, c]) => roofIndices.push(offset + a, offset + c, offset + b));
      }
      const finalRoofGeometry = new THREE.BufferGeometry();
      finalRoofGeometry.setAttribute('position', new THREE.Float32BufferAttribute(roofPositions, 3));
      finalRoofGeometry.setAttribute('uv', new THREE.Float32BufferAttribute(roofUvs, 2));
      finalRoofGeometry.setIndex(roofIndices);
      finalRoofGeometry.computeVertexNormals();
      finalRoofGeometry.computeBoundingSphere();
      addMesh('NATURAL_BUILDING_ROOFS', finalRoofGeometry, mats.paving);
    }

    const species = ['oak', 'oak', 'ash', 'aspen'];
    const assignments = TREE_VARIANTS.map(() => []);
    data.trees.forEach((point, index) => {
      const [x, z] = editorPointToScene(point, packageData.frame);
      const hash = Math.abs(Math.sin(point[0] * 12.9898 + point[1] * 78.233) * 43758.5453);
      const variantIndex = Math.floor((hash % 1) * TREE_VARIANTS.length);
      const scale = 0.88 + (hash % 1) * 0.22;
      assignments[variantIndex].push({x, z, scale, sourceIndex: index});
    });
    const foliage = [];
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3(), rotation = new THREE.Quaternion();
    const scaleVector = new THREE.Vector3();
    TREE_VARIANTS.forEach((variant, variantIndex) => {
      const trees = assignments[variantIndex];
      if (!trees.length) return;
      for (let lod = 0; lod < 3; lod++) {
        const geometryPair = treeGeometries[variant][lod];
        const branchMaterial = own(new THREE.MeshStandardMaterial({
          color: '#ffffff', map: textures.bark,
          normalMap: textures.barkNormal, roughness: 1,
          roughnessMap: textures.barkRoughness,
          metalness: 0,
        }));
        const kind = species[variantIndex];
        const leafMaterial = own(new THREE.MeshStandardMaterial({
          color: '#c1cbb1', map: textures[`leaf:${kind}`],
          roughness: 0.94, metalness: 0, side: THREE.DoubleSide,
          transparent: false, alphaTest: 0.38, depthWrite: true,
        }));
        const branches = own(new THREE.InstancedMesh(geometryPair.branches, branchMaterial, trees.length));
        const leaves = own(new THREE.InstancedMesh(geometryPair.leaves, leafMaterial, trees.length));
        branches.name = `NATURAL_TREES_${variant}_LOD${lod}_BRANCHES`;
        leaves.name = `NATURAL_TREES_${variant}_LOD${lod}_LEAVES`;
        branches.count = leaves.count = 0;
        branches.frustumCulled = leaves.frustumCulled = false;
        group.add(branches, leaves);
        foliage.push({variantIndex, lod, trees, branches, leaves});
      }
    });
    const viewFrustum = new THREE.Frustum();
    const projection = new THREE.Matrix4();
    const treeSphere = new THREE.Sphere();
    const variantBounds = TREE_VARIANTS.map(variant => {
      const pair = treeGeometries[variant][0];
      pair.branches.computeBoundingBox(); pair.leaves.computeBoundingBox();
      return pair.branches.boundingBox.clone().union(pair.leaves.boundingBox).getBoundingSphere(new THREE.Sphere());
    });
    const updateLOD = nextCamera => {
      if (disposed || !nextCamera?.position) return;
      const cull = nextCamera.isCamera === true;
      if (cull) {
        nextCamera.updateMatrixWorld();
        projection.multiplyMatrices(nextCamera.projectionMatrix, nextCamera.matrixWorldInverse);
        viewFrustum.setFromProjectionMatrix(projection);
      }
      for (const entry of foliage) {
        let count = 0;
        for (const tree of entry.trees) {
          if (cull) {
            const bounds = variantBounds[entry.variantIndex];
            treeSphere.center.copy(bounds.center).multiplyScalar(tree.scale);
            treeSphere.center.x += tree.x; treeSphere.center.z += tree.z;
            treeSphere.radius = bounds.radius * tree.scale;
            if (!viewFrustum.intersectsSphere(treeSphere)) continue;
          }
          const dx = nextCamera.position.x - tree.x, dz = nextCamera.position.z - tree.z;
          const dy = nextCamera.position.y;
          const distance = Math.hypot(dx, dy, dz);
          const lod = distance <= 160 ? 0 : distance <= 330 ? 1 : 2;
          if (lod !== entry.lod) continue;
          position.set(tree.x, 0, tree.z);
          rotation.identity();
          scaleVector.setScalar(tree.scale);
          matrix.compose(position, rotation, scaleVector);
          entry.branches.setMatrixAt(count, matrix);
          entry.leaves.setMatrixAt(count, matrix);
          count++;
        }
        entry.branches.count = entry.leaves.count = count;
        entry.branches.instanceMatrix.needsUpdate = entry.leaves.instanceMatrix.needsUpdate = true;
      }
    };
    updateLOD(camera);
    const metrics = {
      roads: data.roads.length, buildings: data.buildings.length, green: data.green.length,
      water: data.water.length, trees: data.trees.length, shrubs: 0,
      treeDrawBatches: foliage.length * 2, roadHalfWidthScale: 1.25,
      triangleCountsByLOD, geometryBufferBytes: geometryBuffer?.byteLength ?? 0,
      mappedBoundsMeters: {
        width: extents.maxX - extents.minX, depth: extents.maxZ - extents.minZ,
      },
    };
    group.userData.metrics = metrics;
    return {group, dispose, updateLOD, metrics};
  } catch (error) {
    dispose();
    throw error;
  }
}
