// BLOCK 3 — 1:1 übernehmen. Erwartet: Import-Map (BLOCK 0) im <head>, Markup (BLOCK 2) und <script id="kit-data"> auf der Seite.
import * as THREE from 'three';

const W = 1352, H = 574, RAIL_Y = H / 2 - 152;   // Welt = Pixel, Ursprung Bildmitte
const KIT_H = 385;                                // Gesamthöhe Bügel + Trikot in px
const STEP = 170;                                 // Drag-Pixel pro Trikot

const stage = document.getElementById('kit-stage');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, });
renderer.setPixelRatio(Math.min(2, devicePixelRatio));
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = .92;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
stage.insertBefore(renderer.domElement, document.getElementById('kit-bar'));

const scene = new THREE.Scene();
const fov = 30, dist = (H / 2) / Math.tan(THREE.MathUtils.degToRad(fov / 2));
const camera = new THREE.PerspectiveCamera(fov, W / H, 10, 6000);
camera.position.set(0, 0, dist);

scene.add(new THREE.HemisphereLight(0xdfe9f2, 0x1a1f24, 0.55));
const spot = new THREE.SpotLight(0xfff3e2, 5.5, 0, Math.PI / 7, 0.55, 0);
spot.position.set(0, H / 2 + 260, 520); spot.target.position.set(0, RAIL_Y - 220, 0);
spot.castShadow = true; spot.shadow.mapSize.set(1024, 1024); spot.shadow.bias = -0.0004;
scene.add(spot, spot.target);
const fill = new THREE.DirectionalLight(0x9fe8ff, 0.5); fill.position.set(-600, -100, 700); scene.add(fill);
const rim = new THREE.DirectionalLight(0xffffff, 0.7); rim.position.set(500, 300, -400); scene.add(rim);

// Schattenfänger auf der Wand (z leicht hinter den Trikots)
const wall = new THREE.Mesh(new THREE.PlaneGeometry(W * 1.2, H * 1.2), new THREE.ShadowMaterial({ opacity: 0.32 }));
wall.position.z = -170; wall.receiveShadow = true; scene.add(wall);

