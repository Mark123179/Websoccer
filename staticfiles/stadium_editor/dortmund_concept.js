// Production port of the four-sided envelope in the approved Dortmund concept.
// All additions are illustrative geometry, never seats counted for capacity.
export const SIDES = {SUED: 'PLUS_X', NORD: 'MINUS_X', OST: 'PLUS_Z', WEST: 'MINUS_Z'};
const sideOrder = ['NORD', 'SUED', 'OST', 'WEST'];
export function conceptWeights(blocks, baseline, full) {
  if (full) return Object.fromEntries(sideOrder.map(stand => [stand, 1]));
  const added = Object.fromEntries(sideOrder.map(stand => [stand, 0]));
  for (const block of blocks) {
    if (!(block.stand in added)) continue;
    const initial = baseline.get(block.sourceId);
    const increment = block.simulated
      ? Math.max(0, Number(block.capacity) || 0)
      : Math.max(0, (Number(block.capacity) || 0) - (Number(initial) || 0));
    added[block.stand] += increment;
  }
  // Seven rows are a visual concept scale, not seats-per-row or measured capacity.
  return Object.fromEntries(sideOrder.map(stand =>
    [stand, added[stand] ? Math.max(1 / 7, Math.min(1, added[stand] / 20000)) : 0]));
}
export const ROOF_NAMES = new Set([
  'center3_0.001', 'center3_1.001', 'center3_12.001', 'center3_13.001',
  'center3_14.001', 'center3_25.001', 'center3_26.001', 'center3_29.001',
  'center3_30.001', 'center3_17.001',
]);
export const SHELL_NAMES = new Set([
  'center3_0.001', 'center3_1.001', 'center3_6.001',
  'center3_12.001', 'center3_13.001', 'center3_14.001',
  'center3_21.001', 'center3_25.001', 'center3_26.001', 'center3_29.001',
]);
const smooth = (lo, hi, value) => {
  const t = Math.max(0, Math.min(1, (value - lo) / (hi - lo)));
  return t * t * (3 - 2 * t);
};

export function cornerEavePoints(signX, signZ, xSide, zSide) {
  const xSpan = xSide.spanAt(signZ, xSide.progress);
  const zSpan = zSide.spanAt(signX, zSide.progress);
  return [
    [signX * (xSide.outer - 2), xSide.crown + 8, signZ * xSpan],
    [signX * (xSide.outer + 2), xSide.crown + 7,
      signZ * (xSpan + xSide.overhangAt(signZ))],
    [signX * (zSpan + zSide.overhangAt(signX)), zSide.crown + 7,
      signZ * (zSide.outer + 2)],
    [signX * zSpan, zSide.crown + 8, signZ * (zSide.outer - 2)],
  ];
}

export function warpShell(geometry, source, weights) {
  const position = geometry.attributes.position;
  for (let i = 0; i < position.count; i++) {
    const x = source[i * 3], y = source[i * 3 + 1], z = source[i * 3 + 2];
    const elevation = smooth(4, 31, y);
    const px = smooth(54, 93, x) * weights.SUED;
    const nx = smooth(54, 93, -x) * weights.NORD;
    const pz = smooth(77, 117, z) * weights.OST;
    const nz = smooth(77, 117, -z) * weights.WEST;
    position.setXYZ(i, x + 35 * (px - nx) * elevation,
      y + 37 * Math.max(px, nx, pz, nz) * elevation,
      z + 36 * (pz - nz) * elevation);
  }
  position.needsUpdate = true;
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
}

