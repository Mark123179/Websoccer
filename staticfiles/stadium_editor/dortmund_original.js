import * as THREE from 'three';
import {previewSupportsMaterial, sourceOpaqueColor} from './dortmund_source_materials.js';
import {ORDER, countState, nextStep, warpPositions, addedChairPositions, terraceTriangles}
  from './dortmund_expansion_model.mjs?v=2';

const host = document.getElementById('scene');
const fallback = document.getElementById('fallback');
const metrics = document.getElementById('metrics');
const base = host.dataset.assets;
const scene = new THREE.Scene();
scene.background = new THREE.Color('#162225');
scene.fog = new THREE.Fog('#162225', 440, 760);
const camera = new THREE.PerspectiveCamera(42, 1, 1, 1000);
const world = new THREE.Group();
scene.add(world);
scene.add(new THREE.HemisphereLight(0xe7f1f2, 0x344045, 1.35));
const sun = new THREE.DirectionalLight(0xfff3d4, 1.5);
sun.position.set(-135, 210, 100);
scene.add(sun);
const chairs = new THREE.Group();
world.add(chairs);
const terraces = new THREE.Group();
world.add(terraces);
const sourceMeshes = [];
const steps = {back: 0, right: 0, front: 0, left: 0};
let data = null, fpsText = '';
const target = new THREE.Vector3(0, 24, 0);
let azimuth = 0.58, elevation = 0.62, distance = 375, dragging = false, lastX = 0, lastY = 0;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const paint = (hex, options = {}) => new THREE.MeshStandardMaterial({
  color: hex, roughness: .83, metalness: .08, side: THREE.DoubleSide, ...options,
});
const dark = paint('#293336'), yellow = paint('#e3b42e');
const terraceMaterial = paint('#717b77');

function positionCamera() {
  camera.position.set(
    target.x + distance * Math.sin(azimuth) * Math.cos(elevation),
    target.y + distance * Math.sin(elevation),
    target.z + distance * Math.cos(azimuth) * Math.cos(elevation),
  );
  camera.lookAt(target);
}
function setView(view) {
  const preset = {
    diagonal: [.58, .62, 375],
    rear: [1.55, .37, 375],
    top: [.62, 1.12, 395],
  }[view];
  [azimuth, elevation, distance] = preset;
  positionCamera();
  document.querySelectorAll('[data-view]').forEach(button =>
    button.setAttribute('aria-pressed', String(button.dataset.view === view)));
}
setView('diagonal');

function shade(name) {
  const n = name.toLowerCase();
  if (n.includes('pitch') || n.includes('dtmnd')) return '#31734a';
  if (n.includes('seat')) return '#b3a04c';
  if (n.includes('pllr') || n.includes('iron') || n.includes('trus')) return '#c6ac42';
  if (n.includes('roof') || n.includes('irpl')) return '#a3a9a7';
  if (n.includes('glas')) return '#667d81';
  if (n.includes('sgbd') || n.includes('coat_band')) return '#d9bd49';
  if (n.includes('wall') || n.includes('cncr')) return '#777f7e';
  return '#8a9290';
}

function chairGeometry() {
  const geometry = new THREE.BufferGeometry();
  // The Bleacher asset is in centimetre-scale coordinates. Its 148 original
  // vertices are scaled to an actual seat (~46 cm wide), not replaced by boxes.
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(
    data.chair.vertices.flatMap(vertex => vertex.map(n => n * 90)), 3));
  geometry.setIndex(data.chair.indices);
  geometry.computeVertexNormals();
  return geometry;
}

