import * as THREE from './stage/vendor/three.module.js';
import {PITCH} from './stage/pitch_geometry.js';

export const STUDY_FRAME = Object.freeze([1880, 940]);
export const STUDY_CONCEPTS = Object.freeze({
  perspective: Object.freeze({height: 72, distance: 76, tilt: 36, near: 1, far: 6000, fieldWidth: .84, fieldHeight: .48}),
  cutaway: Object.freeze({height: 98, distance: 76, tilt: 44, near: 1, far: 6000, fieldWidth: .90, fieldHeight: .60}),
  // Elversberg keeps the exact middle-study pose and framing.
  'approved-elversberg': Object.freeze({height: 72, distance: 76, tilt: 36, near: 1, far: 6000, fieldWidth: .84, fieldHeight: .48}),
});

export function studyPreset(concept) {
  const base = STUDY_CONCEPTS[concept];
  if (!base) throw new Error('Unbekannte Studienkamera.');
  const [width, height] = STUDY_FRAME;
  const tilt = THREE.MathUtils.degToRad(base.tilt);
  // All fitting uses the shared pitch alone, never a club's roof or stands.
  const nearDepth = base.distance * Math.cos(tilt) + base.height * Math.sin(tilt);
  const farDepth = (base.distance + PITCH.width) * Math.cos(tilt) + base.height * Math.sin(tilt);
  const yNear = -base.height * Math.cos(tilt) + base.distance * Math.sin(tilt);
  const yFar = -base.height * Math.cos(tilt) + (base.distance + PITCH.width) * Math.sin(tilt);
  const focal = Math.min(width * base.fieldWidth * nearDepth / PITCH.length,
    height * base.fieldHeight / (yFar / farDepth - yNear / nearDepth));
  const principalY = height * .93 + focal * yNear / nearDepth;
  return {...base, zoom: focal, frame: [...STUDY_FRAME], principal: [width / 2, principalY]};
}

export function applyStudyCamera(camera, concept, width, height, cameraSide = 1) {
  const preset = studyPreset(concept), scale = width / preset.frame[0];
  const focal = preset.zoom * scale, cx = width / 2;
  const cy = preset.principal[1] * height / preset.frame[1];
  camera.projectionMatrix.makePerspective(-cx / focal * preset.near,
    (width - cx) / focal * preset.near, cy / focal * preset.near,
    -(height - cy) / focal * preset.near, preset.near, preset.far);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  camera.near = preset.near; camera.far = preset.far;
  const side = cameraSide < 0 ? -1 : 1;
  const tilt = THREE.MathUtils.degToRad(preset.tilt), z = side * (PITCH.width / 2 + preset.distance);
  camera.position.set(0, preset.height, z);
  camera.up.set(0, 1, 0);
  camera.lookAt(0, preset.height - Math.sin(tilt), z - side * Math.cos(tilt));
  camera.updateMatrixWorld(true);
  return preset;
}

export function projectStudy(camera, width, height, x, y, z = 0, rotation = 0) {
  const angle = THREE.MathUtils.degToRad(rotation);
  const rotatedX = x * Math.cos(angle) - y * Math.sin(angle);
  const rotatedY = x * Math.sin(angle) + y * Math.cos(angle);
  const point = new THREE.Vector3(-rotatedX, z, rotatedY).project(camera);
  return {x: (point.x + 1) * width / 2, y: (1 - point.y) * height / 2,
    visible: point.z >= -1 && point.z <= 1};
}

// Right-handed rotation and per-axis pitch normalization. No source file edits.
export function dortmundAdapter() {
  const group = new THREE.Group();
  group.rotation.y = Math.PI / 2;
  group.scale.set(68 / (34.080013275146484 * 2), 1, 105 / (52.95001220703125 * 2));
  return group;
}
