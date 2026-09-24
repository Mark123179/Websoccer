type Variant = 'rundum' | 'sued';
type Seat = { x: number; y: number; z: number; angle: number; dark: boolean };

// Illustrative seat silhouettes, not a measured seating plan or a capacity
// calculation. The original crowd meshes are textured surfaces, not chairs.
export function addSeatingRhythm(THREE: any, group: any, variant: Variant) {
  const dark = new THREE.MeshStandardMaterial({ color: '#242c2e', roughness: .88 });
  const light = new THREE.MeshStandardMaterial({ color: '#aeb6b3', roughness: .84 });
  const aisle = new THREE.MeshStandardMaterial({ color: '#59615e', roughness: .95, side: THREE.DoubleSide });
  const seats: Seat[] = [];
  const count = variant === 'rundum' ? 21 : 30;
  const addSide = (axis: 'x' | 'z', sign: number) => {
    for (let row = 0; row < count; row++) {
      const t = (row + .5) / count;
      const radial = (axis === 'x' ? 91 : 115) + (axis === 'x' ? (variant === 'sued' ? 76 : 37) : 36) * t;
      const span = variant === 'sued' ? 115 : (axis === 'x' ? 115 + 36 * t : 91 + 37 * t);
      const y = 38 + (variant === 'sued' ? 63 : 31) * t;
      const angle = axis === 'x' ? sign * Math.PI / 2 : sign === 1 ? 0 : Math.PI;
      // A clear cross-aisle and intermittent radial gaps distinguish sections
      // from a solid yellow carpet. Gaps are diagrammatic, not exit design.
      if (row === Math.floor(count * .53)) continue;
      const pitch = 1.65;
      const columns = Math.floor((span * 2 - 8) / pitch);
      for (let column = 0; column < columns; column++) {
        const along = -span + 4 + (column + .5) * pitch;
        if (Math.abs(along) < 1.65 || Math.abs(Math.abs(along) - 27) < 1.4 ||
            Math.abs(Math.abs(along) - 67) < 1.4) continue;
        const x = axis === 'x' ? sign * radial : along;
        const z = axis === 'z' ? sign * radial : along;
        const darkSeat = (Math.floor((along + span) / pitch) + row * 3) % 17 < 14;
        seats.push({ x, y, z, angle, dark: darkSeat });
      }
    }
  };
  addSide('x', 1);
  if (variant === 'rundum') {
    addSide('x', -1);
    addSide('z', 1);
    addSide('z', -1);
  }

  const cushion = new THREE.BoxGeometry(.84, .12, .46);
  const back = new THREE.BoxGeometry(.84, .6, .10);
  const byShade = [seats.filter(s => s.dark), seats.filter(s => !s.dark)];
  for (const [index, members] of byShade.entries()) {
    const material = index ? light : dark;
    const bottom = new THREE.InstancedMesh(cushion, material, members.length);
    const upright = new THREE.InstancedMesh(back, material, members.length);
    bottom.name = `CONCEPT_SEAT_CUSHIONS_${index}`;
    upright.name = `CONCEPT_SEAT_BACKS_${index}`;
    const dummy = new THREE.Object3D();
    members.forEach((seat, i) => {
      dummy.rotation.set(0, seat.angle, 0);
      dummy.position.set(seat.x, seat.y + .22, seat.z);
      dummy.updateMatrix();
      bottom.setMatrixAt(i, dummy.matrix);
      dummy.position.set(seat.x + Math.sin(seat.angle) * .22,
        seat.y + .56, seat.z + Math.cos(seat.angle) * .22);
      dummy.updateMatrix();
      upright.setMatrixAt(i, dummy.matrix);
    });
    bottom.instanceMatrix.needsUpdate = true;
    upright.instanceMatrix.needsUpdate = true;
    bottom.computeBoundingSphere();
    upright.computeBoundingSphere();
    group.add(bottom, upright);
  }

  const strip = (name: string, a: number[], b: number[], c: number[], d: number[]) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c, ...d], 3));
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, aisle);
    mesh.name = name;
    group.add(mesh);
  };
  const crossing = (axis: 'x' | 'z', sign: number) => {
    const start = (Math.floor(count * .53) / count);
    const end = ((Math.floor(count * .53) + 1) / count);
    const radial = (t: number) => (axis === 'x' ? 91 : 115) + (axis === 'x' ? (variant === 'sued' ? 76 : 37) : 36) * t;
    const span = (t: number) => variant === 'sued' ? 115 : (axis === 'x' ? 115 + 36 * t : 91 + 37 * t);
    const point = (t: number, along: number) => axis === 'x'
      ? [sign * radial(t), 38 + (variant === 'sued' ? 63 : 31) * t + .25, along]
      : [along, 38 + 31 * t + .25, sign * radial(t)];
    strip(`CONCEPT_CROSS_AISLE_${axis}_${sign}`,
      point(start, -span(start)), point(start, span(start)),
      point(end, span(end)), point(end, -span(end)));
  };
  crossing('x', 1);
  if (variant === 'rundum') {
    crossing('x', -1);
    crossing('z', 1);
    crossing('z', -1);
  }
  return [dark, light, aisle];
}