function updateChairs(rows) {
  for (const previous of [...chairs.children]) {
    chairs.remove(previous);
  }
  // Both instance groups share one geometry.
  if (chairs.userData.geometry) chairs.userData.geometry.dispose();
  chairs.userData.geometry = null;
  const positions = ORDER.flatMap(side => addedChairPositions(data, rows, side));
  if (!positions.length) return;
  const geometry = chairGeometry();
  chairs.userData.geometry = geometry;
  const gold = new THREE.InstancedMesh(geometry, yellow, positions.length);
  const black = new THREE.InstancedMesh(geometry, dark, positions.length);
  const matrix = new THREE.Matrix4(), rotation = new THREE.Quaternion();
  const translation = new THREE.Vector3(), scale = new THREE.Vector3(1, 1, 1);
  let a = 0, b = 0;
  for (const chair of positions) {
    translation.set(...chair.position);
    rotation.setFromAxisAngle(new THREE.Vector3(0, 1, 0), chair.rotation * Math.PI / 180);
    matrix.compose(translation, rotation, scale);
    const isDark = chair.color[0] < .3;
    (isDark ? black : gold).setMatrixAt(isDark ? b++ : a++, matrix);
  }
  gold.count = a; black.count = b;
  gold.instanceMatrix.needsUpdate = black.instanceMatrix.needsUpdate = true;
  chairs.add(gold, black);
}

function updateTerraces(rows) {
  for (const mesh of [...terraces.children]) {
    terraces.remove(mesh);
    mesh.geometry.dispose();
  }
  for (const side of ORDER) {
    if (!rows[side]) continue;
    const vertices = terraceTriangles(data, rows, side);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.computeVertexNormals();
    terraces.add(new THREE.Mesh(geometry, terraceMaterial));
  }
}

function updateMetrics() {
  if (!data) return;
  const count = countState(data, steps);
  const blocked = [];
  document.getElementById('seat-count').textContent =
    `${count.total.toLocaleString('de-DE')} modellierte Sitze · +${count.added.toLocaleString('de-DE')}`;
  for (const side of ORDER) {
    const holder = document.querySelector(`[data-side-count="${side}"]`);
    holder.textContent = `+${(count.rows[side] * data.sides[side].template.length).toLocaleString('de-DE')}`;
    document.querySelector(`[data-side="${side}"][data-action="minus"]`).disabled = !steps[side];
    const plus = document.querySelector(`[data-side="${side}"][data-action="plus"]`);
    const reason = nextStep(data, steps, side).reason;
    plus.disabled = Boolean(reason);
    plus.title = reason ? `Gemessene Grenze: höchstens ${data.sides[side].maxRows} zusätzliche Reihen` : '';
    if (reason) blocked.push(`${holder.parentElement.firstElementChild.textContent}: Grenze erreicht`);
  }
  document.getElementById('limit-note').textContent = blocked.join(' · ');
  metrics.textContent = `Originalmeshes · ${fpsText || '2D verfügbar'}`;
}

function updateScene() {
  if (!data) return;
  const {rows} = countState(data, steps);
  for (const {geometry, original, working} of sourceMeshes) {
    if (Object.values(rows).some(Boolean)) {
      warpPositions(original, data, rows, working);
      geometry.attributes.position.array.set(working);
      geometry.attributes.position.needsUpdate = true;
      geometry.computeVertexNormals();
    } else {
      geometry.attributes.position.array.set(original);
      geometry.attributes.position.needsUpdate = true;
      geometry.computeVertexNormals();
    }
    geometry.computeBoundingSphere();
  }
  if (sourceMeshes.length) {
    updateChairs(rows);
    updateTerraces(rows);
  }
  drawFallback();
  updateMetrics();
}

