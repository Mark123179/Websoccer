const finite = value => typeof value === 'number' && Number.isFinite(value);
const point = value => Array.isArray(value) && value.length === 2 && value.every(finite);
const fail = message => { throw new Error(`Natural surroundings v2: ${message}`); };

function validate(data) {
  if (data?.schema !== 'websoccer.natural-surroundings' || data.version !== 1 ||
      data.visualVersion !== 2 || data.units !== 'm')
    fail('unsupported mapped package; expected schema v1 / visualVersion 2.');
  if (data.frame?.sceneAxes !== 'pitch-west-camera')
    fail('the pitch-west-camera frame marker is required.');
  if (typeof data.model?.mirror !== 'boolean' || data.model.mirrorAxis !== 'longitudinal')
    fail('model-only mirror calibration must specify a boolean mirror on the longitudinal axis.');
  if (data.model.mirror && data.model.verified !== true)
    fail('model mirror is enabled but has not been verified; refusing an unapproved transform.');
  const mapped = data.data;
  for (const key of ['roads', 'buildings', 'buildingHeights', 'green', 'water', 'trees'])
    if (!Array.isArray(mapped?.[key])) fail(`data.${key} must be an array.`);
  if (mapped.buildingHeights.length !== mapped.buildings.length)
    fail('building heights do not match the building polygons.');
  const polygonPoints = value => Array.isArray(value) ? value : value?.poly || value?.p;
  const polygon = (value, label) => {
    value = polygonPoints(value);
    if (!Array.isArray(value) || value.length < 3 || !value.every(point))
      fail(`${label} is not a finite polygon.`);
  };
  ['green', 'water', 'buildings', 'parking', 'forest', 'scrub', 'grassTagged', 'sports',
        'landuse', 'buildingsTagged'].forEach(key => (mapped[key] || []).forEach((item, index) =>
      polygon(Array.isArray(item) ? item : item.poly || item.p, `${key}[${index}]`)));
  mapped.trees.forEach((p, i) => { if (!point(p)) fail(`trees[${i}] is invalid.`); });
  mapped.roads.forEach((road, i) => {
    if (!Array.isArray(road?.p) || road.p.length < 2 || !road.p.every(point) ||
        !finite(road.w) || road.w <= 0) fail(`roads[${i}] is invalid.`);
  });
  if (!mapped.sourceDetail && !data.sourceDetail) fail('sourceDetail attribution is required.');
}

