import * as THREE from './stage/vendor/three.module.js';

// Opt-in instrumentation for the isolated export only. No replacement geometry,
// light origins, emissive fill or camera changes.
export function createStudyShadowProbe(handle, lighting) {
  if (!lighting.sources.length || lighting.sources.length > 12)
    throw new Error('Schattenprobe benötigt 1–12 deklarierte reale Quellen.');
  lighting.inspectAlignment();
  const renderer = handle.stage.renderer;
  const previous = {enabled: renderer.shadowMap.enabled, type: renderer.shadowMap.type};
  const meshes = [], materials = new Map();
  const roofs = new Set(handle.roofMeshes);
  handle.stage.sceneRoot.traverse(object => {
    if (!object.isMesh) return;
    meshes.push({object, cast: object.castShadow, receive: object.receiveShadow});
    object.castShadow = true;
    object.receiveShadow = true;
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (materials.has(material)) continue;
      materials.set(material, {clip: material.clipShadows, side: material.shadowSide});
      // Respect the open-frame cut, including in the shadow pass. Thin original
      // double-sided roof surfaces must block light from either side.
      material.clipShadows = true;
      material.shadowSide = material.side;
      material.needsUpdate = true;
    }
  });
  const settings = {mapSize: 2048, near: .25, bias: -.00005, normalBias: .02,
    type: 'PCFSoftShadowMap', clipShadows: true};
  lighting.sources.forEach(light => {
    light.shadow.mapSize.set(settings.mapSize, settings.mapSize);
    light.shadow.camera.near = settings.near;
    light.shadow.camera.far = light.distance;
    light.shadow.bias = settings.bias;
    light.shadow.normalBias = settings.normalBias;
  });
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  function setState(enabled, roofCasts = true) {
    renderer.shadowMap.enabled = enabled;
    renderer.shadowMap.needsUpdate = true;
    lighting.sources.forEach(light => { light.castShadow = enabled; });
    meshes.forEach(({object}) => {
      object.castShadow = !roofs.has(object) || roofCasts;
    });
  }
  function inspect() {
    return {...settings, enabled: renderer.shadowMap.enabled,
      sources: lighting.sources.map(light => ({id: light.userData.sourceId,
        casts: light.castShadow, far: light.shadow.camera.far,
        mapRendered: !!light.shadow.map})),
      visibleRoofCasters: handle.roofMeshes.filter(mesh => mesh.visible && mesh.castShadow).length,
      visibleCasters: meshes.filter(({object}) => object.visible && object.castShadow).length,
      roofInventory: handle.roofMeshes.map(mesh => ({
        name: mesh.name, meshPathId: mesh.userData.sourcePathId, visible: mesh.visible,
        casts: mesh.castShadow,
      }))};
  }
  setState(false);
  return {setState, inspect, dispose() {
    renderer.shadowMap.enabled = previous.enabled;
    renderer.shadowMap.type = previous.type;
    meshes.forEach(({object, cast, receive}) => {
      object.castShadow = cast; object.receiveShadow = receive;
    });
    materials.forEach((old, material) => {
      material.clipShadows = old.clip; material.shadowSide = old.side;
      material.needsUpdate = true;
    });
    lighting.sources.forEach(light => { light.castShadow = false; light.shadow.dispose(); });
  }};
}