function drawFallback() {
  if (!data) return;
  const svg = document.getElementById('roof-plan');
  const expanded = Object.values(steps).some(Boolean);
  // SVGElement.hidden is not a reflected property in every browser.
  if (expanded) svg.removeAttribute('hidden');
  else svg.setAttribute('hidden', '');
  document.getElementById('fallback-image').hidden = expanded;
  const offset = side => steps[side] * data.sides[side].rowsPerStep * data.rowDepth;
  const l = -data.sides.front.roofExtent - offset('front');
  const r = data.sides.back.roofExtent + offset('back');
  const b = data.sides.left.roofExtent + offset('left');
  const f = -data.sides.right.roofExtent - offset('right');
  const polygons = {
    back: [[59,-82],[59,82],[r,b],[r,f]],
    right: [[-59,-82],[59,-82],[r,f],[l,f]],
    front: [[-59,82],[-59,-82],[l,f],[l,b]],
    left: [[59,82],[-59,82],[l,b],[r,b]],
  };
  const colors = {back:'#e3b42e',front:'#e3b42e',left:'#e3b42e',right:'#e3b42e'};
  svg.innerHTML = `<rect x="-170" y="-157" width="340" height="314" fill="#1d3031"/>
    ${ORDER.map(side => `<polygon points="${polygons[side].map(([x,z]) => `${x},${z}`).join(' ')}"
      fill="${steps[side] ? colors[side] : '#7b8989'}" stroke="#f5d684" stroke-width=".75"/>`).join('')}
    <rect x="-59" y="-82" width="118" height="164" fill="#355e44"/>
    <rect x="-37" y="-53" width="74" height="106" fill="#398659" stroke="#dfeddf" stroke-width=".8"/>
    <text x="-112" y="0" text-anchor="middle" fill="white" font-size="9">VORN</text>
    <text x="112" y="0" text-anchor="middle" fill="white" font-size="9">HINTEN</text>`;
}

function fallbackWith(message) {
  metrics.textContent = message;
  fallback.hidden = false;
  host.hidden = true;
}

