import * as THREE from './stage/vendor/three.module.js';

export function selectDeclaredSources(fixtures) {
  const groups = new Map();
  for (const fixture of fixtures) {
    if (!fixture.verified || fixture.sourceType !== 0 || !fixture.nearestLampMesh?.meshPathId)
      throw new Error('Unbelegte Lichtquelle in der Studie.');
    const [x,,z] = fixture.position;
    const side = Math.abs(x / 34) > Math.abs(z / 52.5) ? (x > 0 ? 'east' : 'west') :
      (z > 0 ? 'north' : 'south');
    if (!groups.has(side)) groups.set(side, []);
    groups.get(side).push(fixture);
  }
  const result = [];
  for (const side of ['north','east','south','west']) {
    const group = groups.get(side) || [];
    group.sort((a,b) => (side === 'north' || side === 'south' ?
      a.position[0] - b.position[0] : a.position[2] - b.position[2]) || a.id.localeCompare(b.id));
    const picks = group.length <= 3 ? group.map((_, i) => i) :
      [.15,.5,.85].map(t => Math.min(group.length - 1, Math.floor(t * group.length)));
    picks.forEach((index,i) => {
      const from = Math.floor(i * group.length / picks.length);
      const to = Math.floor((i + 1) * group.length / picks.length);
      result.push({...group[index], representedIds: group.slice(from, to).map(f => f.id), side});
    });
  }
  return result;
}

