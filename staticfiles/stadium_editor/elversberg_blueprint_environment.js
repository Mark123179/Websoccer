import * as THREE from './stage/vendor/three.module.js';
import './elversberg_canopies.js?v=1';

const {vegetationCanopies} = globalThis.ElversbergBlueprintCanopies;

export const ELVERSBERG_BLUEPRINT_STYLE = 'elversberg-blueprint';

const COLORS = Object.freeze({
  ground: 0x10282b,
  buildingTop: 0x31505a,
  buildingSide: 0x203a43,
  buildingLine: 0x527985,
  road: 0x19363b,
  roadEdge: 0x3e6870,
  green: 0x173b32,
  greenLine: 0x367462,
  canopy: 0x236047,
  canopyCore: 0x347758,
});

const validRing = ring => Array.isArray(ring) && ring.length >= 3 &&
  ring.every(point => Array.isArray(point) && point.length >= 2 &&
    Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1])));

export function isElversbergBlueprint(environment) {
  return environment?.style === ELVERSBERG_BLUEPRINT_STYLE;
}

export function convertElversbergSurroundings(environment, geometry) {
  const frame = typeof environment?.frame === 'string'
    ? environment.frame : environment?.frame?.name;
  if (!isElversbergBlueprint(environment) ||
      !['raw', 'raw-frame', 'editor'].includes(frame)) return environment;
  const center = geometry?.meta?.fieldC || [geometry?._cx || 0, geometry?._cy || 0];
  const theta = Number(geometry?.meta?.axisTheta) || 0;
  const ct = Math.cos(theta), st = Math.sin(theta);
  const point = value => {
    const dx = Number(value[0]) - center[0], dy = Number(value[1]) - center[1];
    return [dx * ct + dy * st, -dx * st + dy * ct];
  };
  return {
    ...environment,
    frame: 'pitch',
    buildings: (environment.buildings || []).map(item => ({
      ...item, poly: validRing(item.poly) ? item.poly.map(point) : item.poly,
    })),
    roads: (environment.roads || []).map(item => ({
      ...item, p: Array.isArray(item.p) ? item.p.map(point) : item.p,
    })),
    green: (environment.green || []).map(ring => validRing(ring) ? ring.map(point) : ring),
    vegetation: (environment.vegetation || []).map(item => ({
      ...item, poly: validRing(item.poly) ? item.poly.map(point) : item.poly,
    })),
  };
}

function ringShape(ring, transform) {
  if (!validRing(ring)) return null;
  const shape = new THREE.Shape();
  ring.forEach((point, index) => {
    const [x, y] = transform(point);
    if (index) shape.lineTo(x, y);
    else shape.moveTo(x, y);
  });
  shape.closePath();
  return shape;
}

function lineGeometry(points, toWorld, y, width) {
  const positions = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const a = points[index], b = points[index + 1];
    const dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy) || 1;
    const ox = -dy / length * width / 2, oy = dx / length * width / 2;
    const corners = [
      [a[0] + ox, a[1] + oy], [b[0] + ox, b[1] + oy],
      [b[0] - ox, b[1] - oy], [a[0] - ox, a[1] - oy],
    ].map(point => toWorld(point, y));
    positions.push(
      corners[0].x, corners[0].y, corners[0].z, corners[1].x, corners[1].y, corners[1].z,
      corners[2].x, corners[2].y, corners[2].z, corners[0].x, corners[0].y, corners[0].z,
      corners[2].x, corners[2].y, corners[2].z, corners[3].x, corners[3].y, corners[3].z,
    );
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  return geometry;
}

