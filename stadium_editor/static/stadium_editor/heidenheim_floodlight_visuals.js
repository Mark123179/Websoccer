import * as THREE from './stage/vendor/three.module.js';

// Reviewed Voith-Arena lamp atlas: the same 144 disc centres as the offline
// fixture sampling. Positions are reconstructed from ORIGINAL indexed faces,
// never from a generic mast layout. No additional functional lights are added.
const MATERIAL = 'terrain_grass_artificial_02_gray_clean_newyork_color 4';
const PANELS = [[14, 15], [100, 101], [228, 229], [280, 281]];
const U = [33, 65, 97, 159, 191, 225].map(n => n / 512);
const V = [279, 321, 363, 407, 449, 493].map(n => n / 512);
const fail = () => { throw new Error('Heidenheim: Lampenflächen nicht durch Quellgeometrie belegt.'); };

function sampleFace(vertices, uv, indices, triangle, u, v) {
  const ids = Array.from(indices.slice(triangle * 3, triangle * 3 + 3));
  if (ids.length !== 3 || ids.some(i => i * 3 + 2 >= vertices.length)) return fail();
  const [a, b, c] = ids.map(i => new THREE.Vector3().fromArray(vertices, i * 3));
  const [ta, tb, tc] = ids.map(i => new THREE.Vector2().fromArray(uv, i * 2));
  const det = (tb.y - tc.y) * (ta.x - tc.x) + (tc.x - tb.x) * (ta.y - tc.y);
  if (!Number.isFinite(det) || Math.abs(det) < 1e-9) return fail();
  const wa = ((tb.y - tc.y) * (u - tc.x) + (tc.x - tb.x) * (v - tc.y)) / det;
  const wb = ((tc.y - ta.y) * (u - tc.x) + (ta.x - tc.x) * (v - tc.y)) / det;
  const wc = 1 - wa - wb;
  if (Math.min(wa, wb, wc) < -1e-5) return null;
  const position = a.clone().multiplyScalar(wa).addScaledVector(b, wb).addScaledVector(c, wc);
  const normal = b.sub(a).cross(c.sub(a)).normalize();
  const hit = position.clone().addScaledVector(normal, -position.y / normal.y);
  if (!position.toArray().every(Number.isFinite) || position.y < 18 || normal.y >= -.05 ||
      Math.abs(hit.x) > 40 || Math.abs(hit.z) > 60) return fail();
  return {position, normal, triangle, uv: [u, v]};
}

export function heidenheimEmitterPlan(manifest, buffer) {
  if (manifest.clubFmiId !== 880295) return null;
  const mesh = manifest.meshes.find(m => m.name === 'center2_9');
  const parts = mesh?.parts.filter(p => p.material === MATERIAL) || [];
  if (!mesh || parts.length !== 1 || !parts[0].texture) return fail();
  const part = parts[0];
  const vertices = new Float32Array(buffer, mesh.positionOffset, mesh.vertexCount * 3);
  const uv = new Float32Array(buffer, mesh.uvOffset, mesh.vertexCount * 2);
  const indices = new Uint32Array(buffer, part.indexOffset, part.indexCount);
  const emitters = [];
  PANELS.forEach((triangles, panel) => {
    for (const u of U) for (const v of V) {
      const hit = triangles.map(t => sampleFace(vertices, uv, indices, t, u, v)).find(Boolean);
      if (!hit) return fail();
      emitters.push({...hit, panel});
    }
  });
  // Also cross-check against the selected real, declared runtime lamps.
  if (manifest.verifiedFixtureCount !== 144 || manifest.fixtures.length !== 12 ||
      manifest.fixtures.some(f => f.sourceGeometry?.mesh !== mesh.name ||
        f.sourceGeometry?.material !== MATERIAL ||
        !emitters.some(e => e.triangle === f.sourceGeometry.triangle &&
          e.position.distanceTo(new THREE.Vector3(...f.position)) < 1e-4 &&
          e.normal.dot(new THREE.Vector3(...f.direction)) > .99999))) return fail();
  return emitters;
}

const glowVertex = `
  varying vec2 discUv;
  void main() {
    discUv = uv * 2.0 - 1.0;
    gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
  }`;
