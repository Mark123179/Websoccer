// Preview-only enclosure. These coordinates are NOT exported Unity geometry.
// The last, low segment meets the real right2_13 NoDraw corner at y=16.46.
export const RECONSTRUCTED_FACADE_SPANS = [
  {name: 'MINUS_X', top: 36.6, points: [[-93.35, 64.5], [-93.35, -64.3],
    [-94.4, -85.7], [-90.8, -96.7], [-84, -106.1], [-74.7, -112.9],
    [-63.65, -116.54], [63.65, -116.54]]},
  {name: 'SOURCE_CORNER_LOWER', top: 16.46, points: [[63.65, -116.54],
    [74.7, -112.9], [84, -106.1], [90.8, -96.7], [94.4, -85.7], [94.4, -64.3]]},
];

export function addReconstructedFacade(THREE: any, world: any) {
  const group = new THREE.Group();
  group.name = 'RECONSTRUCTED_NOT_UNITY_BESTAND_FACADE';
  const material = new THREE.MeshStandardMaterial({
    color: '#737e7a', roughness: .9, side: THREE.DoubleSide,
  });
  for (const {name, top, points} of RECONSTRUCTED_FACADE_SPANS) {
    for (let i = 0; i < points.length - 1; i++) {
      const [ax, az] = points[i], [bx, bz] = points[i + 1];
      const length = Math.hypot(bx - ax, bz - az);
      // A thin, solid wall section rather than a camera-facing billboard.
      const geometry = new THREE.BoxGeometry(length, top, .8);
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set((ax + bx) / 2, top / 2, (az + bz) / 2);
      mesh.rotation.y = -Math.atan2(bz - az, bx - ax);
      mesh.name = `RECONSTRUCTED_${name}_${i}`;
      group.add(mesh);
    }
  }
  world.add(group);
  return {
    group,
    dispose() {
      group.traverse((object: any) => object.geometry?.dispose());
      material.dispose();
    },
  };
}