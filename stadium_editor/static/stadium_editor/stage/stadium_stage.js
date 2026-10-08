/* stadium_stage.js — BLUEPRINT · Stadion im 2D-Modus · V1
 *
 * Eingabe:  Live-Scene-JSON (websoccer.stadium-live-scene, Version 1) in Feldmetern,
 *           Ursprung Spielfeldmitte, +X Tor-zu-Tor, +Y Seitenlinie-zu-Seitenlinie, +Z hoch.
 *           Zusätzlich `mainStand` (Kameraseite). Kamera liegt im Modul (Preset), nicht in der Szene.
 * Ausgabe:  WebGL-Canvas mit dem Kessel von der Bande nach außen, Hintergrund transparent.
 * Vertrag:  project(xm, ym, zm) → {x, y, d, visible} — die eine Projektion für alles,
 *           was darüber gezeichnet wird (Figuren, Ball, Banden, Torrahmen).
 *
 * Regeln (claude_2d-stadion.md): Block = eine schräge Fläche; rows/seats adressieren nur Farben;
 * Sitze auf festem Raster 0,5 × 0,8 m; Stufen alle 0,8 m; Dach nur Traufkante und Unterseite;
 * Kameraseite wird nie gezeichnet; kein Auto-Fit — das Feld ist der Maßstab.
 */
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import {blockSupportQuads, facadeEdgeTopHeights} from './stadium_geometry_helpers.js?v=25';
import {buildSeatRenderPlan, seatBasis} from './seat_rendering.js?v=2';
import {PITCH, buildPitchLayout} from './pitch_geometry.js?v=1';
import {buildFloodlightPlan} from './stadium_lighting.js?v=1';
import {lightingPreset} from './stadium_lighting_presets.js?v=1';
import {ringVertexHeight, ringFasciaHeights} from './roof_ring_profile.mjs?v=1';

const SKY_URLS = Object.freeze({
  day: new URL('./assets/stadium_sky_day.png?v=1', import.meta.url).href,
  night: new URL('./assets/stadium_sky_night.png?v=1', import.meta.url).href,
});

export const PRESET = Object.freeze({
  height: 42,        // Kamerahöhe über Rasen (m)
  distance: 28,      // Abstand hinter der Seitenlinie der Kameraseite (m)
  tilt: 43,          // Neigung nach unten (°)
  zoom: 700,         // Brennweite in Rahmeneinheiten
  frame: [1880, 940],// Referenzrahmen der Bühne
  principal: [940, 640], // Hauptpunkt im Rahmen (Bildmitte liegt unter der Rahmenmitte)
  near: 4, far: 900,
});

export const RULES = Object.freeze({
  seatPitch: 0.5,    // m je Sitz
  rowPitch: 0.8,     // m je Reihe (Stufenkante)
  seatBox: [0.42, 0.56, 0.42], // Sitzschale b × h × t
  seatClearance: 0.04, // Mindestabstand zur Trittfläche
  soffitMax: 6,      // Blende unter der Vorderkante, max. Höhe
  gapPanelMax: 3.0,  // Fugenpaneel nur bis zu dieser Lücke — offene Ecken bleiben offen
  fascia: 1.2,       // Traufkante des Dachs (m)
  seatMinL: 0.22, wallColor: 0x101316, treadColor: 0x22262b, riserColor: 0x15181c, soffitColor: 0x1c2025,
  roofColor: 0x4a525b, fasciaColor: 0x8a9199, facadeColor: 0x2b3037, buildingColor: 0x2a2f36, greenColor: 0x11301c, roadColor: 0x1a1e23, groundColor: 0x0d1115, pitchColor: 0x0f5a2b, pitchColor2: 0x0d5027,
});

// ShapeGeometry triangulates the annulus in 2D; each contour vertex keeps its
// measured height before the mesh is rotated into the horizontal stadium plane.
export function buildRingRoofGeometry(ringRoof, rot) {
  const contour = points => points.map(point => {
    const r = rot(point);
    return new THREE.Vector2(-r[0], -r[1]);
  });
  const outer = contour(ringRoof.outer);
  const inner = contour(ringRoof.inner);
  const shape = new THREE.Shape(outer);
  shape.holes.push(new THREE.Path(inner));
  const geometry = new THREE.ShapeGeometry(shape);
  const positions = geometry.getAttribute('position');
  for (let i = 0; i < positions.count; i++) {
    const x = positions.getX(i), y = positions.getY(i);
    positions.setZ(i, ringVertexHeight(
      x, y, inner, ringRoof.zInner, ringRoof.zOuter));
  }
  positions.needsUpdate = true;
  geometry.computeVertexNormals();
  return geometry;
}

/* ── Geometrie-Hilfen ───────────────────────────────────────────────── */
const v2 = (a, b) => [b[0] - a[0], b[1] - a[1]];
const len2 = a => Math.hypot(a[0], a[1]);
const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
const lerp2 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

// Abstand eines Punkts zum Spielfeld-Rechteck (0 innerhalb)
function pitchDistance(p) {
  const dx = Math.max(Math.abs(p[0]) - PITCH.length / 2, 0);
  const dy = Math.max(Math.abs(p[1]) - PITCH.width / 2, 0);
  return Math.hypot(dx, dy);
}

/* Kanten des Blocks geometrisch bestimmen — unabhängig von der Wicklung der Quelle.
 * Das Paar (q0-q1, q2-q3) sind Vorder-/Hinterkante; welche vorne liegt, sagt der Feldabstand.
 * Links/rechts aus Sicht des Spielfelds: links = Z × n (n = Normale vom Feld weg). */
function orientBlock(q) {
  const e1 = [q[0], q[1]], e2 = [q[2], q[3]];
  const d1 = pitchDistance(mid(...e1)), d2 = pitchDistance(mid(...e2));
  let front = d1 <= d2 ? e1 : e2, back = d1 <= d2 ? e2 : e1;
  const n = v2(mid(...front), mid(...back));           // vom Feld weg
  const left = [-n[1], n[0]];                          // Z × n
  const dot = (p, w) => p[0] * w[0] + p[1] * w[1];
  if (dot(front[0], left) < dot(front[1], left)) front = [front[1], front[0]];
  if (dot(back[0], left) < dot(back[1], left)) back = [back[1], back[0]];
  const [A, B] = front, [D, C] = back;                  // A vorne-links, B vorne-rechts, C hinten-rechts, D hinten-links
  const width = (len2(v2(A, B)) + len2(v2(D, C))) / 2;
  const depth = (len2(v2(A, D)) + len2(v2(B, C))) / 2;
  return { A, B, C, D, width, depth, n };
}

