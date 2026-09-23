import * as THREE from 'three';

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
const expansion = new THREE.Group();
world.add(expansion);
const roofSkin = [];
const target = new THREE.Vector3(0, 24, 0);
let azimuth = 0.58, elevation = 0.62, distance = 475, dragging = false, lastX = 0, lastY = 0;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const paint = (hex, options = {}) => new THREE.MeshStandardMaterial({
  color: hex, roughness: .83, metalness: .08, side: THREE.DoubleSide, ...options,
});
const concrete = paint('#8a9290'), dark = paint('#293336');
const yellow = paint('#e3b42e'), tierColor = paint('#858684');
const glass = paint('#718587', {transparent: true, opacity: .65});

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
    diagonal: [.58, .62, 475],
    rear: [.05, .37, 475],
    top: [.62, 1.12, 465],
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

// Original Unity meshes are passed through unchanged (only their hierarchy
// transforms are baked by the offline exporter). The additions below have
// different materials and live in their own disposable, non-persistent group.
function addQuad(group, a, b, c, d, material) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(
    [...a, ...b, ...c, ...a, ...c, ...d], 3));
  geometry.computeVertexNormals();
  group.add(new THREE.Mesh(geometry, material));
}
function beam(group, a, b, radius, material) {
  const from = new THREE.Vector3(...a), to = new THREE.Vector3(...b);
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, from.distanceTo(to), 5), material);
  mesh.position.copy(from).add(to).multiplyScalar(.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), to.sub(from).normalize());
  group.add(mesh);
}
function buildExpansion(bounds) {
  // These anchors are measured from the supplied back2 seat data:
  // y<=36.6251, z<=92.661, x~-108..105. The new terrace extends
  // outwards, without stretching or replacing the original Unity vertices.
  const rear = bounds[2][1];
  const top = bounds[1][1];
  const left = -108, right = 105, rows = 18, depth = .91, rise = .43;
  const outer = rear + rows * depth;
  for (let row = 0; row < rows; row++) {
    const za = rear + row * depth, zb = za + depth;
    const ya = top + row * rise, yb = ya + rise;
    addQuad(expansion, [left, ya, za], [right, ya, za], [right, ya, zb], [left, ya, zb], tierColor);
    addQuad(expansion, [left, ya, zb], [right, ya, zb], [right, yb, zb], [left, yb, zb], concrete);
  }
  // Two tapered corner bridges: the rear tier joins the adjacent side
  // silhouette rather than ending as a floating rectangular slab.
  for (const sign of [-1, 1]) {
    const x = sign < 0 ? left : right;
    const sideX = sign * 115;
    for (let i = 0; i < 14; i++) {
      const t = i / 14, next = (i + 1) / 14;
      const z0 = rear + 16 * t, z1 = rear + 16 * next;
      const sideZ0 = 80 + 19 * t, sideZ1 = 80 + 19 * next;
      const y0 = top + 8 * t, y1 = top + 8 * next;
      addQuad(expansion, [x, y0, z0], [sideX, y0, sideZ0],
        [sideX, y1, sideZ1], [x, y1, z1], tierColor);
    }
    // Corner canopy from the original side-roof edge to the rear addition.
    addQuad(expansion, [sideX, 43, 82], [x, 43, rear - 2],
      [x, 54, outer + 7], [sideX, 51, 104], dark);
    roofSkin.push(expansion.children.at(-1));
    beam(expansion, [sideX, 43, 82], [sideX, 51, 104], .48, yellow);
  }
  // Bowl seats are a low-poly instanced representation of the NEW rows,
  // not a claim that these are Unity chair objects.
  const chair = new THREE.BoxGeometry(.42, .26, .38);
  const seats = new THREE.InstancedMesh(chair, yellow, rows * 350);
  const blackSeats = new THREE.InstancedMesh(chair, dark, rows * 350);
  const matrix = new THREE.Matrix4();
  let goldCount = 0, blackCount = 0;
  for (let row = 0; row < rows; row++) {
    for (let x = left + 1; x < right - .8; x += .61) {
      // Access aisles continue through the added tier.
      if (Math.abs(x + 56) < 1.2 || Math.abs(x + 3) < 1.2 || Math.abs(x - 54) < 1.2) continue;
      matrix.makeTranslation(x, top + row * rise + .21, rear + row * depth + .42);
      const black = (Math.floor(x * 4 + row * 7) % 9 + 9) % 9 < 3;
      (black ? blackSeats : seats).setMatrixAt(black ? blackCount++ : goldCount++, matrix);
    }
  }
  seats.count = goldCount;
  blackSeats.count = blackCount;
  seats.instanceMatrix.needsUpdate = blackSeats.instanceMatrix.needsUpdate = true;
  expansion.add(seats, blackSeats);

  // Full-height outside wall and roof extension, whose inner edge joins the
  // measured outer edge of the extracted center3 roof (z~93, y~43).
  addQuad(expansion, [left - 3, 0, outer + 2], [right + 3, 0, outer + 2],
    [right + 3, top + 18, outer + 2], [left - 3, top + 18, outer + 2], dark);
  for (let x = left - 3; x < right + 3; x += 11.5) {
    addQuad(expansion, [x, 8, outer + 2.15], [x + 6.5, 8, outer + 2.15],
      [x + 6.5, 40, outer + 2.15], [x, 40, outer + 2.15], glass);
    beam(expansion, [x, 0, outer + 2.6], [x, 55, outer + 2.6], .53, concrete);
  }
  addQuad(expansion, [left - 5, 43, rear - 2], [right + 5, 43, rear - 2],
    [right + 7, 55, outer + 7], [left - 7, 55, outer + 7], concrete);
  roofSkin.push(expansion.children.at(-1));
  addQuad(expansion, [left - 7, 55, outer + 7], [right + 7, 55, outer + 7],
    [right + 7, 53, outer + 7], [left - 7, 53, outer + 7], yellow);
  for (let x = left - 5; x <= right + 5; x += 14) {
    beam(expansion, [x, 42.8, rear - 2], [x, 54.8, outer + 7], .58, yellow);
    beam(expansion, [x, 42.8, rear - 2], [x + 14, 54.8, outer + 7], .21, concrete);
    beam(expansion, [x, 44, outer], [x, 55, outer + 7], .49, yellow);
  }
  expansion.visible = false;
  const selected = document.querySelector('[data-state][aria-pressed="true"]')?.dataset.state;
  expansion.visible = selected !== 'before';
  roofSkin.forEach(panel => panel.visible = selected !== 'cutaway');
}

