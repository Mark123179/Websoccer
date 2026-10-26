/** Test-only rendered oracle. Never imported by an application entrypoint. */
import * as THREE from './stage/vendor/three.module.js';
import {mountGrassSurfaceStudy} from './grass_surface_study.js';
import {applyGrassStudyCamera, GRASS_STUDY_CAMERA} from './grass_study_camera.js';

// All patches have midtones: saturated RGB primaries cannot detect sRGB errors.
const COLORS = [
  '#b45836', '#487ca4', '#8c609c', '#749442',
  '#bc8050', '#548c78', '#a45c78', '#6874b0',
  '#94844c', '#5c98a0', '#ac7044', '#7c6090',
  '#608c50', '#a45464', '#5078a0', '#b49c60',
];

export function diagnosticTextureUrl() {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 512;
  const ctx = canvas.getContext('2d');
  COLORS.forEach((color, index) => {
    ctx.fillStyle = color;
    ctx.fillRect((index % 4) * 128, Math.floor(index / 4) * 128, 128, 128);
  });
  return canvas.toDataURL('image/png');
}

// Independent world-space oracle: do NOT derive these from canonicalGrassUv
// or the mesh's UV buffer. Image TOP is +worldZ with TextureLoader.flipY=true.
export const GRASS_REFERENCES = Object.freeze([
  [39.375, 25.5, '#b45836'], [13.125, 25.5, '#487ca4'],
  [-13.125, 25.5, '#8c609c'], [-39.375, 25.5, '#749442'],
  [39.375, 8.5, '#bc8050'], [13.125, 8.5, '#548c78'],
  [-13.125, 8.5, '#a45c78'], [-39.375, 8.5, '#6874b0'],
  [39.375, -8.5, '#94844c'], [13.125, -8.5, '#5c98a0'],
  [-13.125, -8.5, '#ac7044'], [-39.375, -8.5, '#7c6090'],
  [39.375, -25.5, '#608c50'], [13.125, -25.5, '#a45464'],
  [-13.125, -25.5, '#5078a0'], [-39.375, -25.5, '#b49c60'],
  // Same patch, opposite sides of a real 10-stripe boundary (worldX=21m).
  [21.8, 6, '#548c78'], [20.2, 6, '#548c78'],
]);

export function inspectGrassSamples(samples, tolerance = 5) {
  if (samples.length !== GRASS_REFERENCES.length)
    throw new Error('Unvollständige Rasen-Referenzpunkte.');
  const failures = [];
  samples.forEach((sample, index) => {
    const [x, z, color] = GRASS_REFERENCES[index];
    const expected = color.slice(1).match(/../g).map(hex => parseInt(hex, 16));
    if (!sample.visible || sample.rgb.length !== 3 ||
        sample.rgb.some((value, channel) => !Number.isFinite(value) ||
          Math.abs(value - expected[channel]) > tolerance))
      failures.push({index, world: [x, z], expected, ...sample});
  });
  return {ok: failures.length === 0, failures};
}

export async function renderGrassDiagnostic(handle, fault = 'none') {
  if (!['none', 'flipY', 'mirrorX', 'linearColorSpace'].includes(fault))
    throw new Error(`Unbekannte Diagnosekontrolle: ${fault}`);
  const stage = handle.stage;
  applyGrassStudyCamera(stage);
  // Neutral, deterministic light isolates texture decoding from art direction,
  // ACES/exposure and stadium-dependent shadows. The REAL Lambert map remains.
  stage.sceneRoot.traverse(object => { if (object.isLight) object.intensity = 0; });
  // Lambert's diffuse BRDF divides irradiance by PI: PI gives unit reflectance.
  const light = new THREE.AmbientLight(0xffffff, Math.PI);
  stage.sceneRoot.add(light);
  stage.renderer.toneMapping = THREE.NoToneMapping;
  stage.renderer.outputColorSpace = THREE.SRGBColorSpace;
  stage.renderer.toneMappingExposure = 1;
  stage.renderer.shadowMap.enabled = false;
  const active = await mountGrassSurfaceStudy(stage, diagnosticTextureUrl());
  try {
    const texture = active.material.map;
    if (fault === 'flipY') texture.flipY = !texture.flipY;
    if (fault === 'mirrorX') { texture.repeat.x = -1; texture.offset.x = 1; }
    if (fault === 'linearColorSpace') texture.colorSpace = THREE.LinearSRGBColorSpace;
    texture.needsUpdate = true;
    stage.render();
    const gl = stage.renderer.getContext();
    gl.finish();
    if (gl.isContextLost()) throw new Error('WebGL-Kontext verloren.');
    if (stage.renderer.info.programs?.some(p => p.diagnostics?.runnable === false))
      throw new Error('Diagnose-Shader fehlgeschlagen.');
    const [width, height] = GRASS_STUDY_CAMERA.format;
    const samples = GRASS_REFERENCES.map(([x, z]) => {
      const point = new THREE.Vector3(x, .01, z).project(stage.camera);
      const px = Math.floor((point.x + 1) * width / 2);
      const py = Math.floor((point.y + 1) * height / 2);
      const visible = point.z >= -1 && point.z <= 1 &&
        px > 0 && px < width - 1 && py > 0 && py < height - 1;
      const bytes = new Uint8Array(3 * 3 * 4);
      if (visible) gl.readPixels(px - 1, py - 1, 3, 3, gl.RGBA, gl.UNSIGNED_BYTE, bytes);
      const rgb = [0, 1, 2].map(channel =>
        Array.from({length: 9}, (_, i) => bytes[i * 4 + channel]).sort((a, b) => a - b)[4]);
      return {pixel: [px, height - 1 - py], visible, rgb};
    });
    if (gl.getError() !== gl.NO_ERROR) throw new Error('WebGL-Pixelauslesung fehlgeschlagen.');
    return {
      fault, samples, ...inspectGrassSamples(samples), surfaceMeshes: active.targets.length,
      projection: stage.camera.projectionMatrix.toArray(),
      view: stage.camera.matrixWorldInverse.toArray(),
      image: handle.canvas.toDataURL('image/png'),
    };
  } finally {
    active.dispose();
    stage.sceneRoot.remove(light);
  }
}
