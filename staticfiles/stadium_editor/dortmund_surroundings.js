// The editor's existing map is the only source for this environment.
// Heights and tree forms are schematic, not a surveyed reconstruction.
// Optional mapping of the editor's north end and west side to the source-model axes.
// The default reproduces the existing transformation exactly.
import {validateSurroundingsGround, createGroundCutoutChecks} from './surroundings_ground.js?v=3';
import {elevationSampler, drapeTriangles, drapeLines} from './measured_ground.js?v=1';
import {validateBuildingParts} from './building_parts.js?v=1';
import {bridgeHeightEvidence, bridgeHeightLabel} from './bridge_height_evidence.js?v=1';
const UNIT = Object.freeze({
  '+x': Object.freeze({index:0, sign:1}), '-x': Object.freeze({index:0, sign:-1}),
  '+z': Object.freeze({index:1, sign:1}), '-z': Object.freeze({index:1, sign:-1}),
});
export const SURROUNDINGS_AXES_DEFAULT = Object.freeze({NORD:'+z', WEST:'-x'});

export function resolveSurroundingsAxes(axes = SURROUNDINGS_AXES_DEFAULT) {
  if (axes === null || typeof axes !== 'object' || Array.isArray(axes) ||
      Object.keys(axes).length !== 2 ||
      !Object.hasOwn(axes, 'NORD') || !Object.hasOwn(axes, 'WEST') ||
      !Object.hasOwn(UNIT, axes.NORD) || !Object.hasOwn(UNIT, axes.WEST) ||
      UNIT[axes.NORD].index === UNIT[axes.WEST].index)
    throw new Error('Die Ortsplan-Achsen des Stadionmodells sind ungültig.');
  return {north: UNIT[axes.NORD], west: UNIT[axes.WEST]};
}

export function editorPointToDortmund(point, frame = {}, axes = SURROUNDINGS_AXES_DEFAULT) {
  if (!Array.isArray(point) || point.length < 2 ||
      !point.slice(0, 2).every(value => typeof value === 'number' && Number.isFinite(value))) {
    throw new Error('Das Stadionumfeld enthält eine ungültige Position.');
  }
  const center = frame.fieldC || [0, 0];
  const theta = frame.axisTheta ?? 0;
  if (!Array.isArray(center) || center.length !== 2 ||
      !center.every(Number.isFinite) || !Number.isFinite(theta)) {
    throw new Error('Der Koordinatenrahmen des Stadionumfelds ist ungültig.');
  }
  const {north, west} = resolveSurroundingsAxes(axes);
  const dx = point[0] - center[0], dy = point[1] - center[1];
  const u = dx * Math.cos(theta) + dy * Math.sin(theta);
  const v = -dx * Math.sin(theta) + dy * Math.cos(theta);
  const result = [0, 0];
  result[north.index] = north.sign * u;
  result[west.index] = west.sign * v;
  return result;
}