export function buildElversbergEnvironment(environment, {rot, toWorld, groundLevel = 0} = {}) {
  const root = new THREE.Group();
  root.name = 'Elversberg shared blueprint surroundings';
  if (!isElversbergBlueprint(environment) || environment.frame !== 'pitch') return root;
  const hasGeometry = ['buildings', 'roads', 'green', 'vegetation'].some(key =>
    Array.isArray(environment[key]) && environment[key].length,
  );
  if (!hasGeometry) return root;
  const transform = point => {
    const result = rot(point);
    return [-result[0], -result[1]];
  };
  const addShape = (ring, material, y, depth = 0) => {
    const shape = ringShape(ring, transform);
    if (!shape) return null;
    const geometry = depth > 0
      ? new THREE.ExtrudeGeometry(shape, {depth, bevelEnabled: false})
      : new THREE.ShapeGeometry(shape);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = y;
    root.add(mesh);
    return mesh;
  };

  const groundMat = new THREE.MeshLambertMaterial({color: COLORS.ground});
  const greenMat = new THREE.MeshLambertMaterial({color: COLORS.green, side: THREE.DoubleSide});
  const roadMat = new THREE.MeshLambertMaterial({color: COLORS.road, side: THREE.DoubleSide});
  const roadEdgeMat = new THREE.MeshLambertMaterial({color: COLORS.roadEdge, side: THREE.DoubleSide});
  const buildingTop = new THREE.MeshLambertMaterial({color: COLORS.buildingTop, side: THREE.DoubleSide});
  const buildingSide = new THREE.MeshLambertMaterial({color: COLORS.buildingSide, side: THREE.DoubleSide});
  const greenEdge = new THREE.MeshLambertMaterial({color: COLORS.greenLine, side: THREE.DoubleSide});
  const roadLines = [];
  const rings = [
    ...(environment.green || []),
    ...(environment.vegetation || []).map(item => item.poly),
    ...(environment.buildings || []).map(item => item.poly),
  ].filter(validRing);
  const points = [
    ...rings.flat(),
    ...(environment.roads || []).flatMap(road => Array.isArray(road.p) ? road.p : []),
  ].filter(point => Array.isArray(point) && Number.isFinite(point[0]) && Number.isFinite(point[1]));
  const box = points.length ? points.reduce((result, point) => ({
    minX: Math.min(result.minX, point[0]), minY: Math.min(result.minY, point[1]),
    maxX: Math.max(result.maxX, point[0]), maxY: Math.max(result.maxY, point[1]),
  }), {minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity}) : {
    minX: -600, minY: -600, maxX: 600, maxY: 600,
  };
  const margin = 90;
  addShape([[box.minX - margin, box.minY - margin], [box.maxX + margin, box.minY - margin],
    [box.maxX + margin, box.maxY + margin], [box.minX - margin, box.maxY + margin]],
  groundMat, groundLevel - .12);

  for (const green of environment.green || []) {
    if (validRing(green)) addShape(green, greenMat, groundLevel + .015);
  }
  for (const road of environment.roads || []) {
    if (!Array.isArray(road.p) || road.p.length < 2) continue;
    const width = Math.max(2.5, Number(road.w) || 5);
    const edge = new THREE.Mesh(lineGeometry(road.p, toWorld, groundLevel + .045, width + .65),
      roadEdgeMat);
    const surface = new THREE.Mesh(lineGeometry(road.p, toWorld, groundLevel + .05, width),
      roadMat);
    edge.userData.environmentId = road.id;
    surface.userData.environmentId = road.id;
    roadLines.push(edge, surface);
  }
  roadLines.forEach(mesh => root.add(mesh));

  for (const building of environment.buildings || []) {
    if (!validRing(building.poly)) continue;
    const height = Math.max(1, Number(building.h) || 6);
    const shape = ringShape(building.poly, transform);
    if (!shape) continue;
    const geometry = new THREE.ExtrudeGeometry(shape, {depth: height, bevelEnabled: false});
    const mesh = new THREE.Mesh(geometry, [buildingTop, buildingSide]);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = groundLevel + .06;
    mesh.userData.environmentId = building.id;
    mesh.userData.osmId = building.osmId;
    mesh.userData.sourceName = building.name;
    mesh.userData.heightMatchIou = building.heightMatchIou;
    mesh.userData.heightStatus = building.heightStatus || 'schematic';
    root.add(mesh);
  }

  const canopyGeometry = new THREE.CylinderGeometry(.42, .8, 2.5, 7, 1);
  const canopyMaterials = [
    new THREE.MeshLambertMaterial({color: COLORS.canopy, side: THREE.DoubleSide}),
    new THREE.MeshLambertMaterial({color: COLORS.canopyCore, side: THREE.DoubleSide}),
  ];
  for (const group of environment.vegetation || []) {
    if (!validRing(group.poly)) continue;
    const height = Number(group.height) || 4;
    const instances = vegetationCanopies(group);
    const batch = new THREE.InstancedMesh(
      canopyGeometry, [canopyMaterials[0], canopyMaterials[1], canopyMaterials[1]], instances.length,
    );
    batch.userData.environmentId = group.id;
    batch.userData.heightStatus = group.heightStatus || 'schematic';
    const matrix = new THREE.Matrix4(), position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    instances.forEach(({point, radius}, index) => {
      const center = toWorld(point, groundLevel + height * .5);
      position.copy(center);
      scale.set(radius, height / 2.5, radius);
      matrix.compose(position, quaternion, scale);
      batch.setMatrixAt(index, matrix);
    });
    batch.instanceMatrix.needsUpdate = true;
    root.add(batch);
    addShape(group.poly, greenEdge, groundLevel + .03);
  }
  root.userData.materials = [groundMat, greenMat, roadMat, roadEdgeMat, buildingTop,
    buildingSide, greenEdge, ...canopyMaterials];
  return root;
}