// ---------- Minimaler GLB-Parser (Positionen, Normalen, UVs, Indizes, BaseColor-Textur) ----------
async function loadGLB(url) {
  const buf = await (await fetch(url)).arrayBuffer();
  const dv = new DataView(buf);
  if (dv.getUint32(0, true) !== 0x46546C67) throw new Error('kein GLB');
  let off = 12, json, bin;
  while (off < buf.byteLength) {
    const len = dv.getUint32(off, true), type = dv.getUint32(off + 4, true);
    const chunk = buf.slice(off + 8, off + 8 + len);
    if (type === 0x4E4F534A) json = JSON.parse(new TextDecoder().decode(chunk));
    else if (type === 0x004E4942) bin = chunk;
    off += 8 + len;
  }
  const NC = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
  const ARR = { 5120: Int8Array, 5121: Uint8Array, 5122: Int16Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array };
  const acc = i => {
    const a = json.accessors[i], bv = json.bufferViews[a.bufferView], T = ARR[a.componentType], n = NC[a.type];
    const start = (bv.byteOffset || 0) + (a.byteOffset || 0), stride = bv.byteStride || 0, es = T.BYTES_PER_ELEMENT * n;
    if (!stride || stride === es) return { arr: new T(bin, start, a.count * n), n, norm: !!a.normalized };
    const out = new T(a.count * n), src = new DataView(bin);
    for (let k = 0; k < a.count; k++) out.set(new T(bin.slice(start + k * stride, start + k * stride + es)), k * n);
    return { arr: out, n, norm: !!a.normalized };
  };
  const texCache = {};
  const tex = async ti => {
    if (texCache[ti]) return texCache[ti];
    const img = json.images[json.textures[ti].source], bv = json.bufferViews[img.bufferView];
    const blob = new Blob([new Uint8Array(bin, bv.byteOffset || 0, bv.byteLength)], { type: img.mimeType || 'image/png' });
    const bmp = await createImageBitmap(blob, { imageOrientation: 'none' });
    const t = new THREE.Texture(bmp); t.flipY = false; t.needsUpdate = true; t.anisotropy = 8;
    return (texCache[ti] = t);
  };
  const group = new THREE.Group();
  const build = async (ni, parent) => {
    const node = json.nodes[ni], obj = new THREE.Group();
    if (node.matrix) obj.applyMatrix4(new THREE.Matrix4().fromArray(node.matrix));
    if (node.translation) obj.position.fromArray(node.translation);
    if (node.rotation) obj.quaternion.fromArray(node.rotation);
    if (node.scale) obj.scale.fromArray(node.scale);
    if (node.mesh != null) for (const p of json.meshes[node.mesh].primitives) {
      const g = new THREE.BufferGeometry();
      const pos = acc(p.attributes.POSITION); g.setAttribute('position', new THREE.BufferAttribute(pos.arr, 3));
      if (p.attributes.NORMAL != null) g.setAttribute('normal', new THREE.BufferAttribute(acc(p.attributes.NORMAL).arr, 3));
      if (p.attributes.TEXCOORD_0 != null) { const u = acc(p.attributes.TEXCOORD_0); g.setAttribute('uv', new THREE.BufferAttribute(u.arr, 2, u.norm)); }
      if (p.indices != null) g.setIndex(new THREE.BufferAttribute(acc(p.indices).arr, 1));
      if (!g.attributes.normal) g.computeVertexNormals();
      const m = json.materials && p.material != null ? json.materials[p.material] : {};
      const pbr = m.pbrMetallicRoughness || {};
      const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.82, metalness: 0.0, side: THREE.DoubleSide });
      if (pbr.baseColorFactor) mat.color.setRGB(pbr.baseColorFactor[0], pbr.baseColorFactor[1], pbr.baseColorFactor[2]);
      if (pbr.baseColorTexture) { const t = await tex(pbr.baseColorTexture.index); t.colorSpace = THREE.SRGBColorSpace; mat.map = t; }
      if (m.normalTexture) { const t = await tex(m.normalTexture.index); mat.normalMap = t; mat.normalScale.set(.8, .8); }
      const mesh = new THREE.Mesh(g, mat); mesh.castShadow = true; mesh.receiveShadow = true;
      obj.add(mesh);
    }
    for (const c of node.children || []) await build(c, obj);
    parent.add(obj);
  };
  const sc = json.scenes[json.scene || 0];
  for (const n of sc.nodes) await build(n, group);
  return group;
}

// Stoff-Deformation: unterer Teil zieht bei Bewegung nach + leichtes Flattern
function clothify(root, U) {
  root.traverse(o => {
    if (!o.isMesh) return;
    o.material.onBeforeCompile = sh => {
      sh.uniforms.uSwing = U.uSwing; sh.uniforms.uFlut = U.uFlut; sh.uniforms.uTime = U.uTime; sh.uniforms.uTop = U.uTop; sh.uniforms.uLen = U.uLen;
      sh.vertexShader = 'uniform float uSwing; uniform float uFlut; uniform float uTime; uniform float uTop; uniform float uLen;\n' + sh.vertexShader.replace('#include <begin_vertex>', `
        vec3 transformed = vec3(position);
        float hang = clamp((uTop - position.y) / uLen, 0.0, 1.0);
        float body = smoothstep(0.16, 1.0, hang);
        transformed.x += uSwing * body * body * uLen * 0.22;
        transformed.z += sin(uTime * 7.0 + position.y * 18.0 / uLen + position.x * 6.0 / uLen) * uFlut * body * uLen * 0.018;
        transformed.x += sin(uTime * 5.3 + position.y * 11.0 / uLen) * uFlut * body * uLen * 0.012;
      `);
    };
    o.material.needsUpdate = true;
  });
}

