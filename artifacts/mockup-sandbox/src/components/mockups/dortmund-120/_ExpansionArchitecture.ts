type Variant = 'original' | 'rundum' | 'sued';
type Point = [number, number, number];
import { addSeatingRhythm } from './_SeatingRhythm';

const smooth = (min: number, max: number, value: number) => {
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  return t * t * (3 - 2 * t);
};

// Work on concept-only mesh instances; the binary and the Bestand view never change.
const shellNames = new Set([
  'center3_0.001', 'center3_1.001', 'center3_6.001',
  'center3_12.001', 'center3_13.001', 'center3_14.001',
  'center3_21.001', 'center3_25.001', 'center3_26.001', 'center3_29.001',
]);

// Surfaces/layers removed by the viewer's roof cutaway. Supporting pylons and
// trusses are intentionally excluded so the structural frame stays legible.
export const roofSurfaceNames = new Set([
  'center3_0.001', 'center3_1.001', 'center3_12.001',
  'center3_13.001', 'center3_14.001', 'center3_25.001',
  'center3_26.001', 'center3_29.001', 'center3_30.001',
  'center3_17.001',
]);

export function addExpansionArchitecture(THREE: any, world: any, variant: Variant) {
  if (variant === 'original') return null;
  const group = new THREE.Group();
  group.name = variant === 'rundum' ? 'CONCEPT_FOUR_SIDED_ENVELOPE' : 'CONCEPT_PLUS_X_ENVELOPE';

  const sourceMaterial = (name: string) => {
    const original = world.children.find((object: any) => object.name === `ORIGINAL_${name}`);
    const material = original?.material;
    if (!material) throw new Error(`Originalbauteil ${name} fehlt; Ausbau kann nicht dargestellt werden.`);
    return (Array.isArray(material) ? material[0] : material).clone();
  };
  // Original geometry keeps its source material/UVs. Every newly constructed
  // surface is neutral grey, distinct from Dortmund's original yellow parts.
  const concrete = sourceMaterial('back1_6.001');
  const seating = new THREE.MeshStandardMaterial({ color: '#858d8b', roughness: .9, side: THREE.DoubleSide });
  const roofEdge = new THREE.MeshStandardMaterial({ color: '#697574', roughness: .72, metalness: .12, side: THREE.DoubleSide });
  const metal = new THREE.MeshStandardMaterial({ color: '#74817f', roughness: .65, metalness: .2, side: THREE.DoubleSide });
  const charcoal = new THREE.MeshStandardMaterial({ color: '#36484a', roughness: .7, side: THREE.DoubleSide });
  const glazing = new THREE.MeshStandardMaterial({ color: '#496167', roughness: .32, metalness: .25, side: THREE.DoubleSide });
  const materials = [concrete, seating, roofEdge, metal, charcoal, glazing];
  const derivedGeometries: any[] = [];
  const cutawayNames = roofSurfaceNames;

  const quad = (name: string, a: Point, b: Point, c: Point, d: Point, material: any) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c, ...d], 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    geometry.computeVertexNormals();
    const object = new THREE.Mesh(geometry, material);
    object.name = name;
    group.add(object);
  };
  const prism = (name: string, from: Point, to: Point, depth: number, material: any) => {
    const a = new THREE.Vector3(...from), b = new THREE.Vector3(...to);
    const direction = new THREE.Vector3().subVectors(b, a);
    const object = new THREE.Mesh(new THREE.BoxGeometry(depth, direction.length(), depth), material);
    object.position.copy(a).add(b).multiplyScalar(.5);
    object.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
    object.name = name;
    group.add(object);
  };
  const roofStrip = (name: string, a: Point, b: Point, c: Point, d: Point) =>
    quad(name, a, b, c, d, roofEdge);

  // Keep the actual original roof/ceiling/truss/pylon triangles and their UVs.
  // A continuous radial displacement extends them toward the new concourse.
  for (const object of world.children) {
    const name = object.name?.replace(/^ORIGINAL_/, '');
    if (!shellNames.has(name)) continue;
    // Keep the Unity mesh byte-for-byte intact. Only the visible concept gets
    // a private copy of the displaced roof/shell geometry.
    const geometry = object.geometry.clone();
    object.geometry = geometry;
    derivedGeometries.push(geometry);
    const positions = geometry.attributes.position;
    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i), y = positions.getY(i), z = positions.getZ(i);
      const elevation = smooth(4, 31, y);
      if (variant === 'rundum') {
        const wx = smooth(54, 93, Math.abs(x));
        const wz = smooth(77, 117, Math.abs(z));
        positions.setXYZ(i, x + Math.sign(x) * 35 * wx * elevation,
          y + 37 * Math.max(wx, wz) * elevation,
          z + Math.sign(z) * 36 * wz * elevation);
      } else {
        const w = smooth(47, 93, x) * elevation;
        positions.setXYZ(i, x + 75 * w, y + 72 * w, z);
      }
    }
    positions.needsUpdate = true;
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
    // Presentation cutaway: the roof retains its exported triangles, UVs and
    // material map but is drawn translucent so the new tiers can be compared.
    // The source Bestand roof remains opaque in its own instance.
    if (cutawayNames.has(name)) {
      const originalMaterials = Array.isArray(object.material) ? object.material : [object.material];
      const cutaway = originalMaterials.map((original: any) => {
        const copy = original.clone();
        copy.transparent = true;
        copy.opacity = .026;
        copy.depthWrite = false;
        materials.push(copy);
        return copy;
      });
      object.material = Array.isArray(object.material) ? cutaway : cutaway[0];
    }
    object.name = `DERIVED_${name}`;
  }

  // Raked seating starts at the measured upper-edge envelope. It is not a
  // modeled seat count; the concrete below it continues to the ground.
  const terrace = (name: string, innerA: Point, innerB: Point, outerB: Point, outerA: Point) => {
    quad(name, innerA, innerB, outerB, outerA, seating);
    const underA: Point = [innerA[0], innerA[1] - 2.2, innerA[2]];
    const underB: Point = [innerB[0], innerB[1] - 2.2, innerB[2]];
    const underC: Point = [outerB[0], outerB[1] - 2.2, outerB[2]];
    const underD: Point = [outerA[0], outerA[1] - 2.2, outerA[2]];
    quad(`${name}_SOFFIT`, underA, underB, underC, underD, concrete);
  };
  const wall = (name: string, a: Point, b: Point, c: Point, d: Point, axis: 'x' | 'z', out: number) => {
    quad(name, a, b, c, d, concrete);
    const at = (bottom: Point, top: Point, f: number): Point =>
      [bottom[0] + (top[0] - bottom[0]) * f, bottom[1] + (top[1] - bottom[1]) * f, bottom[2] + (top[2] - bottom[2]) * f];
    const offset = (p: Point, amount: number): Point =>
      axis === 'x' ? [p[0] + out * amount, p[1], p[2]] : [p[0], p[1], p[2] + out * amount];
    for (const [low, high, material, label] of [
      [.08, .12, charcoal, 'PLINTH'], [.26, .42, glazing, 'CONCOURSE'],
      [.44, .48, metal, 'BELT'], [.78, .82, charcoal, 'UPPER_BELT'],
    ] as const) {
      quad(`${name}_${label}`, offset(at(a, d, low), .35), offset(at(b, c, low), .35),
        offset(at(b, c, high), .35), offset(at(a, d, high), .35), material);
    }
    for (let i = 0; i <= 10; i++) {
      const t = i / 10;
      const foot: Point = [a[0] + (b[0] - a[0]) * t, a[1], a[2] + (b[2] - a[2]) * t];
      const crown: Point = [d[0] + (c[0] - d[0]) * t, d[1], d[2] + (c[2] - d[2]) * t];
      prism(`${name}_BAY_${i}`, offset(foot, .75), offset(crown, .75), 1.8, concrete);
    }
  };

  if (variant === 'rundum') {
    for (let row = 0; row < 7; row++) {
      const a = row / 7, b = (row + 1) / 7, y0 = 38 + 31 * a, y1 = 38 + 31 * b;
      const xi = 91 + 37 * a, xo = 91 + 37 * b, zi = 115 + 36 * a, zo = 115 + 36 * b;
      terrace(`NEW_PLUS_X_ROW_${row}`, [xi, y0, -zi], [xi, y0, zi], [xo, y1, zo], [xo, y1, -zo]);
      terrace(`NEW_MINUS_X_ROW_${row}`, [-xi, y0, zi], [-xi, y0, -zi], [-xo, y1, -zo], [-xo, y1, zo]);
      terrace(`NEW_PLUS_Z_ROW_${row}`, [-xi, y0, zi], [xi, y0, zi], [xo, y1, zo], [-xo, y1, zo]);
      terrace(`NEW_MINUS_Z_ROW_${row}`, [xi, y0, -zi], [-xi, y0, -zi], [-xo, y1, -zo], [xo, y1, -zo]);
    }
    // Four walls share exact corner coordinates at every level. Their lower
    // edges overlap the existing exterior footprint rather than hovering.
    wall('NEW_PLUS_X_FACADE', [110, 0, -137], [110, 0, 137], [128, 69, 151], [128, 69, -151], 'x', 1);
    wall('NEW_MINUS_X_FACADE', [-110, 0, 137], [-110, 0, -137], [-128, 69, -151], [-128, 69, 151], 'x', -1);
    wall('NEW_PLUS_Z_FACADE', [-110, 0, 137], [110, 0, 137], [128, 69, 151], [-128, 69, 151], 'z', 1);
    wall('NEW_MINUS_Z_FACADE', [110, 0, -137], [-110, 0, -137], [-128, 69, -151], [128, 69, -151], 'z', -1);
    for (const sign of [-1, 1]) {
      quad(`NEW_X_ROOF_JUNCTION_${sign}`, [sign * 128, 69, -151], [sign * 128, 69, 151],
        [sign * 130, 76, 153], [sign * 130, 76, -153], charcoal);
      quad(`NEW_Z_ROOF_JUNCTION_${sign}`, [-128, 69, sign * 151], [128, 69, sign * 151],
        [130, 76, sign * 153], [-130, 76, sign * 153], charcoal);
      roofStrip(`NEW_X_EAVE_${sign}`, [sign * 126, 77, -151], [sign * 126, 77, 151], [sign * 130, 76, 153], [sign * 130, 76, -153]);
      roofStrip(`NEW_Z_EAVE_${sign}`, [-128, 77, sign * 149], [128, 77, sign * 149], [130, 76, sign * 153], [-130, 76, sign * 153]);
    }
    for (const [xSign, zSign] of [[-1, -1], [-1, 1], [1, -1], [1, 1]]) {
      // The two eave runs meet at the same outer corner but have different
      // inner endpoints. This triangular return closes the exposed seam.
      const xInner: Point = [xSign * 126, 77, zSign * 151];
      const zInner: Point = [xSign * 128, 77, zSign * 149];
      const outer: Point = [xSign * 130, 76, zSign * 153];
      quad(`NEW_CORNER_EAVE_${xSign}_${zSign}`, xInner, outer, zInner, zInner, roofEdge);
    }
  } else {
    for (let row = 0; row < 12; row++) {
      const a = row / 12, b = (row + 1) / 12;
      terrace(`NEW_PLUS_X_ROW_${row}`, [91 + 76 * a, 38 + 63 * a, -115],
        [91 + 76 * a, 38 + 63 * a, 115],
        [91 + 76 * b, 38 + 63 * b, 115], [91 + 76 * b, 38 + 63 * b, -115]);
    }
    wall('NEW_PLUS_X_FACADE', [160, 0, -115], [160, 0, 115], [167, 101, 115], [167, 101, -115], 'x', 1);
    for (const sign of [-1, 1]) {
      // Solid exposed end wall: the sloping crest meets the upper rows and
      // the lower corner enters the existing side structure at x≈91.
      quad(`NEW_END_WALL_${sign}`, [91, 0, sign * 115], [160, 0, sign * 115],
        [167, 101, sign * 115], [91, 38, sign * 115], concrete);
      quad(`NEW_END_ROOF_JUNCTION_${sign}`, [91, 38, sign * 115],
        [167, 101, sign * 115], [171, 112, sign * 119],
        [92, 46, sign * 119], charcoal);
      roofStrip(`NEW_SIDE_EAVE_${sign}`, [92, 46, sign * 112],
        [165, 112, sign * 112], [171, 112, sign * 119], [92, 46, sign * 119]);
    }
    quad('NEW_PLUS_X_ROOF_JUNCTION', [167, 101, -115], [167, 101, 115],
      [171, 112, 119], [171, 112, -119], charcoal);
    roofStrip('NEW_PLUS_X_EAVE', [166, 113, -119], [166, 113, 119],
      [171, 112, 119], [171, 112, -119]);
    for (const sign of [-1, 1]) {
      const mainEave: Point = [166, 113, sign * 119];
      const endEave: Point = [165, 112, sign * 112];
      const outer: Point = [171, 112, sign * 119];
      quad(`NEW_CORNER_EAVE_PLUS_X_${sign}`, mainEave, outer, endEave, endEave, roofEdge);
    }
  }

  materials.push(...addSeatingRhythm(THREE, group, variant));
  world.add(group);
  return {
    dispose: () => {
      group.traverse((object: any) => object.geometry?.dispose());
      derivedGeometries.forEach((geometry: any) => geometry.dispose());
      materials.forEach(material => material.dispose());
    },
  };
}