// Shared CPU checks: one validated terrain per catalog, no meshes/materials.
// Road footprints are yielded in drawing order, including single-point joins.
export function createSurroundingsChecks(THREE, data = {}, frame = {},
  axes = SURROUNDINGS_AXES_DEFAULT) {
  resolveSurroundingsAxes(axes);
  const terrain = validateSurroundingsGround(data);
  const buildingParts = validateBuildingParts(THREE, data);
  const elevation = elevationSampler(terrain.elevation);
  let checkedRadius = 0;
  const checkCoverage = ([x,z]) => {
    elevation(x,z);
    if (!terrain.elevation) return;
    const radius = Math.max(450,Math.abs(x)+60,Math.abs(z)+60);
    if (radius > checkedRadius) {
      for (const sx of [-radius,radius]) for (const sz of [-radius,radius]) elevation(sx,sz);
      checkedRadius = radius;
    }
  };
  if (terrain.elevation) checkCoverage([0,0]);
  const cutoutChecks = createGroundCutoutChecks(terrain.cutout);
  const point = p => {
    const result = editorPointToDortmund(p, frame, axes);
    checkCoverage(result);
    return result;
  };
  if (terrain.elevation) terrain.cutout.forEach(checkCoverage);
  const polygon = raw => {
    if (!Array.isArray(raw)) throw new Error('Eine Umfeldfläche ist ungültig.');
    const points = raw.map(point);
    if (points.length > 1 && points[0].every((n, i) => n === points.at(-1)[i])) points.pop();
    if (points.length < 3) throw new Error('Eine Umfeldfläche benötigt mindestens drei Punkte.');
    return points;
  };
  const triangulate = points => {
    const contour = points.map(([x, z]) => new THREE.Vector2(x, z));
    const faces = THREE.ShapeUtils.triangulateShape(contour, []);
    if (!faces.length) throw new Error('Eine Umfeldfläche lässt sich nicht darstellen.');
    return faces;
  };
  const rejectOverlap = (points, label) => {
    points.forEach(checkCoverage);
    if (cutoutChecks.polygonRelation(points) !== 'outside')
      throw new Error(`${label} berührt die groundCutout-Aussparung; Quelle prüfen, nichts automatisch löschen.`);
  };
  const surface = (raw, layer, index) => {
    const points = polygon(raw);
    const result = cutoutChecks.polygonRelation(points);
    if (result === 'overlap')
      throw new Error(`${layer}[${index}] kreuzt die groundCutout-Aussparung; Quelle prüfen.`);
    const omitted = result === 'inside';
    return {points, omitted, faces: omitted ? [] : triangulate(points)};
  };
  const building = (raw, height = 9, index = 0) => {
    const points = polygon(raw);
    if (!Number.isFinite(height) || height <= 0) throw new Error('Eine Gebäudehöhe ist ungültig.');
    rejectOverlap(points, `buildings[${index}]`);
    return {points, height, faces: triangulate(points)};
  };
  const road = raw => {
    if (!Array.isArray(raw.p)) throw new Error('Eine Straße im Stadionumfeld ist ungültig.');
    const points = raw.p.map(point), width = raw.w ?? 1;
    if (!Number.isFinite(width) || width <= 0) throw new Error('Eine Straßenbreite ist ungültig.');
    return {points, half: width * 1.25};
  };
  function* roadFootprints({points, half}, index = 0) {
    for (let i = 1; i < points.length; i++) {
      const [ax, az] = points[i - 1], [bx, bz] = points[i];
      const length = Math.hypot(bx - ax, bz - az);
      if (!length) continue;
      const nx = -(bz - az) / length * half, nz = (bx - ax) / length * half;
      const strip = [[ax + nx, az + nz], [bx + nx, bz + nz],
        [bx - nx, bz - nz], [ax - nx, az - nz]];
      rejectOverlap(strip, `roads[${index}]`);
      yield {points: strip};
    }
    for (const [x, z] of points) {
      const join = Array.from({length: 8}, (_, i) => [
        x + Math.cos(i * Math.PI / 4) * half,
        z + Math.sin(i * Math.PI / 4) * half,
      ]);
      rejectOverlap(join, `roads[${index}]`);
      yield {points: join, center: [x, z], closingPoint: [
        x + Math.cos(2 * Math.PI) * half, z + Math.sin(2 * Math.PI) * half,
      ]};
    }
  }
  const checkTree = p => {
    if (cutoutChecks.pointInside(p))
      throw new Error('Ein Baum liegt in der groundCutout-Aussparung; Quelle prüfen.');
    return p;
  };
  const tree = raw => checkTree(point(raw));
  return {terrain, elevation, surface, building, buildingParts, road, roadFootprints, tree, point, checkTree};
}