async function main() {
  try {
    const response = await fetch(base + 'expansion-data.json');
    if (!response.ok) throw new Error('Sitz- und Dachmessdaten fehlen');
    data = await response.json();
    if (data.format !== 'dortmund-expansion-v1') throw new Error('Unbekanntes Ausbauformat');
    if (new URLSearchParams(location.search).get('ausbau') === '1') steps.back = 1;
    if (steps.back) document.querySelector('[data-preset="original"]').setAttribute('aria-pressed', 'false');
    updateScene();
  } catch (error) {
    console.error('Original-Miniatur:', error);
    fallbackWith('Ausbaumessdaten konnten nicht geladen werden');
    return;
  }
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'high-performance'});
  } catch {
    fallbackWith('WebGL nicht verfügbar');
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.6));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  host.appendChild(renderer.domElement);
  try {
    const start = performance.now();
    const [metaResponse, binResponse] = await Promise.all([
      fetch(base + 'manifest.json'), fetch(base + 'geometry.bin'),
    ]);
    if (!metaResponse.ok || !binResponse.ok) throw new Error('Asset-Download fehlgeschlagen');
    const manifest = await metaResponse.json();
    if (manifest.format !== 'unity-mesh-binary-v1') throw new Error('Unbekanntes Geometrieformat');
    const binary = await binResponse.arrayBuffer();
    const textureLoader = new THREE.TextureLoader();
    const textures = Object.fromEntries(manifest.textures.map(name => {
      const texture = textureLoader.load(base + name + '.webp');
      texture.colorSpace = THREE.SRGBColorSpace;
      return [name, texture];
    }));
    const materialCache = new Map();
    for (const entry of manifest.meshes) {
      const geometry = new THREE.BufferGeometry();
      const original = new Float32Array(
        new Float32Array(binary, entry.positionOffset, entry.vertexCount * 3));
      geometry.setAttribute('position', new THREE.BufferAttribute(
        new Float32Array(original), 3));
      geometry.setAttribute('uv', new THREE.BufferAttribute(
        new Float32Array(binary, entry.uvOffset, entry.vertexCount * 2), 2));
      let indices = [];
      const materials = [];
      for (const part of entry.parts) {
        if (!previewSupportsMaterial(part)) continue;
        const start = indices.length;
        indices.push(...new Uint32Array(binary, part.indexOffset, part.indexCount));
        geometry.addGroup(start, part.indexCount, materials.length);
        const key = part.texture || part.material;
        if (!materialCache.has(key)) materialCache.set(key, paint(
          part.texture ? '#ffffff' : sourceOpaqueColor(part) || shade(part.material),
          part.texture ? {map: textures[part.texture]} : {},
        ));
        materials.push(materialCache.get(key));
      }
      if (!indices.length) continue;
      geometry.setIndex(indices);
      geometry.computeVertexNormals();
      const model = new THREE.Mesh(geometry, materials);
      model.frustumCulled = true;
      world.add(model);
      // Existing occupied seating stays seated. The outer section edge is the
      // anchor for new terraces; only the adjacent structure is deformed.
      if (!entry.name.startsWith('st081_pitch_') && !entry.name.startsWith('C_')) {
        sourceMeshes.push({geometry, original, working: new Float32Array(original.length)});
      }
    }
    updateScene();
    const elapsed = ((performance.now() - start) / 1000).toFixed(1);
    fpsText = `${manifest.meshes.length} Originalmeshes · ${elapsed} s geladen`;
    updateMetrics();
  } catch (error) {
    console.error('Original-Miniatur:', error);
    fallbackWith('3D-Daten konnten nicht geladen werden');
    renderer.dispose();
    return;
  }
  const resize = () => {
    const width = host.clientWidth, height = host.clientHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    if (camera.aspect < 1 && distance < 375 / camera.aspect) {
      distance = 375 / camera.aspect;
      positionCamera();
    }
  };
  new ResizeObserver(resize).observe(host);
  resize();
  let last = performance.now(), frames = 0, slowWindows = 0, stopped = false;
  function animate(now) {
    if (stopped) return;
    renderer.render(scene, camera);
    frames++;
    if (now - last > 2500) {
      const fps = Math.round(frames * 1000 / (now - last));
      fpsText = `${fps} fps`;
      updateMetrics();
      slowWindows = window.innerWidth < 700 && fps < 8 ? slowWindows + 1 : 0;
      if (slowWindows >= 2) {
        stopped = true;
        fallbackWith('2D-Ansicht · 3D zu langsam');
        renderer.dispose();
        return;
      }
      last = now;
      frames = 0;
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
}
main();

host.addEventListener('pointerdown', e => {
  dragging = true; lastX = e.clientX; lastY = e.clientY;
  host.setPointerCapture(e.pointerId);
});
host.addEventListener('pointerup', () => dragging = false);
host.addEventListener('pointercancel', () => dragging = false);
host.addEventListener('pointermove', e => {
  if (!dragging) return;
  azimuth += (e.clientX - lastX) * .006;
  elevation = clamp(elevation + (e.clientY - lastY) * .004, .15, 1.35);
  lastX = e.clientX; lastY = e.clientY;
  positionCamera();
});
host.addEventListener('wheel', e => {
  e.preventDefault();
  distance = clamp(distance * Math.exp(e.deltaY * .0008), 240, 850);
  positionCamera();
}, {passive: false});
host.addEventListener('dblclick', () => setView('diagonal'));
document.querySelectorAll('[data-view]').forEach(button =>
  button.addEventListener('click', () => setView(button.dataset.view)));
document.querySelectorAll('[data-side][data-action]').forEach(button =>
  button.addEventListener('click', () => {
    if (!data) return;
    const side = button.dataset.side;
    const action = button.dataset.action;
    const result = action === 'plus' ? nextStep(data, steps, side) : {
      steps: {...steps, [side]: Math.max(0, steps[side] - 1)},
    };
    if (result.reason) {
      document.getElementById('limit-note').textContent = result.reason;
      return;
    }
    Object.assign(steps, result.steps);
    document.querySelectorAll('[data-preset]').forEach(item =>
      item.setAttribute('aria-pressed', String(
        item.dataset.preset === 'original' && !Object.values(steps).some(Boolean))));
    document.getElementById('limit-note').textContent = '';
    updateScene();
  }));
document.querySelectorAll('[data-preset]').forEach(button =>
  button.addEventListener('click', () => {
    if (!data) return;
    for (const side of ORDER) steps[side] = 0;
    if (button.dataset.preset === 'one') steps.back = 1;
    if (button.dataset.preset === 'neighbors') steps.back = steps.left = 1;
    if (button.dataset.preset === 'opposite') steps.back = steps.front = 1;
    document.querySelectorAll('[data-preset]').forEach(item =>
      item.setAttribute('aria-pressed', String(item === button)));
    updateScene();
  }));