export function buildConcept(THREE, weights) {
  const group = new THREE.Group();
  group.name = 'CONCEPT_FOUR_SIDED_ENVELOPE';
  const completeRundum = ['NORD', 'SUED', 'OST', 'WEST'].every(stand =>
    Math.round(7 * (Number(weights[stand]) || 0)) === 7);
  const material = hex => new THREE.MeshStandardMaterial({
    color: hex, roughness: .82, metalness: .08, side: THREE.DoubleSide,
  });
  const concrete = material('#858d8b'), seats = material('#858d8b');
  const edge = material('#697574'), metal = material('#74817f');
  const dark = material('#36484a'), glass = material('#496167');
  const blackSeat = material('#242c2e'), lightSeat = material('#aeb6b3');
  const materials = [concrete, seats, edge, metal, dark, glass, blackSeat, lightSeat];
  const quad = (name, a, b, c, d, mat) => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c, ...d], 3));
    geo.setIndex([0, 1, 2, 0, 2, 3]);
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = name;
    group.add(mesh);
    return mesh;
  };
  const beam = (name, a, b) => {
    const start = new THREE.Vector3(...a), end = new THREE.Vector3(...b);
    const direction = end.clone().sub(start);
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1.8, direction.length(), 1.8), concrete);
    mesh.position.copy(start).add(end).multiplyScalar(.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
    mesh.name = name;
    group.add(mesh);
  };
  const seatGeometry = new THREE.BoxGeometry(.84, .12, .46);
  const backGeometry = new THREE.BoxGeometry(.84, .6, .10);
  const seatLists = [[], []];
  const sideGeometry = {};
  for (const [stand, strength] of Object.entries(weights)) {
    if (!strength) continue;
    const xSide = stand === 'SUED' || stand === 'NORD';
    const sign = stand === 'SUED' || stand === 'OST' ? 1 : -1;
    const key = SIDES[stand];
    const count = 7;
    const inner = xSide ? 91 : 115, rise = xSide ? 37 : 36;
    const initialSpan = xSide ? 115 : 91, spanRise = xSide ? 36 : 37;
    const rows = Math.max(1, Math.round(count * strength));
    const progress = rows / count;
    const adjacentProgress = {
      [-1]: Math.round(count * (Number(weights[xSide ? 'WEST' : 'NORD']) || 0)) / count,
      [1]: Math.round(count * (Number(weights[xSide ? 'OST' : 'SUED']) || 0)) / count,
    };
    const spanAt = (alongSign, atProgress) =>
      initialSpan + spanRise * Math.min(atProgress, adjacentProgress[alongSign]);
    const overhangAt = alongSign =>
      adjacentProgress[alongSign] === progress && progress > 0 ? 2 : 0;
    const lowerSpanAt = alongSign => completeRundum
      ? initialSpan + (xSide ? 22 : 19)
      : spanAt(alongSign, 1);
    const point = (radial, y, along) => xSide
      ? [sign * radial, y, along] : [along, y, sign * radial];
    for (let row = 0; row < rows; row++) {
      const a = row / count, b = (row + 1) / count;
      const start = inner + rise * a, end = inner + rise * b;
      const spanAMinus = spanAt(-1, a), spanAPlus = spanAt(1, a);
      const spanBMinus = spanAt(-1, b), spanBPlus = spanAt(1, b);
      const bottom = 38 + 31 * a, top = 38 + 31 * b;
      const name = `NEW_${key}_ROW_${row}`;
      quad(name, point(start, bottom, -spanAMinus), point(start, bottom, spanAPlus),
        point(end, top, spanBPlus), point(end, top, -spanBMinus), seats);
      quad(`${name}_SOFFIT`, point(start, bottom - 2.2, -spanAMinus),
        point(start, bottom - 2.2, spanAPlus), point(end, top - 2.2, spanBPlus),
        point(end, top - 2.2, -spanBMinus), concrete);
    }
    // Fewer preview steps cover fewer of the approved seven rows. The envelope
    // is schematic, not a proportional conversion of seats into metres.
    const t = rows / count, outer = inner + rise * t;
    const spanMinus = spanAt(-1, t), spanPlus = spanAt(1, t);
    const innerFoot = inner + (xSide ? 19 : 22);
    const lowerSpanMinus = lowerSpanAt(-1), lowerSpanPlus = lowerSpanAt(1);
    const crown = 38 + 31 * t;
    const footA = point(innerFoot, 0, -lowerSpanMinus), footB = point(innerFoot, 0, lowerSpanPlus);
    const topA = point(outer, crown, -spanMinus), topB = point(outer, crown, spanPlus);
    sideGeometry[stand] = {
      stand, xSide, sign, inner, rise, initialSpan, spanRise, rows, progress,
      innerFoot, lowerSpanAt, outer, spanAt, overhangAt, crown, point,
    };
    quad(`NEW_${key}_FACADE`, footA, footB, topB, topA, concrete);
    const at = (a, b, fraction, offset = 0) =>
      [a[0] + (b[0] - a[0]) * fraction + (xSide ? sign * offset : 0),
        a[1] + (b[1] - a[1]) * fraction,
        a[2] + (b[2] - a[2]) * fraction + (xSide ? 0 : sign * offset)];
    for (const [lo, hi, mat, label] of [
      [.08, .12, dark, 'PLINTH'], [.26, .42, glass, 'CONCOURSE'],
      [.44, .48, metal, 'BELT'], [.78, .82, dark, 'UPPER_BELT'],
    ]) {
      quad(`NEW_${key}_${label}`, at(footA, topA, lo, .35), at(footB, topB, lo, .35),
        at(footB, topB, hi, .35), at(footA, topA, hi, .35), mat);
    }
    for (let i = 0; i <= 10; i++) {
      const f = i / 10;
      beam(`NEW_${key}_BAY_${i}`,
        at(footA, footB, f, .75), at(topA, topB, f, .75));
    }
    quad(`NEW_${key}_ROOF_JUNCTION`, topA, topB,
      point(outer + 2, crown + 7, spanPlus + overhangAt(1)),
      point(outer + 2, crown + 7, -spanMinus - overhangAt(-1)), dark);
    quad(`NEW_${key}_EAVE`, point(outer - 2, crown + 8, -spanMinus),
      point(outer - 2, crown + 8, spanPlus),
      point(outer + 2, crown + 7, spanPlus + overhangAt(1)),
      point(outer + 2, crown + 7, -spanMinus - overhangAt(-1)), edge);
    // Same neutral, gapped seat rhythm as the approved model.
    const visualRows = Math.round(21 * strength);
    for (let row = 0; row < visualRows; row++) {
      if (row === Math.floor(21 * .53)) continue;
      const progress = (row + .5) / 21;
      const radial = inner + rise * progress;
      const halfMinus = spanAt(-1, progress), halfPlus = spanAt(1, progress);
      const cols = Math.floor((halfMinus + halfPlus - 8) / 1.65);
      for (let col = 0; col < cols; col++) {
        const along = -halfMinus + 4 + (col + .5) * 1.65;
        if (Math.abs(along) < 1.65 || Math.abs(Math.abs(along) - 27) < 1.4 ||
            Math.abs(Math.abs(along) - 67) < 1.4) continue;
        const position = point(radial, 38 + 31 * progress, along);
        const angle = xSide ? sign * Math.PI / 2 : sign === 1 ? 0 : Math.PI;
        seatLists[(col + row * 3) % 17 < 14 ? 0 : 1].push({position, angle});
      }
    }
  }
  const triangle = (name, a, b, c, mat) => quad(name, a, b, c, c, mat);
  const closeSideEnd = (side, endSign) => {
    const {
      stand, inner, initialSpan, innerFoot, outer, progress, spanAt, overhangAt,
      lowerSpanAt, crown, point,
    } = side;
    const key = SIDES[stand];
    const baseFoot = point(inner, 0, endSign * initialSpan);
    const baseTop = point(inner, 38, endSign * initialSpan);
    const endSpan = spanAt(endSign, progress);
    const facadeFoot = point(innerFoot, 0, endSign * lowerSpanAt(endSign));
    const facadeTop = point(outer, crown, endSign * endSpan);
    const roofOut = point(outer + 2, crown + 7, endSign * (endSpan + overhangAt(endSign)));
    const roofAnchor = point(inner + 1, 46, endSign * spanAt(endSign, 1));
    const eaveStart = point(outer - 2, crown + 8, endSign * endSpan);
    quad(`NEW_${key}_END_WALL_${endSign}`, baseFoot, facadeFoot, facadeTop, baseTop, concrete);
    quad(`NEW_${key}_END_ROOF_JUNCTION_${endSign}`, baseTop, facadeTop, roofOut, roofAnchor, dark);
    triangle(`NEW_${key}_END_EAVE_CAP_${endSign}`, facadeTop, eaveStart, roofOut, edge);
  };
  for (const [xStand, xSign] of [['SUED', 1], ['NORD', -1]]) {
    for (const [zStand, zSign] of [['OST', 1], ['WEST', -1]]) {
      const xSide = sideGeometry[xStand], zSide = sideGeometry[zStand];
      if (xSide && zSide) {
        const [xInner, xOuter, zOuter, zInner] =
          cornerEavePoints(xSign, zSign, xSide, zSide);
        quad(`NEW_CORNER_EAVE_${xStand}_${zStand}`, xInner, xOuter, zOuter, zInner, edge);
        if (xSide.progress > zSide.progress) closeSideEnd(xSide, zSign);
        else if (zSide.progress > xSide.progress) closeSideEnd(zSide, xSign);
      } else if (xSide) {
        closeSideEnd(xSide, zSign);
      } else if (zSide) {
        closeSideEnd(zSide, xSign);
      }
    }
  }
  seatLists.forEach((list, index) => {
    if (!list.length) return;
    const cushion = new THREE.InstancedMesh(seatGeometry, index ? lightSeat : blackSeat, list.length);
    const upright = new THREE.InstancedMesh(backGeometry, index ? lightSeat : blackSeat, list.length);
    const dummy = new THREE.Object3D();
    list.forEach(({position, angle}, i) => {
      dummy.rotation.set(0, angle, 0);
      dummy.position.set(position[0], position[1] + .22, position[2]);
      dummy.updateMatrix(); cushion.setMatrixAt(i, dummy.matrix);
      dummy.position.set(position[0] + Math.sin(angle) * .22,
        position[1] + .56, position[2] + Math.cos(angle) * .22);
      dummy.updateMatrix(); upright.setMatrixAt(i, dummy.matrix);
    });
    cushion.instanceMatrix.needsUpdate = upright.instanceMatrix.needsUpdate = true;
    cushion.computeBoundingSphere(); upright.computeBoundingSphere();
    cushion.name = `CONCEPT_SEAT_CUSHIONS_${index}`;
    upright.name = `CONCEPT_SEAT_BACKS_${index}`;
    group.add(cushion, upright);
  });
  return {
    group,
    dispose() {
      group.traverse(object => {
        if (object.geometry && object.geometry !== seatGeometry && object.geometry !== backGeometry)
          object.geometry.dispose();
      });
      seatGeometry.dispose(); backGeometry.dispose();
      materials.forEach(mat => mat.dispose());
    },
  };
}