function trace(context, points) {
  context.beginPath();
  points.forEach((point, index) => index
    ? context.lineTo(point.x, point.y)
    : context.moveTo(point.x, point.y));
  context.closePath();
}

export function drawBlueprintEnvironment2D(context, environment, project, options = {}) {
  if (!isElversbergBlueprint(environment)) return;
  const projectedRing = ring => {
    if (!validRing(ring)) return null;
    const points = ring.map(point => project(point[0], point[1], 0));
    return points.every(Boolean) ? points : null;
  };
  const heightScale = Number(options.heightScale) || 1;
  for (const green of environment.green || []) {
    const points = projectedRing(green);
    if (!points) continue;
    trace(context, points);
    context.fillStyle = '#173b32'; context.fill();
    context.strokeStyle = 'rgba(70,145,119,.48)'; context.lineWidth = 1; context.stroke();
  }
  for (const road of environment.roads || []) {
    if (!Array.isArray(road.p) || road.p.length < 2) continue;
    const points = road.p.map(point => project(point[0], point[1], 0));
    if (points.some(point => !point)) continue;
    context.beginPath();
    points.forEach((point, index) => index
      ? context.lineTo(point.x, point.y) : context.moveTo(point.x, point.y));
    context.lineJoin = 'round'; context.lineCap = 'round';
    context.strokeStyle = '#19363b'; context.lineWidth = Math.max(2, (Number(road.w) || 5) * heightScale);
    context.stroke();
    context.strokeStyle = 'rgba(79,131,138,.46)'; context.lineWidth = Math.max(1, context.lineWidth * .12);
    context.stroke();
  }
  for (const building of environment.buildings || []) {
    if (!validRing(building.poly)) continue;
    const base = building.poly.map(point => project(point[0], point[1], 0));
    const top = building.poly.map(point => project(point[0], point[1],
      Math.max(1, Number(building.h) || 6)));
    if (base.some(point => !point) || top.some(point => !point)) continue;
    for (let index = 0; index < base.length; index += 1) {
      const next = (index + 1) % base.length;
      trace(context, [base[index], base[next], top[next], top[index]]);
      context.fillStyle = index % 2 ? '#203a43' : '#294750'; context.fill();
      context.strokeStyle = 'rgba(92,139,148,.24)'; context.lineWidth = .65; context.stroke();
    }
    trace(context, top); context.fillStyle = '#31505a'; context.fill();
    context.strokeStyle = 'rgba(117,165,171,.55)'; context.lineWidth = .8; context.stroke();
  }
  for (const group of environment.vegetation || []) {
    if (!validRing(group.poly)) continue;
    const groupRing = projectedRing(group.poly);
    if (!groupRing) continue;
    trace(context, groupRing);
    context.fillStyle = 'rgba(23,59,50,.88)'; context.fill();
    context.strokeStyle = 'rgba(70,145,119,.64)'; context.lineWidth = 1; context.stroke();
    for (const canopy of vegetationCanopies(group)) {
      const point = project(canopy.point[0], canopy.point[1], Number(group.height) || 4);
      if (!point) continue;
      const radius = Math.max(1.4, canopy.radius * heightScale);
      context.beginPath(); context.ellipse(point.x, point.y, radius, radius * .72, 0, 0, Math.PI * 2);
      context.fillStyle = '#236047'; context.fill();
      context.strokeStyle = 'rgba(93,174,131,.57)'; context.lineWidth = .7; context.stroke();
      context.beginPath(); context.ellipse(point.x - radius * .12, point.y - radius * .1,
        radius * .47, radius * .35, 0, 0, Math.PI * 2);
      context.fillStyle = '#347758'; context.fill();
    }
  }
}