// Fallback, falls ein GLB fehlt: Bild als leicht gewölbte Fläche
function planeKit(src, w0, h0) {
  const g = new THREE.PlaneGeometry(1, h0 / w0, 24, 32);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const x = p.getX(i); p.setZ(i, Math.cos(x * Math.PI) * 0.06); }
  g.computeVertexNormals();
  const t = new THREE.TextureLoader().load(src); t.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ map: t, transparent: true, alphaTest: .4, side: THREE.DoubleSide, roughness: .85 }));
  m.castShadow = true; const gr = new THREE.Group(); gr.add(m); return gr;
}

const kits = [];          // { pivot, inner, x, vx, ang, av, U, ... }
let active = 0, dragDx = 0, dragging = false, list = [], listSig = '', gotList = false;

function slot(d) {
  const s = Math.sign(d), ad = Math.abs(d), n1 = Math.min(1, ad);
  return {
    x: s * (n1 * 238 + Math.max(0, ad - 1) * 66),
    rotY: -s * n1 * THREE.MathUtils.degToRad(74),
    z: -n1 * 70 - Math.max(0, ad - 1) * 6,
    dim: 1 - n1 * .42 - Math.max(0, ad - 1) * .08,
  };
}

async function buildKit(k, i) {
  let inner;
  try { inner = await loadGLB(k.glb); } catch (e) { inner = planeKit(k.img, k.W || 500, k.H || 700); }
  // normieren: Höhe, Haken finden
  const box = new THREE.Box3().setFromObject(inner), size = box.getSize(new THREE.Vector3());
  const s = KIT_H / size.y; inner.scale.multiplyScalar(s);
  inner.updateMatrixWorld(true);
  const b2 = new THREE.Box3().setFromObject(inner);
  // Hakenpunkt = Mittel der obersten 3 % Vertices
  const v = new THREE.Vector3(), acc = new THREE.Vector3(); let n = 0; const yCut = b2.max.y - KIT_H * 0.03;
  inner.traverse(o => { if (!o.isMesh) return; const p = o.geometry.attributes.position; for (let j = 0; j < p.count; j += 3) { v.fromBufferAttribute(p, j).applyMatrix4(o.matrixWorld); if (v.y > yCut) { acc.add(v); n++; } } });
  if (n) acc.divideScalar(n); else acc.set((b2.min.x + b2.max.x) / 2, b2.max.y, (b2.min.z + b2.max.z) / 2);
  const hookInset = KIT_H * -0.002;          // Hakenbogen liegt auf der Stange auf
  const holder = new THREE.Group(); holder.add(inner);
  inner.position.set(-acc.x, -(acc.y - hookInset) + inner.position.y, -acc.z);
  const pivot = new THREE.Group(); pivot.add(holder); scene.add(pivot);
  const U = { uSwing: { value: 0 }, uFlut: { value: 0 }, uTime: { value: 0 }, uTop: { value: 0 }, uLen: { value: 1 } };
  // Uniforms im lokalen Mesh-Raum: oberste/unterste Position in Geometrie-Koordinaten
  let top = -Infinity, bot = Infinity;
  inner.traverse(o => { if (!o.isMesh) return; o.geometry.computeBoundingBox(); top = Math.max(top, o.geometry.boundingBox.max.y); bot = Math.min(bot, o.geometry.boundingBox.min.y); });
  U.uTop.value = top; U.uLen.value = top - bot;
  clothify(inner, U);
  const sl = slot(i - active);
  pivot.position.set(sl.x, RAIL_Y, sl.z); pivot.rotation.y = sl.rotY;
  const mats = []; inner.traverse(o => { if (o.isMesh && o.material.name !== 'haken' && !mats.includes(o.material)) mats.push(o.material); });
  kits[i] = { pivot, holder, inner, U, mats, x: sl.x, vx: 0, ang: 0, av: 0, flut: 0, idx: i };
}

