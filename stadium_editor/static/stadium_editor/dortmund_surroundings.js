// The editor's existing map is the only source for this environment.
// Heights and tree forms are schematic, not a surveyed reconstruction.
// Optional mapping of the editor's north end and west side to the source-model axes.
// The default reproduces the existing transformation exactly.
import {validateSurroundingsGround, pointInGroundCutout,
  groundPolygonRelation} from './surroundings_ground.js?v=1';
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

export function buildDortmundSurroundings(THREE, data = {}, frame = {},
  axes = SURROUNDINGS_AXES_DEFAULT) {
  resolveSurroundingsAxes(axes);
  const terrain = validateSurroundingsGround(data);
  const group = new THREE.Group();
  group.name = 'EDITOR_SURROUNDINGS_3D';
  group.userData.source = data.source || '';
  group.userData.treeSource = data.treeSource || '';
  const resources = new Set();
  const own = resource => { resources.add(resource); return resource; };
  const dispose = () => {
    group.removeFromParent();
    resources.forEach(resource => resource.dispose());
    resources.clear();
  };
  const point = p => editorPointToDortmund(p, frame, axes);
  const polygon = raw => {
    if (!Array.isArray(raw)) throw new Error('Eine Umfeldfläche ist ungültig.');
    const points = raw.map(point);
    if (points.length > 1 && points[0].every((n, i) => n === points.at(-1)[i])) points.pop();
    if (points.length < 3) throw new Error('Eine Umfeldfläche benötigt mindestens drei Punkte.');
    return points;
  };
  const material = (color, options = {}) => own(new THREE.MeshBasicMaterial({
    color, side: THREE.DoubleSide, toneMapped: false, ...options,
  }));
  const mesh = (name, vertices, mat) => {
    if (!vertices.length) return;
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
  const surface = (vertices, points, height) => {
    const contour = points.map(([x, z]) => new THREE.Vector2(x, z));
    const faces = THREE.ShapeUtils.triangulateShape(contour, []);
    if (!faces.length) throw new Error('Eine Umfeldfläche lässt sich nicht darstellen.');
    for (const face of faces) {
      // Ground faces upward; materials are double-sided for imported winding.
      const [a, b, c] = face.map(index => [points[index][0], height, points[index][1]]);
      triangle(vertices, a, c, b);
    }
  };
  try {
    const green = [], water = [], roads = [], walls = [], roofs = [];
    const omitted = {green: [], water: []};
    const relation = points => groundPolygonRelation(points, terrain.cutout);
    const rejectOverlap = (points, label) => {
      if (relation(points) !== 'outside')
        throw new Error(`${label} berührt die groundCutout-Aussparung; Quelle prüfen, nichts automatisch löschen.`);
    };
    const omitSurface = (points, layer, index) => {
      const result = relation(points);
      if (result === 'overlap')
        throw new Error(`${layer}[${index}] kreuzt die groundCutout-Aussparung; Quelle prüfen.`);
      if (result === 'inside') { omitted[layer].push(index); return true; }
      return false;
    };
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
      const points = polygon(raw);
      if (omitSurface(points, 'green', index)) continue;
      includeBounds(points); surface(green, points, -.18);
      lineLoop(greenContours, points, -.145);
    }
    for (const [index, raw] of (data.water || []).entries()) {
      const points = polygon(raw);
      if (omitSurface(points, 'water', index)) continue;
      includeBounds(points); surface(water, points, -.16);
      lineLoop(waterContours, points, -.135);
    }
    for (const [roadIndex, road] of (data.roads || []).entries()) {
      if (!Array.isArray(road.p)) throw new Error('Eine Straße im Stadionumfeld ist ungültig.');
      const points = road.p.map(point), width = road.w ?? 1;
      if (!Number.isFinite(width) || width <= 0) throw new Error('Eine Straßenbreite ist ungültig.');
      includeBounds(points);
      for (let i = 1; i < points.length; i++) {
        const [ax, az] = points[i - 1], [bx, bz] = points[i];
        roadContours.push(ax, -.105, az, bx, -.105, bz);
      }
      const half = width * 1.25;
      for (let i = 1; i < points.length; i++) {
        const [ax, az] = points[i - 1], [bx, bz] = points[i];
        const length = Math.hypot(bx - ax, bz - az);
        if (!length) continue;
        const nx = -(bz - az) / length * half, nz = (bx - ax) / length * half;
        const a = [ax + nx, -.12, az + nz], b = [bx + nx, -.12, bz + nz];
        const c = [bx - nx, -.12, bz - nz], d = [ax - nx, -.12, az - nz];
        rejectOverlap([a, b, c, d].map(p => [p[0], p[2]]), `roads[${roadIndex}]`);
        triangle(roads, a, b, c); triangle(roads, a, c, d);
      }
      // Small joins close the turns of the simplified road strips.
      for (const [x, z] of points) {
        rejectOverlap(Array.from({length: 8}, (_, i) => [
          x + Math.cos(i * Math.PI / 4) * half,
          z + Math.sin(i * Math.PI / 4) * half,
        ]), `roads[${roadIndex}]`);
        for (let i = 0; i < 8; i++) {
          const a = i * Math.PI / 4, b = (i + 1) * Math.PI / 4;
          triangle(roads, [x, -.12, z],
            [x + Math.cos(b) * half, -.12, z + Math.sin(b) * half],
            [x + Math.cos(a) * half, -.12, z + Math.sin(a) * half]);
        }
      }
    }
    (data.buildings || []).forEach((raw, index) => {
      const points = polygon(raw), height = data.buildingHeights?.[index] ?? 9;
      if (!Number.isFinite(height) || height <= 0) throw new Error('Eine Gebäudehöhe ist ungültig.');
      rejectOverlap(points, `buildings[${index}]`);
      includeBounds(points);
      lineLoop(buildingContours, points, height + .025);
      surface(roofs, points, height);
      for (let i = 0; i < points.length; i++) {
        const [ax, az] = points[i], [bx, bz] = points[(i + 1) % points.length];
        const a = [ax, -.05, az], b = [bx, -.05, bz];
        const c = [bx, height, bz], d = [ax, height, az];
        triangle(walls, a, b, c); triangle(walls, a, c, d);
      }
    });
    const trees = (data.trees || []).map(point);
    if (terrain.cutout && trees.some(p => pointInGroundCutout(p, terrain.cutout)))
      throw new Error('Ein Baum liegt in der groundCutout-Aussparung; Quelle prüfen.');
    includeBounds(trees);
    // Flat source-declared elevation only: never invent relief from 2D data.
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
    const ground = new THREE.Mesh(groundGeometry,
      material('#03070c'));
    ground.name = 'ENV_GROUND';
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -.35;
    group.add(ground);
    if (Object.hasOwn(data, 'groundLevel')) {
      group.position.y = terrain.level;
      group.userData.terrain = {
        groundLevel: terrain.level, groundCutout: terrain.cutout, omitted,
      };
    }
    if (green.length) mesh('ENV_GREEN', green, material('#09261e'));
    if (water.length) mesh('ENV_WATER', water, material('#071b26'));
    if (roads.length) mesh('ENV_ROADS', roads, material('#061116'));
    if (walls.length) mesh('ENV_BUILDINGS', walls, material('#071312'));
    if (roofs.length) mesh('ENV_BUILDING_ROOFS', roofs, material('#091b1a'));
    const lines = (name, vertices, color, opacity = 1) => {
      if (!vertices.length) return;
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
          new THREE.Vector3(x, 1.02, z),
          new THREE.Quaternion().setFromEuler(new THREE.Euler(0, variation * Math.PI * 2, 0)),
          new THREE.Vector3(.75 + variation * .35, .75 + variation * .45, .75 + variation * .35),
        ));
        crown.setMatrixAt(index, matrix.compose(
          new THREE.Vector3(x, 3.45 + variation * .6, z),
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