/* Drehung der Szene, sodass die Kameraseite (mainStand) bei +Y liegt. */
function sceneRotation(scene) {
  const main = scene.mainStand || 'SUED';
  const pts = scene.blocks.filter(b => b.stand === main).map(b => b.quad).flat();
  if (!pts.length) return 0;
  const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length, cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  const theta = Math.atan2(cy, cx);
  const phi = Math.PI / 2 - theta;
  return Math.round(phi / (Math.PI / 2)) * (Math.PI / 2);   // nur Vielfache von 90°
}

/* ── Texturen aus Canvas: Beton mit Körnung, Fassade mit Etagen und Fenstern ─── */
function canvasTexture(size, draw, repeat) {
  const c = document.createElement('canvas'); c.width = c.height = size;
  const ctx = c.getContext('2d'); draw(ctx, size);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) t.repeat.set(repeat[0], repeat[1]);
  return t;
}
function concreteTexture(base, seed = 1) {
  let r = seed >>> 0; const rnd = () => { r = (r * 1664525 + 1013904223) >>> 0; return r / 4294967296; };
  return canvasTexture(256, (ctx, n) => {
    ctx.fillStyle = base; ctx.fillRect(0, 0, n, n);
    for (let i = 0; i < 2600; i++) { ctx.fillStyle = rnd() > 0.5 ? 'rgba(0,0,0,0.18)' : 'rgba(255,255,255,0.05)'; ctx.fillRect(rnd() * n, rnd() * n, 2, 2); }
    ctx.strokeStyle = 'rgba(0,0,0,0.22)'; ctx.lineWidth = 1;
    for (let y = 0; y < n; y += 64) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(n, y); ctx.stroke(); }
  });
}
function facadeTexture(floors) {
  return canvasTexture(512, (ctx, n) => {
    ctx.fillStyle = '#2b3037'; ctx.fillRect(0, 0, n, n);
    const fh = n / floors;
    for (let f = 0; f < floors; f++) {
      const y = n - (f + 1) * fh;
      ctx.fillStyle = '#20252b'; ctx.fillRect(0, y, n, 2);                       // Etagenband
      for (let x = 12; x < n - 20; x += 40) {                                  // Fenster
        ctx.fillStyle = f % 2 ? '#3b4650' : '#33404a'; ctx.fillRect(x, y + fh * 0.28, 24, fh * 0.44);
        ctx.fillStyle = 'rgba(255,255,255,0.06)'; ctx.fillRect(x, y + fh * 0.28, 24, 2);
      }
    }
  });
}

