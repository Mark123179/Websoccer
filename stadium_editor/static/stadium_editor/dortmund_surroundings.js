// The editor's existing map is the only source for this environment.
// Heights and tree forms are schematic, not a surveyed reconstruction.
export function editorPointToDortmund(point, frame = {}) {
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
  const dx = point[0] - center[0], dy = point[1] - center[1];
  const u = dx * Math.cos(theta) + dy * Math.sin(theta);
  const v = -dx * Math.sin(theta) + dy * Math.cos(theta);
  // Editor +X is goal-to-goal; Unity +Z is goal-to-goal.
  // Preserve handedness: editor +Y (across the pitch) becomes Unity -X.
  return [-v, u];
}

export function buildDortmundSurroundings(THREE, data = {}, frame = {}) {
  const group = new THREE.Group();
  group.name = 'EDITOR_SURROUNDINGS_3D';
  group.userData.source = data.source || '';
  const resources = new Set();
  const own = resource => { resources.add(resource); return resource; };
  const dispose = () => {
    group.removeFromParent();
    resources.forEach(resource => resource.dispose());
    resources.clear();
  };
  const point = p => editorPointToDortmund(p, frame);
  const polygon = raw => {
    if (!Array.isArray(raw)) throw new Error('Eine Umfeldfläche ist ungültig.');
    const points = raw.map(point);
    if (points.length > 1 && points[0].every((n, i) => n === points.at(-1)[i])) points.pop();
    if (points.length < 3) throw new Error('Eine Umfeldfläche benötigt mindestens drei Punkte.');
    return points;
  };
  const material = color => own(new THREE.MeshStandardMaterial({
    color, roughness: 1, metalness: 0, side: THREE.DoubleSide,
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
    let radius = 450;
    const includeBounds = points => {
      for (const [x, z] of points) radius = Math.max(radius, Math.abs(x) + 60, Math.abs(z) + 60);
    };
    for (const raw of data.green || []) {
      const points = polygon(raw);
      includeBounds(points); surface(green, points, -.18);
    }
    for (const raw of data.water || []) {
      const points = polygon(raw);
      includeBounds(points); surface(water, points, -.16);
    }
    for (const road of data.roads || []) {
      if (!Array.isArray(road.p)) throw new Error('Eine Straße im Stadionumfeld ist ungültig.');
      const points = road.p.map(point), width = road.w ?? 1;
      if (!Number.isFinite(width) || width <= 0) throw new Error('Eine Straßenbreite ist ungültig.');
      includeBounds(points);
      const half = width * 1.25;
      for (let i = 1; i < points.length; i++) {
        const [ax, az] = points[i - 1], [bx, bz] = points[i];
        const length = Math.hypot(bx - ax, bz - az);
        if (!length) continue;
        const nx = -(bz - az) / length * half, nz = (bx - ax) / length * half;
        const a = [ax + nx, -.12, az + nz], b = [bx + nx, -.12, bz + nz];
        const c = [bx - nx, -.12, bz - nz], d = [ax - nx, -.12, az - nz];
        triangle(roads, a, b, c); triangle(roads, a, c, d);
      }
      // Small joins close the turns of the simplified road strips.
      for (const [x, z] of points) {
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
      includeBounds(points);
      surface(roofs, points, height);
      for (let i = 0; i < points.length; i++) {
        const [ax, az] = points[i], [bx, bz] = points[(i + 1) % points.length];
        const a = [ax, -.05, az], b = [bx, -.05, bz];
        const c = [bx, height, bz], d = [ax, height, az];
        triangle(walls, a, b, c); triangle(walls, a, c, d);
      }
    });
    const trees = (data.trees || []).map(point);
    includeBounds(trees);
    // No terrain elevation is present in the 2D data: do not invent relief.
    const ground = new THREE.Mesh(own(new THREE.PlaneGeometry(radius * 2, radius * 2)),
      material('#414a43'));
    ground.name = 'ENV_GROUND';
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -.35;
    group.add(ground);
    if (green.length) mesh('ENV_GREEN', green, material('#38583f'));
    if (water.length) mesh('ENV_WATER', water, material('#335e73'));
    if (roads.length) mesh('ENV_ROADS', roads, material('#777b75'));
    if (walls.length) mesh('ENV_BUILDINGS', walls, material('#92958b'));
    if (roofs.length) mesh('ENV_BUILDING_ROOFS', roofs, material('#61695f'));
    if (trees.length) {
      const trunk = new THREE.InstancedMesh(
        own(new THREE.CylinderGeometry(.35, .5, 3, 6)), material('#625949'), trees.length);
      const crown = new THREE.InstancedMesh(
        own(new THREE.IcosahedronGeometry(3, 0)), material('#4e714d'), trees.length);
      const matrix = new THREE.Matrix4();
      trees.forEach(([x, z], index) => {
        trunk.setMatrixAt(index, matrix.makeTranslation(x, 1.45, z));
        crown.setMatrixAt(index, matrix.makeTranslation(x, 4.8, z));
      });
      trunk.instanceMatrix.needsUpdate = crown.instanceMatrix.needsUpdate = true;
      trunk.computeBoundingSphere(); crown.computeBoundingSphere();
      trunk.name = 'ENV_TREE_TRUNKS'; crown.name = 'ENV_TREE_CROWNS';
      // InstancedMesh owns GPU buffers in addition to geometry/material.
      own(trunk); own(crown);
      group.add(trunk, crown);
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