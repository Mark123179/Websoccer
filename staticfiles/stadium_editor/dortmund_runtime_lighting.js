import {selectDeclaredSources} from './study_lighting.js';

/** Real source mounting points; calibrated intensity, no synthetic lamps. */
export function createDortmundRuntimeLighting(THREE, scene, model, meshes, data,
  hemisphere, sun) {
  const selected = selectDeclaredSources(data.verifiedFixtures || []);
  if (!selected.length) throw new Error('Belegte BVB-Leuchten fehlen.');
  const group = new THREE.Group();
  group.name = 'DECLARED_DORTMUND_FLOODLIGHTS';
  const evidence = selected.map(fixture => {
    const mesh = meshes.find(m => String(m.userData.sourcePathId) ===
      String(fixture.nearestLampMesh.meshPathId));
    if (!mesh) throw new Error(`BVB-Lampenmesh fehlt: ${fixture.id}`);
    let distance = Infinity;
    const point = new THREE.Vector3(...fixture.position);
    for (const part of mesh.geometry.groups) {
      if (mesh.userData.sourceParts[part.materialIndex]?.material !==
          fixture.nearestLampMesh.material) continue;
      for (let i = part.start; i < part.start + part.count; i++) {
        const vertex = new THREE.Vector3().fromBufferAttribute(
          mesh.geometry.attributes.position, mesh.geometry.index.getX(i));
        distance = Math.min(distance, vertex.distanceTo(point));
      }
    }
    if (distance > 1 || Math.abs(distance - fixture.meshDistance) > .001)
      throw new Error(`BVB-Leuchtenrahmen stimmt nicht: ${fixture.id}`);
    model.updateMatrixWorld(true);
    const target = new THREE.Object3D();
    target.position.copy(model.localToWorld(point.clone().addScaledVector(
      new THREE.Vector3(...fixture.direction), 50)));
    const light = new THREE.SpotLight(new THREE.Color(...fixture.color), 0,
      fixture.range, THREE.MathUtils.degToRad(fixture.angle / 2), .5, 2);
    light.position.copy(model.localToWorld(point));
    light.target = target;
    light.userData.sourceId = fixture.id;
    light.userData.onIntensity = fixture.intensity * 8 *
      Math.min(4, Math.sqrt(fixture.representedIds.length));
    group.add(light, target);
    return {light, id: fixture.id, meshDistance: distance,
      representedIds: fixture.representedIds};
  });
  scene.add(group);
  let day = true, floodlight = false;
  return {
    evidence,
    setState(next = {}) {
      if (typeof next.day === 'boolean') day = next.day;
      if (typeof next.floodlight === 'boolean') floodlight = next.floodlight;
      hemisphere.intensity = day ? 1.35 : .08;
      hemisphere.color.set(day ? 0xe7f1f2 : 0x8499b8);
      sun.intensity = day ? 1.5 : 0;
      evidence.forEach(({light}) => {
        light.intensity = floodlight ? light.userData.onIntensity : 0;
      });
    },
    dispose() { group.removeFromParent(); },
  };
}