/* ── Modul ──────────────────────────────────────────────────────────── */
export function createStadiumStage({ canvas, scene, width, height, drawPitch = false, preset = PRESET, rules = RULES, seatMode = 'instances',
                                     view = 'match', orbit = {}, surroundings = null, facade = null, seat = null, lighting = 'day',
                                      floodlight = false, exposure = 1, design = null, coordinateRotation = null }) {
  let lightingMode = lighting === 'night' ? 'night' : 'day';
  const isSeat = view === 'seat';
  const isOrbit = view === 'orbit' || isSeat;
  const ORBIT = Object.assign({ azimuth: 40, elevation: 32, distance: 0, fov: 38, targetZ: 8 }, orbit);
  const drawSurroundings = surroundings === null ? isOrbit : surroundings;
  const drawFacade = facade === null ? (isOrbit && scene.facade !== false) : facade;
  const groundLevel = (scene.steckbrief && scene.steckbrief.sunken) || 0;   // Gelände über Rasenniveau (versenkte Stadien)
  if (isOrbit) drawPitch = true;
  const W = width || canvas.clientWidth || preset.frame[0];
  const H = height || canvas.clientHeight || preset.frame[1];

  /* Koordinaten: Szene (X, Y, Z) → gedreht (mainStand bei +Y) → three (x = −X, y = Z, z = Y).
   * Die Abbildung ist eine echte Drehung (det = +1): Kamera auf der Haupttribüne, +X links im Bild. */
  const phi = coordinateRotation === null ? sceneRotation(scene) : coordinateRotation;
  if (!Number.isFinite(phi)) throw new Error('Ungültige Szenenrotation.');
  const cph = Math.cos(phi), sph = Math.sin(phi);
  const rot = p => [p[0] * cph - p[1] * sph, p[0] * sph + p[1] * cph];
  const toWorld = (p, z) => { const r = rot(p); return new THREE.Vector3(-r[0], z, r[1]); };

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H, false);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const three = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera();
  three.add(camera);
  let active = true;
  const skyTextures = {};
  let skyMesh = null;
  if (isSeat) {
    for (const mode of ['day', 'night']) {
      skyTextures[mode] = new THREE.TextureLoader().load(
        SKY_URLS[mode],
        () => { if (active && lightingMode === mode) render(); },
      );
      skyTextures[mode].colorSpace = THREE.SRGBColorSpace;
    }
  }

  /* Kamera: Preset, Hauptpunkt unter der Bildmitte — exakt die Projektion der bisherigen Bühne,
   * nur als echte (nicht gespiegelte) Kamera. */
  function applyCamera() {
    if (isSeat && seat) {
      camera.fov = seat.fov || 62; camera.aspect = W / H; camera.near = 0.3; camera.far = 3000;
      THREE.PerspectiveCamera.prototype.updateProjectionMatrix.call(camera);
      const p = seat.position.clone();                       // Sitzmitte (three-Koordinaten)
      const inward = new THREE.Vector3(-p.x, 0, -p.z).normalize();
      p.addScaledVector(inward, 0.12).add(new THREE.Vector3(0, 1.18, 0));   // Augenhöhe sitzend
      camera.position.copy(p); camera.up.set(0, 1, 0);
      camera.lookAt(0, 1.2, 0); camera.updateMatrixWorld(true);
      return;
    }
    if (isOrbit && !isSeat) {
      const ext = (scene.outline || []).reduce((m, p) => Math.max(m, Math.hypot(p[0], p[1])), 120);
      const dist = ORBIT.distance || ext * 2.35;
      camera.fov = ORBIT.fov; camera.aspect = W / H; camera.near = 2; camera.far = 4000;
      THREE.PerspectiveCamera.prototype.updateProjectionMatrix.call(camera);
      const az = ORBIT.azimuth * Math.PI / 180, el = ORBIT.elevation * Math.PI / 180;
      camera.position.set(Math.sin(az) * Math.cos(el) * dist, Math.sin(el) * dist + ORBIT.targetZ, Math.cos(az) * Math.cos(el) * dist);
      camera.up.set(0, 1, 0); camera.lookAt(0, ORBIT.targetZ, 0); camera.updateMatrixWorld(true);
      return;
    }
    const F = preset.zoom * (W / preset.frame[0]);
    const cx = preset.principal[0] / preset.frame[0] * W;
    const cy = preset.principal[1] / preset.frame[1] * H;
    const n = preset.near;
    camera.projectionMatrix.makePerspective(-cx / F * n, (W - cx) / F * n, cy / F * n, -(H - cy) / F * n, n, preset.far);
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    const tilt = preset.tilt * Math.PI / 180;
    const camY = PITCH.width / 2 + preset.distance;      // Szene-Y der Kamera (Kameraseite)
    camera.position.set(0, preset.height, camY);
    camera.up.set(0, 1, 0);
    camera.lookAt(0, preset.height - Math.sin(tilt), camY - Math.cos(tilt));
    camera.updateMatrixWorld(true);
  }
  camera.updateProjectionMatrix = applyCamera;
  applyCamera();
  if (isSeat) {
    const distance = 500;
    const imageAspect = 2688 / 1520;
    const viewHeight = 2 * Math.tan(camera.fov * Math.PI / 360) * distance;
    const viewWidth = viewHeight * camera.aspect;
    const skyWidth = Math.max(viewWidth, viewHeight * imageAspect) * 1.02;
    const skyHeight = Math.max(viewHeight, viewWidth / imageAspect) * 1.02;
    skyMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(skyWidth, skyHeight),
      new THREE.MeshBasicMaterial({
        map: skyTextures[lightingMode],
        depthTest: false,
        depthWrite: false,
        fog: false,
        toneMapped: false,
      }),
    );
    skyMesh.position.z = -distance;
    skyMesh.renderOrder = -1000;
    skyMesh.frustumCulled = false;
    camera.add(skyMesh);
  }

  const hemisphere = new THREE.HemisphereLight();
  const ambient = new THREE.AmbientLight();
  const keyLight = new THREE.DirectionalLight();
  const fillLight = new THREE.DirectionalLight();
  three.add(hemisphere, ambient, keyLight, fillLight);
  const lightingMaterials = {
    buildings: new Set(),
    structures: new Set(),
    roofs: new Set(),
    pitch: new Set(),
  };
  const lightPlan = buildFloodlightPlan(scene);
  const floodlightSources = [];
  const fixtureMaterials = new Set();
  const floodlightFill = new THREE.HemisphereLight(0xddeeff, 0x222833, 0);
  three.add(floodlightFill);
  const addSpot = (fixture, position) => {
    const target = new THREE.Object3D();
    target.position.copy(toWorld(fixture.target, fixture.target[2]));
    three.add(target);
    const reach = position.distanceTo(target.position) * 1.65;
    const source = new THREE.SpotLight(0xf4f7ff, 0, reach, 0.72, 0.72, 1);
    source.position.copy(position);
    source.target = target;
    source.userData.onIntensity = fixture.kind === 'rim' ? 460 : 960;
    three.add(source);
    floodlightSources.push(source);
  };
  const fixtureMat = new THREE.MeshLambertMaterial({
    color: 0x9aa3ab, emissive: 0x000000, emissiveIntensity: 0,
  });
  fixtureMaterials.add(fixtureMat);

  /* ── Bauteile sammeln ─────────────────────────────────────────────── */
  const bodyPos = [], bodyCol = [], roofPos = [], roofCol = [];
  const pushQuad = (p0, p1, p2, p3, color, both = true) => {  // p: Vector3
    const c = new THREE.Color(color);
    const tri = (a, b, d) => { bodyPos.push(a.x, a.y, a.z, b.x, b.y, b.z, d.x, d.y, d.z); bodyCol.push(c.r, c.g, c.b, c.r, c.g, c.b, c.r, c.g, c.b); };
    tri(p0, p1, p2); tri(p0, p2, p3);
  };

  if (design && design.blocks) for (const b of scene.blocks) if (design.blocks[b.id]) b.rle = design.blocks[b.id];
  const mainStand = scene.mainStand;
  const drawn = isOrbit ? scene.blocks.slice() : scene.blocks.filter(b => b.stand !== mainStand);
  // Sitzfarben: Helligkeitsboden, damit schwarze Schalen nicht im Körper verschwinden
  const hsl = { h: 0, s: 0, l: 0 };
  const palette = scene.palette.map(h => { const c = new THREE.Color(h); c.getHSL(hsl); if (hsl.l < rules.seatMinL) c.setHSL(hsl.h, hsl.s, rules.seatMinL); return c; });

  // Blockrahmen vorbereiten
  const frames = new Map();
  for (const b of scene.blocks) frames.set(b.id, { b, ...orientBlock(b.quad) });

  // Hat ein Block einen Nachbarn hinter sich (Oberrang)? → dann keine Außenwand
  const covered = new Set();
  for (const f of frames.values()) {
    const back = mid(f.D, f.C);
    for (const g of frames.values()) {
      if (g === f || g.b.stand !== f.b.stand) continue;
      const front = mid(g.A, g.B);
      if (Math.hypot(front[0] - back[0], front[1] - back[1]) < 6 && g.b.z0 > f.b.z0) { covered.add(f.b.id); break; }
    }
  }

  let seatCount = 0;
  const seatPaletteCounts = Array(palette.length).fill(0);
  const seatTransforms = [], seatColors = [], seatIndex = [];
  const tmpM = new THREE.Matrix4(), tmpQ = new THREE.Quaternion(), tmpS = new THREE.Vector3(1, 1, 1), tmpP = new THREE.Vector3();
  const basis = new THREE.Matrix4();

  for (const b of drawn) {
    const f = frames.get(b.id);
    const seatPlan = buildSeatRenderPlan({
      width: f.width, depth: f.depth,
      rowPitch: rules.rowPitch, seatPitch: rules.seatPitch,
      rows: b.rows, seats: b.seats, rle: b.rle,
      paletteSize: palette.length,
    });
    const nRows = seatPlan.rows;
    const nCols = seatPlan.cols;
    const rise = b.z1 - b.z0;
    const seatClearance = Math.max(
      rules.seatClearance, rise / nRows - 0.36,
    );
    const support = blockSupportQuads(b);
    const wallBase = support.wallBase;
    const P = (u, v, z) => toWorld(lerp2(lerp2(f.A, f.B, u), lerp2(f.D, f.C, u), v), z);

    // Stufen: Trittfläche auf z_i, Setzstufe auf z_{i+1}
    for (let i = 0; i < nRows; i++) {
      const v0 = i / nRows, v1 = (i + 1) / nRows;
      const z0 = b.z0 + v0 * rise, z1 = b.z0 + v1 * rise;
      pushQuad(P(0, v0, z0), P(1, v0, z0), P(1, v1, z0), P(0, v1, z0), rules.treadColor, false);
      pushQuad(P(0, v1, z0), P(1, v1, z0), P(1, v1, z1), P(0, v1, z1), rules.riserColor, true);
    }
    // Außenwand hinter dem letzten Rang
    if (!covered.has(b.id)) pushQuad(P(0, 1, b.z1), P(1, 1, b.z1), P(1, 1, wallBase), P(0, 1, wallBase), rules.wallColor, true);
    // Blende unter der Vorderkante (Umlauf zwischen den Rängen)
    if (b.z0 > 3) {
      const h = Math.min(b.z0 - 0.5, rules.soffitMax);
      pushQuad(P(0, 0, b.z0), P(1, 0, b.z0), P(1, 0, b.z0 - h), P(0, 0, b.z0 - h), rules.soffitColor, true);
    }
    // Vorschau-Oberränge erhalten eine geschlossene schräge Unterseite bis
    // zur Auflagerhöhe, ohne eine neue Wand bis zum Boden zu erzeugen.
    if (support.underside) {
      pushQuad(
        ...support.underside.map(point => toWorld(point, point[2])),
        rules.soffitColor, true,
      );
    }
    // Seitenwände der Blöcke (schließen Stufen seitlich, sichtbar an offenen Ecken)
    for (const wall of support.sideWalls) {
      pushQuad(
        ...wall.map(point => toWorld(point, point[2])),
        rules.wallColor, true,
      );
    }

    // Sitze auf festem Raster; Farbe aus der RLE-Zelle
    const axes = seatBasis(
      toWorld(f.A, 0).toArray(), toWorld(f.B, 0).toArray(),
      toWorld(f.D, 0).toArray(), toWorld(f.C, 0).toArray(),
    );
    basis.makeBasis(
      new THREE.Vector3(...axes.right),
      new THREE.Vector3(...axes.up),
      new THREE.Vector3(...axes.back),
    );
    tmpQ.setFromRotationMatrix(basis);
    for (let i = 0; i < nRows; i++) {
      const v = (i + 0.5) / nRows, zTread = b.z0 + (i / nRows) * rise;
      for (let j = 0; j < nCols; j++) {
        const u = (j + 0.5) / nCols;
        const idx = seatPlan.colours[i * nCols + j];
        tmpP.copy(P(u, v, zTread + seatClearance));
        tmpM.compose(tmpP, tmpQ, tmpS);
        seatTransforms.push(tmpM.clone()); seatIndex.push({ block: b.id, row: i, col: j, position: tmpP.clone() });
        seatColors.push(palette[idx] || palette[0]);
        seatPaletteCounts[idx in palette ? idx : 0]++;
        seatCount++;
      }
    }
  }

  // Fugenpaneele: Nachbarblöcke derselben Tribüne und Ebene, Lücke > 0,3 m und ≤ 3 m
  const groups = new Map();
  for (const b of drawn) { const k = b.stand + '|' + b.tier; (groups.get(k) || groups.set(k, []).get(k)).push(frames.get(b.id)); }
  for (const list of groups.values()) {
    list.sort((a, b) => (a.b.order ?? 0) - (b.b.order ?? 0));
    for (let i = 0; i + 1 < list.length; i++) {
      const a = list[i], c = list[i + 1];
      const gapF = len2(v2(a.B, c.A)), gapB = len2(v2(a.C, c.D));
      if (Math.max(gapF, gapB) <= 0.3 || Math.min(gapF, gapB) > rules.gapPanelMax) continue;
      pushQuad(toWorld(a.B, a.b.z0), toWorld(c.A, c.b.z0), toWorld(c.D, c.b.z1), toWorld(a.C, a.b.z1), rules.treadColor, true);
    }
  }

  // Dach: Dortmunds vermessener geschlossener Kranz oder die bisherigen Einzelplatten.
  const roofSegs = (scene.roof && scene.roof.segments) || [];
  const camLimit = PITCH.width / 2 + 6;
  const ringRoof = scene.roof && scene.roof.ring;
  if (ringRoof) {
    const ringMaterial = new THREE.MeshLambertMaterial({
      color: rules.roofColor, side: THREE.DoubleSide,
    });
    lightingMaterials.roofs.add(ringMaterial);
    const mesh = new THREE.Mesh(buildRingRoofGeometry(ringRoof, rot), ringMaterial);
    mesh.rotation.x = -Math.PI / 2;
    three.add(mesh);
    for (let i = 0; i < ringRoof.inner.length; i++) {
      const a = ringRoof.inner[i], b = ringRoof.inner[(i + 1) % ringRoof.inner.length];
      if (!isOrbit && (rot(a)[1] + rot(b)[1]) / 2 > camLimit) continue;
      const fascia = ringFasciaHeights(ringRoof.zInner, rules.fascia);
      const p0 = toWorld(a, fascia.top), p1 = toWorld(b, fascia.top);
      pushQuad(p0, p1, p1.clone().setY(fascia.bottom),
        p0.clone().setY(fascia.bottom), rules.fasciaColor, true);
    }
  }
  for (const seg of ringRoof ? [] : roofSegs) {
    const q = seg.quad.map(rot);
    const cy = q.reduce((s, p) => s + p[1], 0) / 4;
    if (!isOrbit && cy > camLimit) continue;
    const hs = seg.heights || seg.quad.map(() => seg.z);
    const pts = seg.quad.map((p, i) => toWorld(p, hs[i]));
    // Unterseite: Wicklung so, dass die Normale nach unten zeigt (von oben unsichtbar)
    const c = new THREE.Color(rules.roofColor);
    const tri = (a, b2, d) => { roofPos.push(a.x, a.y, a.z, b2.x, b2.y, b2.z, d.x, d.y, d.z); roofCol.push(c.r, c.g, c.b, c.r, c.g, c.b, c.r, c.g, c.b); };
    // jedes Dreieck einzeln so wickeln, dass seine Normale nach unten zeigt — robust auch bei verdrehten Quads
    const down = (a, b2, d) => { const n = new THREE.Vector3().crossVectors(b2.clone().sub(a), d.clone().sub(a)); return n.y > 0 ? tri(a, d, b2) : tri(a, b2, d); };
    for (let i = 1; i + 1 < pts.length; i++) down(pts[0], pts[i], pts[i + 1]);
    // Traufkante an der feldnahen Kante
    const edges = seg.quad.map((_, i) => [i, (i + 1) % seg.quad.length]);
    const inner = edges.reduce((best, e) => {
      const m = mid(seg.quad[e[0]], seg.quad[e[1]]); const d = pitchDistance(m);
      return !best || d < best.d ? { e, d } : best; }, null).e;
    const p0 = pts[inner[0]], p1 = pts[inner[1]];
    pushQuad(p0, p1, p1.clone().setY(p1.y - rules.fascia), p0.clone().setY(p0.y - rules.fascia), rules.fasciaColor, true);
  }

  // Fassade: Außenkontur senkrecht bis über den obersten Rang (nur Außenansicht)
  if (drawFacade && scene.outline && scene.outline.length > 3) {
    const globalTop = Math.max(...scene.blocks.map(b => b.z1)) + 2.5;
    const hasExpansion = scene.blocks.some(b => Number.isFinite(Number(b.wallBaseZ)));
    const facadeBlocks = scene.blocks.filter(b => !covered.has(b.id));
    const floors = Math.max(3, Math.round(globalTop / 4.2));
    const o = scene.outline, fp = [], fuv = [];
    let run = 0;
    const edges = scene.facadeSegments || o.map((p, i) => [p, o[(i + 1) % o.length]]);   // Szene kann Innenkanten ausschließen
    for (let i = 0; i < edges.length; i++) {
      const a = edges[i][0], b2 = edges[i][1];
      const L = Math.hypot(b2[0] - a[0], b2[1] - a[1]); if (L < 0.05) continue;
      const [zTopA, zTopB] = hasExpansion
        ? facadeEdgeTopHeights([a, b2], facadeBlocks, 2.5, roofSegs)
        : [globalTop, globalTop];
      const A0 = toWorld(a, groundLevel), B0 = toWorld(b2, groundLevel);
      const A1 = toWorld(a, zTopA), B1 = toWorld(b2, zTopB);
      const u0 = run / 12, u1 = (run + L) / 12; run += L;
      fp.push(A0.x, A0.y, A0.z, B0.x, B0.y, B0.z, B1.x, B1.y, B1.z, A0.x, A0.y, A0.z, B1.x, B1.y, B1.z, A1.x, A1.y, A1.z);
      fuv.push(u0, 0, u1, 0, u1, 1, u0, 0, u1, 1, u0, 1);
      pushQuad(
        A1, B1,
        B1.clone().setY(zTopB + 0.6),
        A1.clone().setY(zTopA + 0.6),
        rules.fasciaColor,
      );
    }
    const fg = new THREE.BufferGeometry();
    fg.setAttribute('position', new THREE.Float32BufferAttribute(fp, 3)); fg.setAttribute('uv', new THREE.Float32BufferAttribute(fuv, 2)); fg.computeVertexNormals();
    three.add(new THREE.Mesh(fg, new THREE.MeshLambertMaterial({ map: facadeTexture(floors), side: THREE.DoubleSide })));
  }
  // Pylone und Flutlichtmasten (Steckbrief)
  const sb = scene.steckbrief || {};
  if (sb.pylons && scene.outline && scene.outline.length > 3) {
    const o = scene.outline; const segs = []; let total = 0;
    for (let i = 0; i < o.length; i++) { const a = o[i], b2 = o[(i + 1) % o.length]; const L = Math.hypot(b2[0] - a[0], b2[1] - a[1]); segs.push([a, b2, L]); total += L; }
    const col = new THREE.Color(sb.pylons.color || '#f7d418'), h = sb.pylons.height || 60, n = sb.pylons.count || 8;
    for (let k = 0; k < n; k++) {
      let target = ((k + 0.5) / n) * total, acc = 0, pos = o[0];
      for (const [a, b2, L] of segs) { if (acc + L >= target) { const t = (target - acc) / L; pos = [a[0] + (b2[0] - a[0]) * t, a[1] + (b2[1] - a[1]) * t]; break; } acc += L; }
      const out = Math.hypot(pos[0], pos[1]) || 1; const p2 = [pos[0] * (1 + 4 / out), pos[1] * (1 + 4 / out)];
      const m = new THREE.Mesh(new THREE.BoxGeometry(2.4, h, 2.4),
        new THREE.MeshLambertMaterial({
          color: col,
          emissive: scene.preview ? col : 0x000000,
          emissiveIntensity: scene.preview ? 0.28 : 0,
        }));
      const w = toWorld(p2, h / 2); m.position.copy(w); three.add(m);
    }
  }
  for (const fixture of lightPlan.fixtures) {
    const position = toWorld(fixture.position, fixture.position[2]);
    if (fixture.kind === 'rim') {
      const head = new THREE.Mesh(
        new THREE.BoxGeometry(1.6, 0.6, 0.5), fixtureMat,
      );
      head.position.copy(position);
      head.lookAt(new THREE.Vector3(0, 0, 0));
      three.add(head);
      const polePosition = [
        fixture.position[0], fixture.position[1],
        fixture.position[2] - fixture.poleHeight / 2,
      ];
      const pole = new THREE.Mesh(
        new THREE.CylinderGeometry(0.12, 0.12, fixture.poleHeight, 6),
        new THREE.MeshLambertMaterial({color: 0x8a9199}),
      );
      pole.position.copy(toWorld(polePosition, polePosition[2]));
      three.add(pole);
    } else {
      const polePosition = [
        fixture.position[0], fixture.position[1], fixture.poleHeight / 2,
      ];
      const pole = new THREE.Mesh(
        new THREE.CylinderGeometry(0.5, 0.7, fixture.poleHeight, 8),
        new THREE.MeshLambertMaterial({color: 0x9aa3ab}),
      );
      pole.position.copy(toWorld(polePosition, polePosition[2]));
      three.add(pole);
      const head = new THREE.Mesh(
        new THREE.BoxGeometry(6, 3, 1.2), fixtureMat,
      );
      head.position.copy(position);
      head.lookAt(new THREE.Vector3(0, fixture.position[2], 0));
      three.add(head);
    }
  }
  for (const source of lightPlan.sources) {
    addSpot(source, toWorld(source.position, source.position[2]));
  }
  // Umfeld aus OSM: Gebäude extrudiert, Straßen und Grün flach
  if (drawSurroundings && scene.surroundings) {
    const S = scene.surroundings;
    const shapeOf = pts => new THREE.Shape(pts.map(p => { const r = rot(p); return new THREE.Vector2(-r[0], -r[1]); }));
    const bMat = new THREE.MeshLambertMaterial();
    lightingMaterials.buildings.add(bMat);
    for (const b2 of S.buildings || []) {
      try {
        const geo = new THREE.ExtrudeGeometry(shapeOf(b2.poly), { depth: b2.h || 9, bevelEnabled: false });
        const m = new THREE.Mesh(geo, bMat); m.rotation.x = -Math.PI / 2; m.position.y = groundLevel; three.add(m);
      } catch (e) { /* ungültiges Polygon überspringen */ }
    }
    const gMat = new THREE.MeshLambertMaterial({ color: rules.greenColor });
    const bb = scene.standsBounds || [-90, -60, 90, 60];
    const insideStands = pts => pts.some(p => p[0] > bb[0] && p[0] < bb[2] && p[1] > bb[1] && p[1] < bb[3]);
    for (const g of S.green || []) {
      if (insideStands(g)) continue;                                   // Innenraum gehört dem Feld, nicht der Kulisse
      try { const m = new THREE.Mesh(new THREE.ShapeGeometry(shapeOf(g)), gMat); m.rotation.x = -Math.PI / 2; m.position.y = groundLevel + 0.04; three.add(m); } catch (e) { }
    }
    for (const r of S.roads || []) {
      const w = Math.max(3, (r.w || 1) * 2.5);
      for (let i = 0; i + 1 < r.p.length; i++) {
        const a = toWorld(r.p[i], groundLevel + 0.06), b2 = toWorld(r.p[i + 1], groundLevel + 0.06);
        const L = a.distanceTo(b2); if (L < 0.5) continue;
        const m = new THREE.Mesh(new THREE.BoxGeometry(L, 0.02, w), new THREE.MeshLambertMaterial({ color: rules.roadColor }));
        m.position.copy(a).lerp(b2, 0.5); m.lookAt(b2); m.rotateY(Math.PI / 2); three.add(m);
      }
    }
    // Boden: bei versenkten Stadien mit Loch an der Stelle des Kessels, damit der Innenraum unter Geländeniveau sichtbar bleibt
    const gShape = new THREE.Shape([[-800, -800], [800, -800], [800, 800], [-800, 800]].map(p => new THREE.Vector2(p[0], p[1])));
    const holeSrc = scene.groundHole || scene.outline;
    if (groundLevel > 0 && holeSrc && holeSrc.length > 3) {
      const hole = holeSrc.map(p => { const r = rot(p); return new THREE.Vector2(-r[0], -r[1]); });
      if (hole[0].distanceTo(hole[hole.length - 1]) < 0.01) hole.pop();        // Schlusspunkt stört die Triangulation
      gShape.holes.push(new THREE.Path(hole));
    }
    const ground = new THREE.Mesh(new THREE.ShapeGeometry(gShape), new THREE.MeshLambertMaterial({ color: rules.groundColor, side: THREE.DoubleSide }));
    ground.rotation.x = -Math.PI / 2; ground.position.y = groundLevel - 0.05; three.add(ground);
  }

  // Körper als ein Mesh
  const bodyGeo = new THREE.BufferGeometry();
  bodyGeo.setAttribute('position', new THREE.Float32BufferAttribute(bodyPos, 3));
  bodyGeo.setAttribute('color', new THREE.Float32BufferAttribute(bodyCol, 3));
  const buv = []; for (let i = 0; i < bodyPos.length; i += 3) buv.push(bodyPos[i] / 6, (bodyPos[i + 2] + bodyPos[i + 1]) / 6);
  bodyGeo.setAttribute('uv', new THREE.Float32BufferAttribute(buv, 2));
  bodyGeo.computeVertexNormals();
  const concrete = concreteTexture('#8b8f95', 11);
  const bodyMaterial = new THREE.MeshLambertMaterial({
    vertexColors: true, side: THREE.DoubleSide, map: concrete,
  });
  lightingMaterials.structures.add(bodyMaterial);
  three.add(new THREE.Mesh(bodyGeo, bodyMaterial));
  // Dach-Unterseiten: nur Vorderseiten, Normale nach unten → von oben unsichtbar (Regel: nie eine Dachoberseite)
  const roofGeo = new THREE.BufferGeometry();
  roofGeo.setAttribute('position', new THREE.Float32BufferAttribute(roofPos, 3));
  roofGeo.setAttribute('color', new THREE.Float32BufferAttribute(roofCol, 3));
  roofGeo.computeVertexNormals();
  const roofMaterial = new THREE.MeshLambertMaterial({
    vertexColors: true,
    side: isOrbit ? THREE.DoubleSide : THREE.FrontSide,
  });
  lightingMaterials.roofs.add(roofMaterial);
  three.add(new THREE.Mesh(roofGeo, roofMaterial));

  // Sitze als Instanzen
  let seats = null;
  if (seatMode === 'instances' && seatCount) {
    // Sitzschale: Sitzfläche + Rückenlehne, beides in einer Geometrie (Instanzen bleiben ein Draw-Call)
    const pan = new THREE.BoxGeometry(rules.seatBox[0], 0.10, rules.seatBox[2]);
    pan.translate(0, 0.12, -0.02);
    const back = new THREE.BoxGeometry(rules.seatBox[0], 0.52, 0.08);
    back.translate(0, 0.30, rules.seatBox[2] / 2 - 0.04);
    const geo = mergeGeometries([pan, back]);
    // Vereinsfarben müssen auch im Nachtmodus und bei steilen Lehnen exakt
    // lesbar bleiben. Die Stufen liefern weiterhin die räumliche Schattierung;
    // die getrennten Schalen werden selbst nicht vom Flutlicht abgedunkelt.
    seats = new THREE.InstancedMesh(geo, new THREE.MeshBasicMaterial({
      color: 0xffffff, toneMapped: false,
    }), seatCount);
    for (let i = 0; i < seatCount; i++) { seats.setMatrixAt(i, seatTransforms[i]); seats.setColorAt(i, seatColors[i]); }
    seats.instanceMatrix.needsUpdate = true; seats.instanceColor.needsUpdate = true;
    three.add(seats);
  }

  // Laufbahn (Steckbrief/Szene): Tartanring zwischen Innenraum und Rängen, Innenraum als Rasen
  if (isSeat) {
    const grassMaterial = scene.preview
      ? new THREE.MeshBasicMaterial({color: 0x164829, toneMapped: false})
      : new THREE.MeshLambertMaterial({color: rules.greenColor});
    const seatGround = new THREE.Mesh(
      new THREE.PlaneGeometry(360, 280),
      grassMaterial,
    );
    seatGround.rotation.x = -Math.PI / 2;
    seatGround.position.y = scene.preview ? 0.12 : -0.02;
    three.add(seatGround);
  }
  if (scene.track && scene.track.outer) {
    const shape = new THREE.Shape(scene.track.outer.map(p => { const r = rot(p); return new THREE.Vector2(-r[0], -r[1]); }));
    if (scene.track.inner) shape.holes.push(new THREE.Path(scene.track.inner.map(p => { const r = rot(p); return new THREE.Vector2(-r[0], -r[1]); })));
    const ring = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshLambertMaterial({ color: 0x8e3b30 }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = 0.02; three.add(ring);
    if (scene.track.inner) {
      const infield = new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape(scene.track.inner.map(p => { const r = rot(p); return new THREE.Vector2(-r[0], -r[1]); }))), new THREE.MeshLambertMaterial({ color: rules.pitchColor2 }));
      infield.rotation.x = -Math.PI / 2; infield.position.y = 0.005; three.add(infield);
    }
  }
  // Spielfeld nur für die Abnahme — im Spiel gehört der Rasen der Bühne
  if (drawPitch) {
    const g = new THREE.Group();
    const pitchLayout = buildPitchLayout(phi);
    for (const stripe of pitchLayout.stripes) {
      const [a, b, c, d] = stripe.quad.map(
        ([x, z]) => new THREE.Vector3(x, scene.preview ? 0.16 : 0.01, z),
      );
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute([
        a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z,
        a.x, a.y, a.z, c.x, c.y, c.z, d.x, d.y, d.z,
      ], 3));
      geometry.computeVertexNormals();
      const pitchMaterial = scene.preview
        ? new THREE.MeshBasicMaterial({
          color: stripe.index % 2 ? 0x216b3e : 0x1b5e36,
          side: THREE.DoubleSide, toneMapped: false,
        })
        : new THREE.MeshLambertMaterial({
          color: stripe.index % 2 ? rules.pitchColor : rules.pitchColor2,
          side: THREE.DoubleSide,
        });
      if (!scene.preview) lightingMaterials.pitch.add(pitchMaterial);
      g.add(new THREE.Mesh(geometry, pitchMaterial));
    }
    for (const segment of pitchLayout.lines) {
      const a = new THREE.Vector3(segment.from[0], 0.03, segment.from[1]);
      const b2 = new THREE.Vector3(segment.to[0], 0.03, segment.to[1]);
      const L = a.distanceTo(b2); const mm = new THREE.Mesh(new THREE.BoxGeometry(L, 0.02, 0.12), new THREE.MeshBasicMaterial({ color: 0xffffff }));
      mm.position.copy(a).lerp(b2, 0.5); mm.lookAt(b2); mm.rotateY(Math.PI / 2); g.add(mm);
    }
    const circ = new THREE.Mesh(new THREE.RingGeometry(9.03, 9.15, 64), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    circ.rotation.x = -Math.PI / 2;
    circ.position.set(pitchLayout.center[0], 0.03, pitchLayout.center[1]);
    g.add(circ);
    three.add(g);
  }

  /* ── Vertrag ─────────────────────────────────────────────────────── */
  const fwd = new THREE.Vector3();
  function project(xm, ym, zm) {
    const p = toWorld([xm, ym], zm || 0);
    const rel = p.clone().sub(camera.position);
    camera.getWorldDirection(fwd);
    const d = rel.dot(fwd);
    const ndc = p.project(camera);
    return { x: (ndc.x + 1) / 2 * W, y: (1 - ndc.y) / 2 * H, d, visible: d > preset.near };
  }
  function render() { renderer.render(three, camera); }
  let exposureMultiplier = Math.max(0.2, Number(exposure) || 1);
  function setExposure(value, shouldRender = true) {
    exposureMultiplier = Math.max(0.2, Number(value) || 1);
    renderer.toneMappingExposure =
      lightingPreset(lightingMode).exposure * exposureMultiplier;
    if (shouldRender) render();
    return renderer.toneMappingExposure;
  }
  function setLightingMode(mode, shouldRender = true) {
    lightingMode = mode === 'night' ? 'night' : 'day';
    const config = lightingPreset(lightingMode);
    renderer.setClearColor(config.background, 1);
    hemisphere.color.setHex(config.hemisphere.sky);
    hemisphere.groundColor.setHex(config.hemisphere.ground);
    hemisphere.intensity = config.hemisphere.intensity;
    ambient.color.setHex(config.ambient.color);
    ambient.intensity = config.ambient.intensity;
    keyLight.color.setHex(config.key.color);
    keyLight.intensity = config.key.intensity;
    keyLight.position.fromArray(config.key.position);
    fillLight.color.setHex(config.fill.color);
    fillLight.intensity = config.fill.intensity;
    fillLight.position.fromArray(config.fill.position);
    for (const material of lightingMaterials.buildings) {
      material.color.setHex(config.building);
    }
    for (const material of lightingMaterials.structures) {
      material.emissive.setHex(config.structureEmissive);
      material.emissiveIntensity = config.structureEmissiveIntensity;
    }
    for (const material of lightingMaterials.roofs) {
      material.emissive.setHex(config.roofEmissive);
      material.emissiveIntensity = config.roofEmissiveIntensity;
    }
    for (const material of lightingMaterials.pitch) {
      material.emissive.setHex(config.pitchEmissive);
      material.emissiveIntensity = config.pitchEmissiveIntensity;
    }
    if (skyMesh) {
      skyMesh.material.map = skyTextures[lightingMode];
      skyMesh.material.needsUpdate = true;
    }
    setExposure(exposureMultiplier, false);
    if (shouldRender) render();
    return lightingMode;
  }
  function seatAt(blockId, row, col) {           // Sitz für den Sitzblick: nächste Instanz zum gewünschten Raster
    let best = null, bd = 1e9;
    for (const sIx of seatIndex) { if (sIx.block !== blockId) continue; const d = Math.abs(sIx.row - row) + Math.abs(sIx.col - col); if (d < bd) { bd = d; best = sIx; } }
    return best;
  }
  let fpsAcc = 0, fpsN = 0, fpsCheck = 0;
  function adaptQuality(dt, now) {                // FPS-gesteuerte Pixelrate: Rückfall unter Leistungsgrenze, konkret
    fpsAcc += dt; fpsN++; if (now - fpsCheck < 2500) return;
    fpsCheck = now; const fps = fpsN / Math.max(1e-4, fpsAcc); fpsAcc = 0; fpsN = 0;
    const pr = renderer.getPixelRatio(), max = Math.min(2, window.devicePixelRatio || 1);
    if (fps < 40 && pr > 0.6) renderer.setPixelRatio(Math.max(0.6, pr - 0.2));
    else if (fps > 70 && pr < max) renderer.setPixelRatio(Math.min(max, pr + 0.2));
  }
  let floodlightsEnabled = false;
  function setFloodlights(enabled, shouldRender = true) {
    floodlightsEnabled = Boolean(enabled);
    for (const source of floodlightSources) {
      source.visible = floodlightsEnabled;
      source.intensity = floodlightsEnabled ? source.userData.onIntensity : 0;
    }
    floodlightFill.intensity =
      floodlightsEnabled && floodlightSources.length ? 0.2 : 0;
    for (const material of fixtureMaterials) {
      material.emissive.setHex(floodlightsEnabled ? 0xfff0b0 : 0x000000);
      material.emissiveIntensity = floodlightsEnabled ? 1.8 : 0;
      material.needsUpdate = true;
    }
    if (shouldRender) render();
    return floodlightsEnabled;
  }
  setLightingMode(lightingMode, false);
  setFloodlights(floodlight, false);
  function dispose() {
    active = false;
    const geometries = new Set();
    const materials = new Set();
    const textures = new Set();
    three.traverse(object => {
      if (object.geometry) geometries.add(object.geometry);
      const objectMaterials = Array.isArray(object.material)
        ? object.material : [object.material];
      for (const material of objectMaterials) {
        if (!material) continue;
        materials.add(material);
        if (material.map) textures.add(material.map);
      }
    });
    Object.values(skyTextures).forEach(texture => textures.add(texture));
    geometries.forEach(geometry => geometry.dispose());
    textures.forEach(texture => texture.dispose());
    materials.forEach(material => material.dispose());
    renderer.dispose();
  }

  return {
    project, render, dispose, camera, renderer, seatAt, adaptQuality,
    // Read-only study integration: adding source geometry does not change the
    // existing renderer's camera, lights or default editor behavior.
    sceneRoot: three, pitchMaterials: lightingMaterials.pitch,
    setFloodlights, setLightingMode, setExposure,
    backgroundReady() {
      const texture = skyTextures[lightingMode];
      return !texture ||
        Boolean(texture.image?.complete && texture.image?.naturalWidth);
    },
    stats: {
      blocks: drawn.length, blocksTotal: scene.blocks.length,
      seats: seatCount, seatPaletteCounts,
      pitchStripes: drawPitch ? 10 : 0,
      pitchLines: drawPitch ? 17 : 0,
      get sky() { return isSeat ? lightingMode : null; },
      get lightingMode() { return lightingMode; },
      get toneMappingExposure() { return renderer.toneMappingExposure; },
      roof: roofSegs.length, mainStand,
      rotationDeg: Math.round(phi * 180 / Math.PI),
      floodlightType: lightPlan.type,
      floodlightFixtures: lightPlan.fixtures.length,
      floodlightSources: lightPlan.sources.length,
      get floodlightEnabled() { return floodlightsEnabled; },
    },
  };
}
