/** Opt-in full-field texture inspection. Never imported by productive entrypoints. */
import * as THREE from './stage/vendor/three.module.js';
import {PITCH} from './stage/pitch_geometry.js?v=1';

export function canonicalGrassUv(x, z) {
  return [(PITCH.length / 2 - x) / PITCH.length, (z + PITCH.width / 2) / PITCH.width];
}

export async function mountGrassSurfaceStudy(stage, textureUrl) {
  const targets = [];
  stage.sceneRoot.traverse(mesh => {
    if (mesh.isMesh && !Array.isArray(mesh.material) && stage.pitchMaterials.has(mesh.material))
      targets.push({mesh, material: mesh.material, uv: mesh.geometry.getAttribute('uv')});
  });
  if (!targets.length) throw new Error('Keine gemeinsame Spielfeldoberfläche für die Studie.');
  const texture = await new THREE.TextureLoader().loadAsync(textureUrl);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.anisotropy = Math.min(8, stage.renderer.capabilities.getMaxAnisotropy());
  const material = new THREE.MeshLambertMaterial({color: 0xffffff, map: texture,
    side: THREE.DoubleSide, emissive: 0x000000});
  for (const {mesh} of targets) {
    const positions = mesh.geometry.getAttribute('position');
    const uv = [];
    for (let i = 0; i < positions.count; i++)
      uv.push(...canonicalGrassUv(positions.getX(i), positions.getZ(i)));
    mesh.geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    mesh.material = material;
  }
  return {targets, material, dispose() {
    for (const {mesh, material: original, uv} of targets) {
      mesh.material = original;
      if (uv) mesh.geometry.setAttribute('uv', uv); else mesh.geometry.deleteAttribute('uv');
    }
    texture.dispose(); material.dispose();
  }};
}
