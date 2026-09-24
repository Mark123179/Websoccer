// These two elevations are missing from the Unity export. The reconstruction
// sits alongside, and is never presented as, the original exported geometry.
export function addExistingFacade(THREE: any, world: any) {
  const group = new THREE.Group();
  group.name = 'RECONSTRUCTED_EXISTING_FACADE';
  const material = (color: string, roughness = .86) => new THREE.MeshStandardMaterial({
    color, roughness, side: THREE.DoubleSide,
  });
  const wall = material('#707975');
  const trim = material('#939c96');
  const glazing = material('#26383a', .35);
  const mullion = material('#535e5c');
  const materials = [wall, trim, glazing, mullion];
  type Foot = [number, number];
  type Point = [number, number, number];
  const quad = (name: string, a: Point, b: Point, c: Point, d: Point, mat: any) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c, ...d], 3));
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, mat);
    mesh.name = name;
    group.add(mesh);
  };
  const spans: Array<[string, Foot, Foot]> = [
    ['SHORT_MINUS_X', [-93, -70], [-93, 70]],
    ['LONG_MINUS_Z', [-70, -116], [70, -116]],
    ['CORNER_MINUS_X_MINUS_Z', [-93, -70], [-70, -116]],
    ['CORNER_MINUS_X_PLUS_Z', [-93, 70], [-70, 116]],
    ['CORNER_PLUS_X_MINUS_Z', [70, -116], [93, -70]],
  ];
  for (const [name, a, b] of spans) {
    const outward: Foot = name === 'SHORT_MINUS_X' ? [-1, 0] :
      name === 'LONG_MINUS_Z' ? [0, -1] :
      [Math.sign(a[0] + b[0]) / Math.SQRT2,
        Math.sign(a[1] + b[1]) / Math.SQRT2];
    const point = (at: number, height: number, offset = 0): Point =>
      [a[0] + (b[0] - a[0]) * at + outward[0] * offset,
        height, a[1] + (b[1] - a[1]) * at + outward[1] * offset];
    quad(`RECONSTRUCTED_${name}_WALL`, point(0, 0), point(1, 0),
      point(1, 37), point(0, 37), wall);
    for (const [low, high, mat, label] of [
      [7, 12, glazing, 'GROUND_GLAZING'],
      [23, 28, glazing, 'UPPER_GLAZING'],
      [34, 36, trim, 'CORNICE'],
    ] as const) {
      quad(`RECONSTRUCTED_${name}_${label}`, point(0, low, .15),
        point(1, low, .15), point(1, high, .15), point(0, high, .15), mat);
    }
    const bays = Math.max(2, Math.round(Math.hypot(b[0] - a[0], b[1] - a[1]) / 13));
    for (let i = 0; i <= bays; i++) {
      const beam = new THREE.Mesh(new THREE.BoxGeometry(.8, 36, .8), mullion);
      beam.position.set(...point(i / bays, 18, .5));
      beam.name = `RECONSTRUCTED_${name}_BAY_${i}`;
      group.add(beam);
    }
  }
  world.add(group);
  return {
    dispose() {
      group.traverse((object: any) => object.geometry?.dispose());
      materials.forEach(mat => mat.dispose());
    },
  };
}