function fallbackWith(message) {
  metrics.textContent = message;
  fallback.hidden = false;
  host.hidden = true;
}

async function main() {
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
    const data = await binResponse.arrayBuffer();
    const textureLoader = new THREE.TextureLoader();
    const textures = Object.fromEntries(manifest.textures.map(name => {
      const texture = textureLoader.load(base + name + '.webp');
      texture.colorSpace = THREE.SRGBColorSpace;
      return [name, texture];
    }));
    const materialCache = new Map();
    for (const entry of manifest.meshes) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(
        new Float32Array(data, entry.positionOffset, entry.vertexCount * 3), 3));
      geometry.setAttribute('uv', new THREE.BufferAttribute(
        new Float32Array(data, entry.uvOffset, entry.vertexCount * 2), 2));
      let indices = [];
      const materials = [];
      for (const part of entry.parts) {
        const start = indices.length;
        indices.push(...new Uint32Array(data, part.indexOffset, part.indexCount));
        geometry.addGroup(start, part.indexCount, materials.length);
        const key = part.texture || part.material;
        if (!materialCache.has(key)) materialCache.set(key, paint(
          part.texture ? '#ffffff' : shade(part.material),
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
    }
    buildExpansion(manifest.backUpperSeatBounds);
    const elapsed = ((performance.now() - start) / 1000).toFixed(1);
    metrics.textContent = `${manifest.meshes.length} Originalmeshes · ${elapsed} s geladen`;
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
    if (camera.aspect < 1 && distance < 475 / camera.aspect) {
      distance = 475 / camera.aspect;
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
      metrics.textContent = `${world.children.length - 1} Originalmeshes · ${fps} fps`;
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
document.querySelectorAll('[data-state]').forEach(button =>
  button.addEventListener('click', () => {
    expansion.visible = button.dataset.state !== 'before';
    roofSkin.forEach(panel => panel.visible = button.dataset.state !== 'cutaway');
    const image = document.getElementById('fallback-image');
    image.src = image.dataset[button.dataset.state];
    image.alt = button.dataset.state !== 'before'
      ? 'Berechnete 2D-Projektion der Originalmeshes mit modellierter Ausbaugeometrie'
      : 'Berechnete 2D-Projektion der Dortmunder Originalmeshes';
    document.querySelectorAll('[data-state]').forEach(item =>
      item.setAttribute('aria-pressed', String(item === button)));
  }));
const initialState = new URLSearchParams(location.search).get('ausbau');
if (initialState === '1') document.querySelector('[data-state="after"]').click();
if (initialState === 'offen') document.querySelector('[data-state="cutaway"]').click();