export function createStudyLighting(handle, fixtureData) {
  const root = handle.stage.sceneRoot;
  const ambient = new THREE.HemisphereLight(0xe8eff7, 0x36402e, .75);
  const sun = new THREE.DirectionalLight(0xfff3da, 1.6);
  sun.position.set(-100,150,80);
  root.add(ambient, sun);
  const fixtures = fixtureData?.verifiedFixtures || [];
  const selected = selectDeclaredSources(fixtures);
  const lightGroup = new THREE.Group(), diagnostic = new THREE.Group();
  root.add(lightGroup, diagnostic);
  handle.model.updateMatrixWorld(true);
  const sources = [];
  const markerGeometry=new THREE.SphereGeometry(.35,8,6);
  const markers=new THREE.InstancedMesh(markerGeometry,
    new THREE.MeshBasicMaterial({depthTest:false}),fixtures.length);
  markers.renderOrder=20;diagnostic.add(markers);
  const selectedIds=new Set(selected.map(f=>f.id));
  fixtures.forEach((fixture,index)=>markers.setColorAt(index,
    new THREE.Color(selectedIds.has(fixture.id)?'#ffd056':'#54e2ed')));
  selected.forEach(fixture => {
    const sourcePoint = new THREE.Vector3(...fixture.position);
    const point = handle.model.localToWorld(sourcePoint.clone());
    const localTarget = sourcePoint.clone().addScaledVector(new THREE.Vector3(...fixture.direction), 50);
    const target = new THREE.Object3D();
    target.position.copy(handle.model.localToWorld(localTarget));
    const spot = new THREE.SpotLight(new THREE.Color(...fixture.color), 0,
      fixture.range, THREE.MathUtils.degToRad(fixture.angle / 2), .5, 2);
    spot.position.copy(point); spot.target = target; spot.castShadow = false;
    spot.userData.sourceId = fixture.id;
    // Calibrated browser intensity, bounded grouping, no additional fill sources.
    spot.userData.onIntensity = fixture.intensity * 8 * Math.min(4, Math.sqrt(fixture.representedIds.length));
    spot.userData.fixture = fixture;
    lightGroup.add(spot, target); sources.push(spot);
    const helper = new THREE.SpotLightHelper(spot, '#54e2ed'); diagnostic.add(helper);
  });
  diagnostic.visible = false;
  let night = false, enabled = true;
  function sync() {
    handle.model.updateMatrixWorld(true);
    root.background = new THREE.Color(night ? '#02070c' : '#b9c9d8');
    ambient.intensity = night ? .08 : .75;
    ambient.color.set(night ? '#8499b8' : '#e8eff7');
    sun.intensity = night ? 0 : 1.6;
    sources.forEach(source => {
      const fixture = source.userData.fixture;
      const position = new THREE.Vector3(...fixture.position);
      source.position.copy(handle.model.localToWorld(position.clone()));
      source.target.position.copy(handle.model.localToWorld(position.clone()
        .addScaledVector(new THREE.Vector3(...fixture.direction), 50)));
      source.intensity = enabled ? source.userData.onIntensity : 0;
    });
    fixtures.forEach((fixture,index)=>{
      const point=handle.model.localToWorld(new THREE.Vector3(...fixture.position));
      markers.setMatrixAt(index,new THREE.Matrix4().makeTranslation(point.x,point.y,point.z));
    });
    markers.instanceMatrix.needsUpdate=true;
    handle.stage.renderer.toneMappingExposure = night ? 1.1 : 1;
    diagnostic.children.forEach(object => { if (object.isSpotLightHelper) object.update(); });
  }
  // Audit the actual loaded lamp vertices, not just a repeated light formula.
  // Coordinates in the declaration are in the exported mesh's local frame.
  function inspectAlignment() {
    root.updateMatrixWorld(true);
    handle.model.updateMatrixWorld(true);
    return sources.map(source => {
      const fixture = source.userData.fixture;
      const mesh = handle.allMeshes?.find(mesh =>
        String(mesh.userData.sourcePathId) === String(fixture.nearestLampMesh.meshPathId));
      if (!mesh) throw new Error(`Lampenmesh fehlt für Quelle ${fixture.id}.`);
      const geometry = mesh.geometry, vertices = geometry.attributes.position;
      let localDistance = Infinity, worldDistance = Infinity, matched = false;
      const localPoint = new THREE.Vector3(...fixture.position);
      const worldPoint = source.getWorldPosition(new THREE.Vector3());
      const target = source.target.getWorldPosition(new THREE.Vector3());
      const expected = handle.model.localToWorld(localPoint.clone());
      const expectedTarget = handle.model.localToWorld(localPoint.clone()
        .addScaledVector(new THREE.Vector3(...fixture.direction), 50));
      for (const group of geometry.groups) {
        const material = (Array.isArray(mesh.material) ? mesh.material : [mesh.material])[group.materialIndex];
        if (material?.userData.sourceMaterial !== fixture.nearestLampMesh.material) continue;
        matched = true;
        for (let i = group.start; i < group.start + group.count; i++) {
          const vertex = new THREE.Vector3().fromBufferAttribute(vertices,
            geometry.index ? geometry.index.getX(i) : i);
          localDistance = Math.min(localDistance, vertex.distanceTo(localPoint));
          worldDistance = Math.min(worldDistance, vertex.applyMatrix4(mesh.matrixWorld).distanceTo(worldPoint));
        }
      }
      if (!matched || localDistance > 1 || worldDistance > 1 ||
          Math.abs(localDistance - fixture.meshDistance) > 1e-4 ||
          worldPoint.distanceTo(expected) > 1e-8 || target.distanceTo(expectedTarget) > 1e-8)
        throw new Error(`Leuchten-/Modellausrichtung stimmt nicht für ${fixture.id}.`);
      return {id: fixture.id, meshPathId: fixture.nearestLampMesh.meshPathId,
        material: fixture.nearestLampMesh.material, position: worldPoint.toArray(),
        target: target.toArray(), direction: target.clone().sub(worldPoint).normalize().toArray(),
        localMeshDistance: localDistance, worldMeshDistance: worldDistance,
        representedIds: fixture.representedIds,
        originError: worldPoint.distanceTo(expected), targetError: target.distanceTo(expectedTarget)};
    });
  }
  return {
    sources, selected, verifiedCount: fixtures.length, inspectAlignment,
    setState(nextNight, showDiagnostics, floodlight = true) {
      night = nextNight; enabled = floodlight; diagnostic.visible = showDiagnostics; sync();
    },
    dispose() {
      diagnostic.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); });
      root.remove(lightGroup, diagnostic, ambient, sun);
    },
  };
}