async function setList(newList, idx) {
  kits.splice(0).forEach(k => k && scene.remove(k.pivot));
  list = newList; active = Math.max(0, Math.min(idx || 0, list.length - 1));
  document.getElementById('kit-load').style.display = '';
  await Promise.all(list.map((k, i) => buildKit(k, i)));
  document.getElementById('kit-load').style.display = 'none';
}

function go(i, from) {
  const j = Math.max(0, Math.min(list.length - 1, i));
  if (j === active) return;
  active = j;
}

// ---------- Physik ----------
let last = performance.now(), t = 0;
function tick(now) {
  const dt = Math.min(0.033, Math.max(0, (now - last) / 1000)); last = now; t += dt;
  const frac = active - dragDx / STEP;
  kits.forEach((k, i) => {
    if (!k) return;
    const sl = slot(i - frac);
    // Position folgt dem Ziel kritisch gedämpft (wie ein Bügel, der über die Stange rutscht)
    const kx = dragging ? 260 : 90, cx = 2 * Math.sqrt(kx);
    const ax = (sl.x - k.x) * kx - k.vx * cx;
    k.vx += ax * dt; k.x += k.vx * dt;
    k.pivot.position.x = k.x;
    k.pivot.position.z += (sl.z - k.pivot.position.z) * Math.min(1, dt * 9);
    k.pivot.rotation.y += (sl.rotY - k.pivot.rotation.y) * Math.min(1, dt * 7);
    // Pendel um den Haken: Beschleunigung der Stange treibt den Ausschlag (Trägheit)
    const g = 26, damp = 2.4;
    const aa = -g * Math.sin(k.ang) - damp * k.av - ax * 0.0021;
    k.av += aa * dt; k.ang += k.av * dt;
    k.ang = Math.max(-0.5, Math.min(0.5, k.ang));
    k.holder.rotation.z = k.ang;
    // Saum hängt nach, Flattern klingt ab
    k.flut += (Math.min(1, Math.abs(k.vx) / 900 + Math.abs(k.av) * .6) - k.flut) * Math.min(1, dt * 4);
    k.U.uSwing.value = -k.av * 0.18 - k.vx * 0.00012;
    k.U.uFlut.value = k.flut; k.U.uTime.value = t;
    const dim = sl.dim; k.mats.forEach(m => m.color.setScalar(dim));
  });
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

// ---------- Interaktion ----------
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
let x0 = 0, moved = false;
stage.addEventListener('pointerdown', e => {
  x0 = e.clientX; moved = false; dragging = true; stage.classList.add('drag');
  stage.setPointerCapture(e.pointerId);
});
stage.addEventListener('pointermove', e => {
  if (!dragging) return;
  const dx = e.clientX - x0; if (Math.abs(dx) > 5) moved = true;
  const lo = -(list.length - 1 - active) * STEP - 70, hi = active * STEP + 70;
  dragDx = Math.max(lo, Math.min(hi, dx));
});
stage.addEventListener('pointerup', e => {
  dragging = false; stage.classList.remove('drag');
  if (moved) { const j = Math.round(active - dragDx / STEP); dragDx = 0; active = Math.max(0, Math.min(list.length - 1, j)); return; }
  dragDx = 0;
  const r = stage.getBoundingClientRect();
  mouse.set((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hits = ray.intersectObjects(kits.filter(Boolean).map(k => k.pivot), true);
  if (hits.length) { let o = hits[0].object; const k = kits.find(k => { let p = o; while (p) { if (p === k.pivot) return true; p = p.parent; } return false; }); if (k) go(k.idx); }
});
addEventListener('keydown', e => { if (e.key === 'ArrowRight') go(active + 1); if (e.key === 'ArrowLeft') go(active - 1); });

// Daten: vom Django-View als JSON in #kit-data gerendert (Reihenfolge = Saison aufsteigend)
const KITS = JSON.parse(document.getElementById('kit-data').textContent);
setList(KITS, 0);