const directPoint = ([fieldX, fieldY]) => [fieldY, fieldX];
const polygonPoints = item => Array.isArray(item) ? item : item?.poly || item?.p;
const hashUint = value => {
  let hash = 2166136261;
  for (const character of String(value)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};
const seededUnit = value => hashUint(value) / 0x100000000;
const pointInside = (x, z, raw) => {
  const ring = polygonPoints(raw);
  if (!ring?.length) return false;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = directPoint(ring[i]), b = directPoint(ring[j]);
    if ((a[1] > z) !== (b[1] > z) &&
        x < (b[0] - a[0]) * (z - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
};
const rawPolygons = items => (items || []).map(polygonPoints).filter(Boolean);

export function buildMappedVegetationRepresentatives(data, {forestSpacing = 20, scrubSpacing = 10} = {}) {
  // Feature polygons can cross the source query circle by a few metres. The
  // 20m allowance samples those exact clipped polygons but never extrapolates them.
  const radius = Math.max(1, Number((data.sourceDetail || {}).radius_m) || 420) + 20;
  const grass = (data.grassTagged || []).filter(item =>
    ['grass', 'grassland'].includes(item.kind));
  const surfaceParking = (data.parking || []).filter(item => item?.parking === 'surface');
  const protectedPolygons = [
    ...rawPolygons(grass), ...rawPolygons(data.sports), ...rawPolygons(data.buildings),
    ...rawPolygons(surfaceParking),
  ];
  const mappedTrees = (data.trees || []).map(directPoint);
  const accepted = [];
  const sample = (features, spacing, kind) => {
    const results = [];
    for (let featureIndex = 0; featureIndex < features.length; featureIndex++) {
      const feature = features[featureIndex], polygon = polygonPoints(feature);
      if (!polygon?.length) continue;
      const points = polygon.map(directPoint);
      const xs = points.map(point => point[0]), zs = points.map(point => point[1]);
      const sourceId = feature.id ?? featureIndex;
      const offsetX = seededUnit(`${kind}:${sourceId}:x`) * spacing;
      const offsetZ = seededUnit(`${kind}:${sourceId}:z`) * spacing;
      const x0 = Math.floor((Math.max(-radius, Math.min(...xs)) - offsetX) / spacing) *
        spacing + offsetX + spacing / 2;
      const z0 = Math.floor((Math.max(-radius, Math.min(...zs)) - offsetZ) / spacing) *
        spacing + offsetZ + spacing / 2;
      const xEnd = Math.min(0, Math.max(...xs));
      const zEnd = Math.min(radius, Math.max(...zs));
      for (let x = x0; x <= xEnd; x += spacing) {
        for (let z = z0; z <= zEnd; z += spacing) {
          if (x * x + z * z > radius * radius || !pointInside(x, z, polygon)) continue;
          if (protectedPolygons.some(blocker => pointInside(x, z, blocker))) continue;
          const tooClose = [...mappedTrees, ...accepted].some(point =>
            Math.hypot(x - point[0], z - point[1]) < 2.5);
          if (tooClose) continue;
          const point = {x, z, featureId: sourceId,
            variant: seededUnit(`${kind}:${sourceId}:${x.toFixed(3)}:${z.toFixed(3)}:variant`)};
          accepted.push([x, z]);
          results.push(point);
        }
      }
    }
    return results;
  };
  return {
    forest: sample(data.forest || [], forestSpacing, 'forest'),
    scrub: sample(data.scrub || [], scrubSpacing, 'scrub'),
  };
}

function polygonGeometry(THREE, polygons, y, uvScale = 1) {
  const positions = [], uvs = [], indices = [];
  for (const raw of polygons) {
    const points = raw.map(directPoint);
    if (points.length > 3 && points[0][0] === points.at(-1)[0] &&
        points[0][1] === points.at(-1)[1]) points.pop();
    const contour = points.map(([x, z]) => new THREE.Vector2(x, z));
    const faces = THREE.ShapeUtils.triangulateShape(contour, []);
    if (!faces.length) continue;
    const offset = positions.length / 3;
    points.forEach(([x, z]) => {
      positions.push(x, y, z);
      uvs.push(x / uvScale, z / uvScale);
    });
    faces.forEach(([a, b, c]) => indices.push(offset + a, offset + c, offset + b));
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return geometry;
}

function bounds(data) {
  const points = [];
  const collect = raw => raw.forEach(p => points.push(directPoint(p)));
  for (const key of ['green', 'water', 'buildings', 'parking', 'sports', 'landuse'])
    for (const item of data[key] || []) collect(Array.isArray(item) ? item : item.poly || item.p);
  for (const road of data.roads) road.p.forEach(p => points.push(directPoint(p)));
  data.trees.forEach(p => points.push(directPoint(p)));
  const xs = points.map(p => p[0]), zs = points.map(p => p[1]);
  if (!points.length) return {minX: -40, maxX: 40, minZ: -40, maxZ: 40};
  return {minX: Math.min(...xs), maxX: Math.max(...xs), minZ: Math.min(...zs), maxZ: Math.max(...zs)};
}

function octaViewIndex(direction) {
  const length = Math.abs(direction.x) + Math.abs(direction.y) + Math.abs(direction.z) || 1;
  let x = direction.x / length, z = direction.z / length;
  const up = direction.y / length;
  if (up < 0) {
    const oldX = x;
    x = (1 - Math.abs(z)) * Math.sign(oldX || 1);
    z = (1 - Math.abs(oldX)) * Math.sign(z || 1);
  }
  const ix = Math.max(0, Math.min(7, Math.floor((x * .5 + .5) * 8)));
  const iy = Math.max(0, Math.min(7, Math.floor((z * .5 + .5) * 8)));
  return iy * 8 + ix;
}

function addAtlasShader(material, viewIndex, {preserveBakedColor = false} = {}) {
  material.onBeforeCompile = shader => {
    shader.uniforms.uTreeView = {value: viewIndex.value};
    shader.vertexShader = `varying vec2 vTreeUv;\n${shader.vertexShader}`
      .replace('#include <uv_vertex>', '#include <uv_vertex>\n vTreeUv = uv;');
    shader.fragmentShader = `uniform float uTreeView;\nvarying vec2 vTreeUv;\n${shader.fragmentShader}`;
    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <map_fragment>',
      `vec2 atlasCell = vec2(mod(uTreeView, 8.0), floor(uTreeView / 8.0));
       vec2 atlasUv = (atlasCell + (vec2(0.5) + vTreeUv * 255.0) / 256.0) / 8.0;
       #ifdef USE_MAP
        vec4 sampledDiffuseColor = texture2D(map, atlasUv);
        diffuseColor *= sampledDiffuseColor;
      #endif`,
    );
    if (preserveBakedColor) {
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <emissivemap_fragment>',
        `#ifdef USE_EMISSIVEMAP
           vec4 emissiveColor = texture2D(emissiveMap, atlasUv);
           #ifdef DECODE_VIDEO_TEXTURE_EMISSIVE
             emissiveColor = sRGBTransferEOTF(emissiveColor);
           #endif
           totalEmissiveRadiance *= emissiveColor.rgb;
         #endif`,
      ).replace(
        '#include <opaque_fragment>',
        `#ifdef USE_SHADOWMAP
           outgoingLight *= mix(0.56, 1.0, getShadowMask());
         #endif
         #include <opaque_fragment>`,
      );
    }
    material.userData.treeShader = shader;
  };
  material.customProgramCacheKey = () => 'tree-impostor-hemi-octa-source-albedo-shadow-v3';
}

export function createImpostorMaterial(THREE, atlas, viewIndex, depth = false) {
  const material = depth
    ? new THREE.MeshDepthMaterial({map: atlas, alphaTest: .26, depthPacking: THREE.RGBADepthPacking,
      side: THREE.DoubleSide})
    : new THREE.MeshLambertMaterial({map: atlas, color:'#000000', emissive:'#ffffff',
      emissiveMap:atlas,emissiveIntensity:1,alphaTest:.26,side:THREE.DoubleSide,transparent:false});
  addAtlasShader(material, viewIndex, {preserveBakedColor:!depth});
  return material;
}

export function buildParkingPoints(data, vegetation = {forest: [], scrub: []}) {
  const parkingFeatures = (data.parking || []).filter(item => item?.parking === 'surface');
  const clearance = 2.5;
  const vegetationPoints = [
    ...(data.trees || []).map(directPoint),
    ...(vegetation.forest || []).map(point => [point.x, point.z]),
    ...(vegetation.scrub || []).map(point => [point.x, point.z]),
  ];
  const obstacles = [...rawPolygons(data.buildings), ...vegetationPoints];
  const result = [];
  let eligibleBays = 0;
  const blocked = (x, z) => obstacles.some(p => {
    if (Array.isArray(p) && p.length === 2 && p.every(finite))
      return Math.hypot(x - p[0], z - p[1]) < clearance;
    const pts = p.map(directPoint);
    const xs = pts.map(v => v[0]), zs = pts.map(v => v[1]);
    return x > Math.min(...xs) - 2.4 && x < Math.max(...xs) + 2.4 &&
      z > Math.min(...zs) - 4.8 && z < Math.max(...zs) + 4.8;
  });
  parkingFeatures.forEach(feature => {
    const raw = polygonPoints(feature);
    if (!raw?.length) return;
    const pts = raw.map(directPoint), xs = pts.map(p => p[0]), zs = pts.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
    const firstX = Math.floor(x0 / 5) * 5 + 2.5;
    const firstZ = Math.floor(z0 / 5) * 5 + 2.5;
    // 90-degree parking bays, two staggered rows with a center aisle; positions
    // are accepted only when the full vehicle footprint remains in its OSM polygon.
    // Only explicit parking=surface features are eligible; each bay is 2.5×5m.
    // Cars occupy two adjacent width cells; every second 5m depth cell is an aisle.
    for (let row = 0, z = firstZ; z < z1 - 2.5; row++, z += 10) {
      for (let column = 0, x = firstX; x < x1 - 2.5; column++, x += 5) {
        const seed = seededUnit(`${feature.id || 'surface'}:${column}:${row}:jitter`);
        const xx = x + (seed - .5) * .45;
        const zz = z + (row % 2 ? 1.1 : 0);
        const occupancy = seededUnit(`${feature.id || 'surface'}:${column}:${row}:occupancy`);
        const vehicle = seededUnit(`${feature.id || 'surface'}:${column}:${row}:vehicle`);
        if (![[xx - 1.2, zz - 2.3], [xx + 1.2, zz - 2.3],
          [xx - 1.2, zz + 2.3], [xx + 1.2, zz + 2.3]]
          .every(([cx, cz]) => pointInside(cx, cz, raw)) || blocked(xx, zz)) continue;
        eligibleBays++;
        if (occupancy < .7) result.push({x: xx, z: zz, parkingId: feature.id,
          yaw: row % 2 ? Math.PI : 0, type: Math.floor(vehicle * 10)});
      }
    }
  });
  return {points: result, eligibleBays, lots: parkingFeatures.length,
    rejectedNonSurfaceLots: (data.parking || []).length - parkingFeatures.length};
}

export async function buildNaturalSurroundingsV2(THREE, packageData, {assetBase, camera} = {}) {
  validate(packageData);
  if (!assetBase) fail('local assetBase is required.');
  const root = assetBase instanceof URL ? new URL(assetBase.href) : new URL(assetBase, import.meta.url);
  if (!root.pathname.endsWith('/')) root.pathname += '/';
  const group = new THREE.Group();
  group.name = 'NATURAL_STADIUM_SURROUNDINGS_V2';
  group.userData.sourceDetail = packageData.data.sourceDetail || packageData.sourceDetail;
  const owned = new Set(), own = value => { if (value) owned.add(value); return value; };
  let disposed = false;
  const dispose = () => {
    if (disposed) return;
    disposed = true; group.removeFromParent();
    owned.forEach(value => value.dispose?.()); owned.clear(); group.clear();
  };
  try {
    const manifestResponse = await fetch(new URL('library_v2.json', root));
    if (!manifestResponse.ok) fail(`local visual asset manifest failed (${manifestResponse.status}).`);
    const manifest = await manifestResponse.json();
    const data = packageData.data;
    if (manifest.schema !== 'websoccer.natural-assets' || manifest.version !== 2 ||
        !manifest.trees?.length || !manifest.carModel || !manifest.surfaces?.aerialGrass ||
        !manifest.surfaces?.asphalt || !manifest.hdri?.day || !manifest.hdri?.night)
      fail('visual asset manifest is incomplete; refusing to render fallback graphics.');
    if (data.scrub?.length && !manifest.shrubs?.length)
      fail('mapped scrub needs a source-derived shrub atlas; refusing a generic shrub fallback.');
    const textureLoader = new THREE.TextureLoader();
    const loadTexture = async (name, colorSpace = THREE.SRGBColorSpace) => {
      const texture = await textureLoader.loadAsync(new URL(name, root).href);
      texture.colorSpace = colorSpace; texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
      texture.anisotropy = 8; texture.needsUpdate = true; return own(texture);
    };
    const textureResults = await Promise.allSettled([
      loadTexture(manifest.surfaces.aerialGrass.color),
      loadTexture(manifest.surfaces.grassDetail.color),
      loadTexture(manifest.surfaces.asphalt.color),
      loadTexture(manifest.trees[0].atlas),
    ]);
    const textureFailure = textureResults.find(result => result.status === 'rejected');
    if (textureFailure) throw textureFailure.reason;
    const [grass, grassGround, asphalt, atlas] = textureResults.map(result => result.value);
    const extents = bounds(data), centerX = (extents.minX + extents.maxX) / 2,
      centerZ = (extents.minZ + extents.maxZ) / 2;
    const width = Math.max(50, extents.maxX - extents.minX + 50);
    const depth = Math.max(50, extents.maxZ - extents.minZ + 50);
    const addMesh = (name, geometry, material, {castShadow = true, receiveShadow = true} = {}) => {
      own(geometry);
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = name; mesh.castShadow = castShadow; mesh.receiveShadow = receiveShadow;
      group.add(mesh); return mesh;
    };
    const groundMat = own(new THREE.MeshStandardMaterial({color:'#7d8377',roughness:1,metalness:0}));
    const groundGeom = own(new THREE.PlaneGeometry(width, depth));
    const ground = new THREE.Mesh(groundGeom, groundMat);
    ground.name = 'NATURAL_GROUND_BASE'; ground.rotation.x = -Math.PI / 2;
    ground.position.set(centerX, -.42, centerZ); ground.receiveShadow = true; group.add(ground);
    const mappedGreen = [...(data.green || []), ...(data.forest || []), ...(data.scrub || [])]
      .map(item => Array.isArray(item) ? item : item.poly || item.p);
    if (mappedGreen.length)
      addMesh('NATURAL_MAPPED_GREEN_AERIAL', polygonGeometry(THREE, mappedGreen, -.25, 15),
        own(new THREE.MeshStandardMaterial({map: grass, roughness: 1, metalness: 0, side: THREE.DoubleSide})));
    const sourcePolygon = item => Array.isArray(item) ? item : item.poly || item.p;
    const sportData = data.sports || [];
    const turfSports = sportData.filter(item =>
      ['grass','artificial_turf'].includes(item.surface)).map(sourcePolygon);
    const tartanSports = sportData.filter(item => item.surface === 'tartan').map(sourcePolygon);
    const hardSports = sportData.filter(item => item.kind === 'pitch' &&
      !['grass','artificial_turf'].includes(item.surface) && item.surface !== 'tartan')
      .map(sourcePolygon);
    const polygonsForSport = (name, polygons, y, material) => {
      if(polygons.length) addMesh(name,polygonGeometry(THREE,polygons,y,15),
        own(new THREE.MeshStandardMaterial(material)));
    };
    polygonsForSport('NATURAL_MAPPED_SPORTS_TURF',turfSports,-.23,
      {map:grassGround,color:'#78ac58',roughness:.94,metalness:0,side:THREE.DoubleSide});
    polygonsForSport('NATURAL_MAPPED_SPORTS_TARTAN',tartanSports,-.225,
      {map:asphalt,color:'#b29188',roughness:.96,metalness:0,side:THREE.DoubleSide});
    polygonsForSport('NATURAL_MAPPED_SPORTS_HARD_COURTS',hardSports,-.23,
      {map:asphalt,color:'#c0b9ad',roughness:.96,metalness:0,side:THREE.DoubleSide});
    const allotments=(data.landuse||[]).filter(item=>item.kind==='allotments').map(sourcePolygon);
    if(allotments.length) addMesh('NATURAL_MAPPED_ALLOTMENTS',
      polygonGeometry(THREE,allotments,-.235,15),
      own(new THREE.MeshStandardMaterial({map:grassGround,roughness:1,side:THREE.DoubleSide})));
    const railwayLand=(data.landuse||[]).filter(item=>item.kind==='railway').map(sourcePolygon);
    polygonsForSport('NATURAL_MAPPED_RAILWAY_LAND',railwayLand,-.232,
      {map:asphalt,color:'#96948c',roughness:1,side:THREE.DoubleSide});
    const constructionLand=(data.landuse||[]).filter(item=>item.kind==='construction').map(sourcePolygon);
    polygonsForSport('NATURAL_MAPPED_CONSTRUCTION',constructionLand,-.232,
      {map:asphalt,color:'#a39d90',roughness:1,side:THREE.DoubleSide});
    const parkingFeatures = (data.parking || []).filter(item => item?.parking === 'surface');
    const greenParking = parkingFeatures.filter(item => ['grass','grass_paver'].includes(item.surface))
      .map(sourcePolygon);
    const groundParking = parkingFeatures.filter(item => item.surface === 'ground').map(sourcePolygon);
    const asphaltPolygons = parkingFeatures.filter(item =>
      !['grass','grass_paver','ground'].includes(item.surface)).map(sourcePolygon);
    if (greenParking.length)
      addMesh('NATURAL_OSM_PARKING_GRASS',polygonGeometry(THREE,greenParking,-.24,15),
        own(new THREE.MeshStandardMaterial({map:grass,roughness:1,side:THREE.DoubleSide})));
    if (groundParking.length)
      addMesh('NATURAL_OSM_PARKING_GROUND',polygonGeometry(THREE,groundParking,-.24,15),
        own(new THREE.MeshStandardMaterial({map:grassGround,roughness:1,side:THREE.DoubleSide})));
    if (asphaltPolygons.length)
      addMesh('NATURAL_OSM_PARKING', polygonGeometry(THREE, asphaltPolygons, -.24, 30),
        own(new THREE.MeshStandardMaterial({map: asphalt, roughness: .96, metalness: 0,
          side: THREE.DoubleSide})));
    if (data.roads.length) {
      const positions = [], uvs = [], indices = [];
      for (const road of data.roads) for (let i = 1; i < road.p.length; i++) {
        const [ax, az] = directPoint(road.p[i - 1]), [bx, bz] = directPoint(road.p[i]);
        const length = Math.hypot(bx - ax, bz - az), half = road.w * 1.25;
        if (!length) continue;
        const nx = -(bz - az) / length * half, nz = (bx - ax) / length * half;
        const start = positions.length / 3;
        [[ax + nx, -.28, az + nz], [bx + nx, -.28, bz + nz],
          [bx - nx, -.28, bz - nz], [ax - nx, -.28, az - nz]].forEach(([x,y,z]) => {
          positions.push(x,-.20,z); uvs.push(x / 30,z / 30);
        });
        indices.push(start,start+2,start+1,start,start+3,start+2);
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions,3));
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs,2)); geometry.setIndex(indices);
      geometry.computeVertexNormals();
      addMesh('NATURAL_MAPPED_ROADS', geometry,
        own(new THREE.MeshStandardMaterial({map: asphalt, roughness: .95, side: THREE.DoubleSide})));
    }
    if (data.water.length) addMesh('NATURAL_MAPPED_WATER',
      polygonGeometry(THREE, data.water, -.18, 25),
      own(new THREE.MeshStandardMaterial({color: '#879b9a', roughness: .32, metalness: .02,
        side: THREE.DoubleSide})));
    if (data.buildings.length) {
      const positions = [], uvs = [], indices = [], roofP = [], roofUvs = [], roofI = [];
      data.buildings.forEach((raw, index) => {
        const ring = raw.slice(); if (ring.length > 3 && ring[0][0] === ring.at(-1)[0] &&
          ring[0][1] === ring.at(-1)[1]) ring.pop();
        const pts = ring.map(directPoint), height = data.buildingHeights[index];
        const start = positions.length / 3;
        pts.forEach(([x,z]) => { positions.push(x,-.05,z); uvs.push(x/4,z/4); });
        pts.forEach(([x,z]) => { positions.push(x,height,z); uvs.push(x/4,z/4); });
        const n = pts.length;
        for (let i=0;i<n;i++) { const j=(i+1)%n;
          indices.push(start+i,start+j,start+n+j,start+i,start+n+j,start+n+i);
        }
        const face = pts.map(([x,z]) => new THREE.Vector2(x,z));
        const triangles = THREE.ShapeUtils.triangulateShape(face, []), roofStart=roofP.length/3;
        pts.forEach(([x,z])=>{roofP.push(x,height,z);roofUvs.push(x/30,z/30);});
        triangles.forEach(([a,b,c])=>roofI.push(roofStart+a,roofStart+c,roofStart+b));
      });
      const walls = new THREE.BufferGeometry();
      walls.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
      walls.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2)); walls.setIndex(indices);
      walls.computeVertexNormals();
      addMesh('NATURAL_BUILDING_WALLS',walls,own(new THREE.MeshStandardMaterial({
        color:'#c9c5b7',roughness:.9,side:THREE.DoubleSide})));
      const roofs = new THREE.BufferGeometry();
      roofs.setAttribute('position',new THREE.Float32BufferAttribute(roofP,3));
      roofs.setAttribute('uv',new THREE.Float32BufferAttribute(roofUvs,2));roofs.setIndex(roofI);
      roofs.computeVertexNormals();
      addMesh('NATURAL_BUILDING_ROOFS',roofs,own(new THREE.MeshStandardMaterial({
        map:asphalt,roughness:.9,side:THREE.DoubleSide})));
    }

    // Each actual OSM tree gets an alpha-tested multi-view card at its source
    // coordinate. 32k instance budget is split across source model variants.
    const vegetation = buildMappedVegetationRepresentatives(data);
    const mappedTrees = data.trees.map((source,index) => {
      const [x,z] = directPoint(source);
      const metadata = data.treeMetadata?.[index];
      const h = seededUnit(`mapped-tree:${source[0]}:${source[1]}`);
      return {x,z,metadata,scale:.82+h*.38,variant:Math.floor(h*manifest.trees.length)};
    });
    const forestTrees = vegetation.forest.map(item => ({...item, scale:.88+item.variant*.28,
      variant:Math.floor(item.variant*manifest.trees.length), kind:'forest'}));
    const trees = [...mappedTrees, ...forestTrees];
    const shrubs = vegetation.scrub.map(item => ({...item, scale:.86+item.variant*.28,
      variant:Math.floor(item.variant*manifest.shrubs.length)}));
    const viewIndex = {value: 0};
    const createImpostors = async (items, specs, prefix, firstAtlas = null) => {
      for (let variant = 0; variant < specs.length; variant++) {
        const batch = items.filter(item => item.variant === variant);
        if (!batch.length) continue;
        const spec = specs[variant];
        const image = firstAtlas && variant === 0 ? firstAtlas : await loadTexture(spec.atlas);
        const geometry = own(new THREE.PlaneGeometry(spec.widthMeters, spec.heightMeters));
        const material = own(createImpostorMaterial(THREE, image, viewIndex));
        const depthMaterial = own(createImpostorMaterial(THREE, image, viewIndex, true));
        const instanced = new THREE.InstancedMesh(geometry, material, batch.length);
        instanced.name = `${prefix}_${spec.id}`;
        instanced.castShadow = true; instanced.receiveShadow = true;
        instanced.customDepthMaterial = depthMaterial; instanced.frustumCulled = false;
        const matrix = new THREE.Matrix4(), pos = new THREE.Vector3();
        const quaternion = new THREE.Quaternion(), euler = new THREE.Euler();
        const scale = new THREE.Vector3();
        batch.forEach((item,index) => {
          pos.set(item.x, spec.heightMeters * .5 * item.scale - .22, item.z);
          euler.set(0, Math.atan2(camera?.position?.x - item.x || 0,
            camera?.position?.z - item.z || 1), 0);
          quaternion.setFromEuler(euler); scale.setScalar(item.scale);
          matrix.compose(pos,quaternion,scale); instanced.setMatrixAt(index,matrix);
        });
        instanced.instanceMatrix.needsUpdate=true; group.add(instanced);
      }
    };
    await createImpostors(trees,manifest.trees,'NATURAL_TREE_IMPOSTORS',atlas);
    await createImpostors(shrubs,manifest.shrubs,'NATURAL_SCRUB_IMPOSTORS');

    // Occupied cars require explicit OSM parking polygons; no free-form
    // placements are ever invented. The car loader is local and source-derived.
    const parking = buildParkingPoints(data, vegetation);
    const cars = parking.points;
    let carHandle = null;
    if (cars.length) {
      const {loadInstancedCars} = await import('./natural_car_models.js?v=4');
      carHandle = await loadInstancedCars(THREE, root, cars, manifest.carModel, group);
      if (carHandle?.dispose) own({dispose: carHandle.dispose});
    }
    const updateLOD = activeCamera => {
      if (disposed || !activeCamera?.position) return;
      const view = new THREE.Vector3(activeCamera.position.x - centerX, activeCamera.position.y,
        activeCamera.position.z - centerZ);
      viewIndex.value = octaViewIndex(view);
      for (const child of group.children) {
        if (child.material?.userData?.treeShader)
          child.material.userData.treeShader.uniforms.uTreeView.value = viewIndex.value;
        if (child.customDepthMaterial?.userData?.treeShader)
          child.customDepthMaterial.userData.treeShader.uniforms.uTreeView.value = viewIndex.value;
      }
    };
    updateLOD(camera);
    const metrics = {trees: trees.length, mappedTreeNodes: mappedTrees.length,
      forestRepresentatives: vegetation.forest.length, scrubRepresentatives: vegetation.scrub.length,
      treeModelVariants: manifest.trees.map(item => item.id), shrubModelVariants: manifest.shrubs.map(item => item.id),
      treeMeshInstances: 0, treeImpostorInstances: trees.length, shrubImpostorInstances: shrubs.length,
      carShadowProxyInstances: cars.length, carShadowProxyTriangles: cars.length * 12,
      parkedCars: cars.length, eligibleParkingBays: parking.eligibleBays,
      graphicParkingFillTarget: .7,
      realizedParkingFillFraction: parking.eligibleBays ? cars.length / parking.eligibleBays : 0,
      mappedParkingLots: parking.lots, rejectedNonSurfaceParkingLots: parking.rejectedNonSurfaceLots,
      roads: data.roads.length, buildings: data.buildings.length,
      mappedBoundsMeters:{width:extents.maxX-extents.minX,depth:extents.maxZ-extents.minZ}};
    group.userData.metrics=metrics;
    return {group,dispose,updateLOD,metrics};
  } catch (error) { dispose(); throw error; }
}