const glowFragment = `
  uniform float strength;
  varying vec2 discUv;
  void main() {
    float r = length(discUv);
    float core = 1.0 - smoothstep(0.20, 0.35, r);
    float halo = exp(-r * r * 5.2) * (1.0 - smoothstep(0.7, 1.0, r));
    float alpha = strength * (core * 0.96 + halo * 0.34);
    gl_FragColor = vec4(0.92, 0.96, 1.0, alpha);
  }`;
const beamVertex = `
  varying vec3 viewPosition;
  varying vec3 viewNormal;
  varying float progress;
  varying float heightAboveGround;
  uniform float lengthMeters;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vec4 view = viewMatrix * world;
    viewPosition = view.xyz;
    viewNormal = normalize(normalMatrix * normal);
    progress = -position.y / lengthMeters;
    heightAboveGround = world.y;
    gl_Position = projectionMatrix * view;
  }`;
const beamFragment = `
  uniform float strength;
  varying vec3 viewPosition;
  varying vec3 viewNormal;
  varying float progress;
  varying float heightAboveGround;
  void main() {
    float facing = abs(dot(normalize(viewNormal), normalize(-viewPosition)));
    float edge = pow(facing, 1.6);
    float along = smoothstep(0.0, 0.04, progress) * pow(max(0.0, 1.0 - progress), 1.4);
    float groundFade = smoothstep(0.0, 4.0, heightAboveGround);
    gl_FragColor = vec4(0.85, 0.92, 1.0, strength * edge * along * groundFade);
  }`;

export function mountHeidenheimFloodlightVisuals(scene, manifest, buffer) {
  const emitters = heidenheimEmitterPlan(manifest, buffer);
  if (!emitters) return {update() {}, dispose() {}};
  const group = new THREE.Group();
  group.name = 'SOURCE_FLOODLIGHT_VISUALS';
  group.visible = false;
  group.userData = {emitters: emitters.length, panels: PANELS.length,
    beams: manifest.fixtures.length, additionalLightSources: 0, source: 'reviewed-source-uv'};
  const options = {transparent: true, depthWrite: false, depthTest: true,
    blending: THREE.AdditiveBlending, toneMapped: false, fog: false};
  const glowMaterial = new THREE.ShaderMaterial({...options,
    vertexShader: glowVertex, fragmentShader: glowFragment, uniforms: {strength: {value: 1}}});
  const glowGeometry = new THREE.PlaneGeometry(1.5, 1.5);
  const lamps = new THREE.InstancedMesh(glowGeometry, glowMaterial, emitters.length);
  lamps.name = 'SOURCE_LAMP_DISC_GLOW';
  const transform = new THREE.Object3D(), front = new THREE.Vector3(0, 0, 1);
  emitters.forEach((emitter, i) => {
    transform.position.copy(emitter.position).addScaledVector(emitter.normal, .025);
    transform.quaternion.setFromUnitVectors(front, emitter.normal);
    transform.updateMatrix();
    lamps.setMatrixAt(i, transform.matrix);
  });
  lamps.instanceMatrix.needsUpdate = true;
  lamps.computeBoundingSphere();
  group.add(lamps);
  const beams = manifest.fixtures.map(fixture => {
    const direction = new THREE.Vector3(...fixture.direction).normalize();
    const length = -fixture.position[1] / direction.y;
    // This is an artistic air-scattering core, NOT a change to the real
    // SpotLight's angle, intensity or reach. End it at ground and feather it.
    const geometry = new THREE.CylinderGeometry(.22, length * .12, length, 24, 12, true);
    geometry.translate(0, -length / 2, 0);
    const material = new THREE.ShaderMaterial({...options, side: THREE.DoubleSide,
      vertexShader: beamVertex, fragmentShader: beamFragment,
      uniforms: {strength: {value: .065}, lengthMeters: {value: length}}});
    const beam = new THREE.Mesh(geometry, material);
    beam.name = `SOURCE_LIGHT_CONE_${fixture.id}`;
    beam.position.fromArray(fixture.position).addScaledVector(direction, .03);
    beam.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), direction);
    group.add(beam);
    return beam;
  });
  scene.add(group);
  let disposed = false;
  return {
    update({enabled, day}) {
      if (disposed) return;
      group.visible = enabled;
      glowMaterial.uniforms.strength.value = day ? .65 : 1;
      for (const beam of beams) beam.material.uniforms.strength.value = day ? .01 : .065;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      group.removeFromParent();
      glowGeometry.dispose(); glowMaterial.dispose();
      for (const beam of beams) {beam.geometry.dispose(); beam.material.dispose();}
    },
  };
}