export function buildDortmundSurroundings(THREE, data = {}, frame = {},
  axes = SURROUNDINGS_AXES_DEFAULT) {
  const checks = createSurroundingsChecks(THREE, data, frame, axes);
  const {terrain, elevation} = checks;
  const group = new THREE.Group();
  group.name = 'EDITOR_SURROUNDINGS_3D';
  group.userData.source = data.source || '';
  group.userData.treeSource = data.treeSource || '';
  const bridges = bridgeHeightEvidence(data);
  if (bridges.length) group.userData.bridgeHeightEvidence = bridges;
  const heightNotice = bridgeHeightLabel(data, bridges);
  if (heightNotice) group.userData.bridgeHeightNotice = heightNotice;
  if (checks.buildingParts.size) {
    group.userData.buildingParts = {
      referenceNHN: data.buildingParts.referenceNHN,
      verticalDatum: data.buildingParts.verticalDatum,
      groups: data.buildingParts.groups.map(g => ({
        osm:g.osm, components:g.parts.length, residualPolygons:g.residualPolygons.length,
        heights:g.parts.map(p=>({lodId:p.lodId,baseNHN:p.baseNHN,roofNHN:p.roofNHN})),
      })),
    };
  }
  const resources = new Set();
  const own = resource => { resources.add(resource); return resource; };
  const dispose = () => {
    group.removeFromParent();
    resources.forEach(resource => resource.dispose());
    resources.clear();
  };
  const material = (color, options = {}) => own(new THREE.MeshBasicMaterial({
    color, side: THREE.DoubleSide, toneMapped: false, ...options,
  }));
  const mesh = (name, vertices, mat, drape = false) => {
    if (!vertices.length) return;
    if (drape && terrain.elevation)
      vertices = drapeTriangles(vertices, terrain.elevation, elevation);
    const geometry = own(new THREE.BufferGeometry());
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
    const object = new THREE.Mesh(geometry, mat);
    object.name = name;
    group.add(object);
    return object;
  };
  const triangle = (vertices, a, b, c) => vertices.push(...a, ...b, ...c);
  const surface = (vertices, points, height, faces) => {
    for (const face of faces) {
      // Ground faces upward; materials are double-sided for imported winding.
      const [a, b, c] = face.map(index => [points[index][0], height, points[index][1]]);
      triangle(vertices, a, c, b);
    }
  };
  try {
    const green = [], water = [], roads = [], walls = [], roofs = [];
    const omitted = {green: [], water: []};
    const greenContours = [], waterContours = [], roadContours = [], buildingContours = [];
    let radius = 450;
    const includeBounds = points => {
      for (const [x, z] of points) radius = Math.max(radius, Math.abs(x) + 60, Math.abs(z) + 60);
    };
    const lineLoop = (target, points, y) => {
      for (let i = 0; i < points.length; i++) {
        const [ax, az] = points[i], [bx, bz] = points[(i + 1) % points.length];
        target.push(ax, y, az, bx, y, bz);
      }
    };
    for (const [index, raw] of (data.green || []).entries()) {
      const {points, faces, omitted: skip} = checks.surface(raw, 'green', index);
      if (skip) { omitted.green.push(index); continue; }
      includeBounds(points); surface(green, points, -.18, faces);
      lineLoop(greenContours, points, -.145);
    }
    for (const [index, raw] of (data.water || []).entries()) {
      const {points, faces, omitted: skip} = checks.surface(raw, 'water', index);
      if (skip) { omitted.water.push(index); continue; }
      includeBounds(points); surface(water, points, -.16, faces);
      lineLoop(waterContours, points, -.135);
    }
    for (const [roadIndex, road] of (data.roads || []).entries()) {
      const prepared = checks.road(road), {points} = prepared;
      includeBounds(points);
      for (let i = 1; i < points.length; i++) {
        const [ax, az] = points[i - 1], [bx, bz] = points[i];
        roadContours.push(ax, -.105, az, bx, -.105, bz);
      }
      for (const footprint of checks.roadFootprints(prepared, roadIndex)) {
        if (!footprint.center) {
          const [a, b, c, d] = footprint.points.map(([x, z]) => [x, -.12, z]);
          triangle(roads, a, b, c); triangle(roads, a, c, d);
        } else {
          // Preserve the original fan's final 2π vertex (including rounding).
          const [x, z] = footprint.center;
          for (let i = 0; i < 8; i++) {
            const a = footprint.points[i], b = footprint.points[i + 1] || footprint.closingPoint;
            triangle(roads, [x, -.12, z],
              [b[0], -.12, b[1]], [a[0], -.12, a[1]]);
          }
        }
      }
    }
    (data.buildings || []).forEach((raw, index) => {
      const entries = checks.buildingParts.get(index) ||
        [{poly:raw,height:data.buildingHeights?.[index] ?? 9}];
      entries.forEach(entry => {
      const {points, height, faces} = checks.building(entry.poly, entry.height, index);
      // A flat envelope roof, not a claim to reproduce surveyed roof topology.
      // All wall bottoms follow terrain. Keep the roof above the entire footprint.
      let base = 0;
      if (terrain.elevation && entry.top === undefined) {
        const footprint = [];
        surface(footprint, points, 0, faces);
        const sampled = drapeTriangles(footprint, terrain.elevation, elevation);
        // Negative elevations must not be clamped to local apron zero.
        base = sampled.length ? sampled.reduce((max,n,i) => i%3===1 ? Math.max(max,n) : max,
          -Infinity) : Math.max(...points.map(p => elevation(...p)));
      }
      const top = entry.top ?? base + height;
      includeBounds(points);
      lineLoop(buildingContours, points, top + .025);
      surface(roofs, points, top, faces);
      for (let i = 0; i < points.length; i++) {
        const [ax, az] = points[i], [bx, bz] = points[(i + 1) % points.length];
        if (entry.base !== undefined) {
          const a=[ax,entry.base,az], b=[bx,entry.base,bz];
          const c=[bx,top,bz], d=[ax,top,az];
          triangle(walls,a,b,c); triangle(walls,a,c,d);
          continue;
        }
        if (terrain.elevation) {
          const bottom = drapeLines([ax,-.35,az,bx,-.35,bz], terrain.elevation, elevation);
          for (let j = 0; j < bottom.length; j += 6) {
            const a = bottom.slice(j,j+3), b = bottom.slice(j+3,j+6);
            const c = [b[0],top,b[2]], d = [a[0],top,a[2]];
            triangle(walls,a,b,c); triangle(walls,a,c,d);
          }
          continue;
        }
        const a = [ax, -.35 + elevation(ax, az), az], b = [bx, -.35 + elevation(bx, bz), bz];
        if (!terrain.elevation) { a[1] = -.05; b[1] = -.05; }
        const c = [bx, top, bz], d = [ax, top, az];
        triangle(walls, a, b, c); triangle(walls, a, c, d);
      }
      });
    });
    const trees = (data.trees || []).map(checks.point);
    trees.forEach(checks.checkTree);
    includeBounds(trees);
    // Legacy stays flat; source-declared grids are draped only when present.
    let groundGeometry;
    if (terrain.cutout) {
      includeBounds(terrain.cutout);
      const shape = new THREE.Shape();
      shape.moveTo(-radius, -radius); shape.lineTo(radius, -radius);
      shape.lineTo(radius, radius); shape.lineTo(-radius, radius); shape.closePath();
      const hole = new THREE.Path();
      terrain.cutout.forEach(([x, z], i) => i ? hole.lineTo(x, -z) : hole.moveTo(x, -z));
      hole.closePath(); shape.holes.push(hole);
      groundGeometry = own(new THREE.ShapeGeometry(shape));
    } else groundGeometry = own(new THREE.PlaneGeometry(radius * 2, radius * 2));
    if (terrain.elevation) {
      const geometry = groundGeometry.index ? groundGeometry.toNonIndexed() : groundGeometry;
      const positions = geometry.getAttribute('position'), vertices = [];
      for (let i = 0; i < positions.count; i++)
        vertices.push(positions.getX(i), -.35, -positions.getY(i));
      if (geometry !== groundGeometry) geometry.dispose();
      mesh('ENV_GROUND', vertices, material('#03070c'), true);
    } else {
      const ground = new THREE.Mesh(groundGeometry, material('#03070c'));
      ground.name = 'ENV_GROUND';
      ground.rotation.x = -Math.PI / 2;
      ground.position.y = -.35;
      group.add(ground);
    }
    if (Object.hasOwn(data, 'groundLevel')) {
      group.position.y = terrain.level;
      group.userData.terrain = {
        groundLevel: terrain.level, groundCutout: terrain.cutout, omitted,
        ...(terrain.elevation ? {elevationSource: terrain.elevation.source} : {}),
      };
    }
    if (green.length) mesh('ENV_GREEN', green, material('#09261e'), true);
    if (water.length) mesh('ENV_WATER', water, material('#071b26'), true);
    if (roads.length) mesh('ENV_ROADS', roads, material('#061116'), true);
    if (walls.length) mesh('ENV_BUILDINGS', walls, material('#071312'));
    if (roofs.length) mesh('ENV_BUILDING_ROOFS', roofs, material('#091b1a'));
    const lines = (name, vertices, color, opacity = 1) => {
      if (!vertices.length) return;
      if (terrain.elevation && !name.includes('BUILDING') && !name.includes('TREE'))
        vertices = drapeLines(vertices, terrain.elevation, elevation);
      const geometry = own(new THREE.BufferGeometry());
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
      geometry.computeBoundingSphere();
      const object = new THREE.LineSegments(geometry, own(new THREE.LineBasicMaterial({
        color, transparent: opacity < 1, opacity, depthWrite: false, toneMapped: false,
      })));
      object.name = name;
      object.renderOrder = 2;
      group.add(object);
    };
    lines('ENV_GREEN_CONTOURS', greenContours, '#146343', .6);
    lines('ENV_WATER_CONTOURS', waterContours, '#14778a', .48);
    lines('ENV_ROAD_CONTOURS', roadContours, '#22e6ff', .25);
    lines('ENV_BUILDING_CONTOURS', buildingContours, '#22e6ff', .4);
    if (trees.length) {
      const trunk = new THREE.InstancedMesh(
        own(new THREE.CylinderGeometry(.24, .34, 2.1, 5)), material('#10513a'), trees.length);
      const crown = new THREE.InstancedMesh(
        own(new THREE.IcosahedronGeometry(3.2, 1)), material('#103a2a'), trees.length);
      const matrix = new THREE.Matrix4();
      trees.forEach(([x, z], index) => {
        const seed = Math.sin(x * 12.9898 + z * 78.233) * 43758.5453;
        const variation = seed - Math.floor(seed);
        trunk.setMatrixAt(index, matrix.compose(
          new THREE.Vector3(x, 1.02 + elevation(x, z), z),
          new THREE.Quaternion().setFromEuler(new THREE.Euler(0, variation * Math.PI * 2, 0)),
          new THREE.Vector3(.75 + variation * .35, .75 + variation * .45, .75 + variation * .35),
        ));
        crown.setMatrixAt(index, matrix.compose(
          new THREE.Vector3(x, 3.45 + variation * .6 + elevation(x, z), z),
          new THREE.Quaternion().setFromEuler(new THREE.Euler(
            variation * .35, variation * Math.PI * 2, variation * .2,
          )),
          new THREE.Vector3(.82 + variation * .38, .78 + variation * .36, .82 + variation * .38),
        ));
      });
      trunk.instanceMatrix.needsUpdate = crown.instanceMatrix.needsUpdate = true;
      trunk.computeBoundingSphere(); crown.computeBoundingSphere();
      trunk.name = 'ENV_TREE_TRUNKS'; crown.name = 'ENV_TREE_CROWNS';
      // InstancedMesh owns GPU buffers in addition to geometry/material.
      own(trunk); own(crown);
      group.add(trunk, crown);
      // Apply the exact instance matrices, including all rotations/scales, so
      // green crown contours follow the volume rather than floating beside it.
      const wire = new THREE.EdgesGeometry(crown.geometry);
      const contourVertices = [];
      try {
        const edges = wire.getAttribute('position'), vertex = new THREE.Vector3();
        trees.forEach((_, index) => {
          crown.getMatrixAt(index, matrix);
          for (let i = 0; i < edges.count; i++) {
            vertex.fromBufferAttribute(edges, i).applyMatrix4(matrix);
            contourVertices.push(vertex.x, vertex.y, vertex.z);
          }
        });
      } finally { wire.dispose(); }
      lines('ENV_TREE_CROWN_CONTOURS', contourVertices, '#30f29c', .48);
    }
    group.userData.counts = {
      green: (data.green || []).length, water: (data.water || []).length,
      roads: (data.roads || []).length, buildings: (data.buildings || []).length,
      trees: trees.length,
    };
    return {group, dispose};
  } catch (error) {
    dispose();
    throw error;
  }
}