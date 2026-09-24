// The Unity export has exterior walls on +X / +Z, but leaves the facing
// -X / -Z lower elevations open. These are reconstructed presentation parts,
// not exported Unity meshes or a measured rebuild.
export function addExistingFacade(THREE, world) {
  const group = new THREE.Group();
  group.name = 'RECONSTRUCTED_EXISTING_FACADE';
  const material = (color, roughness = .86) => new THREE.MeshStandardMaterial({
    color, roughness, side: THREE.DoubleSide,
  });
  const wall = material('#707975');
  const trim = material('#939c96');
  const glazing = material('#26383a', .35);
  const mullion = material('#535e5c');
  const materials = [wall, trim, glazing, mullion];
  const quad = (name, a, b, c, d, mat) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c, ...d], 3));
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, mat);
    mesh.name = name;
    group.add(mesh);
  };
  // All perimeter points are at the source's lower concourse footprint.
  // The diagonal transitions close the exposed ends of both missing sides.
  const spans = [
    ['SHORT_MINUS_X', [-93, -70], [-93, 70]],
    ['LONG_MINUS_Z', [-70, -116], [70, -116]],
    ['CORNER_MINUS_X_MINUS_Z', [-93, -70], [-70, -116]],
    ['CORNER_MINUS_X_PLUS_Z', [-93, 70], [-70, 116]],
    ['CORNER_PLUS_X_MINUS_Z', [70, -116], [93, -70]],
  ];
  for (const [name, a, b] of spans) {
    const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const outward = name === 'SHORT_MINUS_X' ? [-1, 0] :
      name === 'LONG_MINUS_Z' ? [0, -1] :
      [Math.sign(a[0] + b[0]) / Math.SQRT2,
        Math.sign(a[1] + b[1]) / Math.SQRT2];
    const point = (at, height, offset = 0) =>
      [a[0] + (b[0] - a[0]) * at + outward[0] * offset,
        height, a[1] + (b[1] - a[1]) * at + outward[1] * offset];
    quad(`RECONSTRUCTED_${name}_WALL`, point(0, 0), point(1, 0),
      point(1, 37), point(0, 37), wall);
    for (const [low, high, mat, label] of [
      [7, 12, glazing, 'GROUND_GLAZING'],
      [23, 28, glazing, 'UPPER_GLAZING'],
      [34, 36, trim, 'CORNICE'],
    ]) {
      quad(`RECONSTRUCTED_${name}_${label}`, point(0, low, .15),
        point(1, low, .15), point(1, high, .15), point(0, high, .15), mat);
    }
    const bays = Math.max(2, Math.round(length / 13));
    for (let i = 0; i <= bays; i++) {
      const at = i / bays;
      const beam = new THREE.Mesh(new THREE.BoxGeometry(.8, 36, .8), mullion);
      beam.position.set(...point(at, 18, .5));
      beam.name = `RECONSTRUCTED_${name}_BAY_${i}`;
      group.add(beam);
    }
  }
  world.add(group);
  return {
    group,
    dispose() {
      group.traverse(object => object.geometry?.dispose());
      materials.forEach(mat => mat.dispose());
    },
  };
}