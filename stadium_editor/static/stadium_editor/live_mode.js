const SCHEMA = 'websoccer.stadium-live-scene';
const EPSILON = 1e-7;
const LIVE_MODE_ASSET_URL = new URL(import.meta.url);

function liveModeModuleUrl(path) {
  const url = new URL(path, LIVE_MODE_ASSET_URL);
  url.search = LIVE_MODE_ASSET_URL.search;
  return url.href;
}

const stageAdapterPromise = import(liveModeModuleUrl('./stadium_stage_adapter.js'));

export function bilinearPoint(quad, u, v) {
  const [frontLeft, frontRight, backRight, backLeft] = quad;
  const frontX = frontLeft[0] + (frontRight[0] - frontLeft[0]) * u;
  const frontY = frontLeft[1] + (frontRight[1] - frontLeft[1]) * u;
  const backX = backLeft[0] + (backRight[0] - backLeft[0]) * u;
  const backY = backLeft[1] + (backRight[1] - backLeft[1]) * u;
  return [frontX + (backX - frontX) * v, frontY + (backY - frontY) * v];
}

export function decodeRle(rle, expectedLength) {
  const values = [];
  for (const pair of rle) {
    if (!Array.isArray(pair) || pair.length !== 2) throw new Error('Ungültige RLE-Zelle.');
    const [count, colour] = pair;
    if (!Number.isInteger(count) || count < 1 || !Number.isInteger(colour)) {
      throw new Error('Ungültige RLE-Zelle.');
    }
    if (values.length + count > expectedLength) throw new Error('RLE ist zu lang.');
    for (let index = 0; index < count; index += 1) values.push(colour);
  }
  if (values.length !== expectedLength) throw new Error('RLE-Länge stimmt nicht mit dem Raster überein.');
  return values;
}

function assertPoint(point) {
  return Array.isArray(point) && point.length === 2 && point.every(Number.isFinite);
}

export function validateScene(scene) {
  if (!scene || scene.schema !== SCHEMA || scene.version !== 1) {
    throw new Error('Unbekanntes Live-Scene-Format.');
  }
  if (scene.units !== 'm' || scene.frame?.name !== 'pitch') {
    throw new Error('Die Stadion-Scene ist nicht pitch-zentriert.');
  }
  if (!Array.isArray(scene.palette) || !scene.palette.length || !Array.isArray(scene.blocks)) {
    throw new Error('Die Stadion-Scene ist unvollständig.');
  }
  for (const block of scene.blocks) {
    if (!Number.isInteger(block.rows) || block.rows < 1 ||
        !Number.isInteger(block.seats) || block.seats < 1 ||
        !Array.isArray(block.quad) || block.quad.length !== 4 ||
        !block.quad.every(assertPoint) ||
        !Number.isFinite(block.z0) || !Number.isFinite(block.z1) || block.z1 <= block.z0) {
      throw new Error(`Block ${block.id}: ungültige Geometrie.`);
    }
    block._colours = decodeRle(block.rle, block.rows * block.seats);
    if (block._colours.some(index => index < 0 || index >= scene.palette.length)) {
      throw new Error(`Block ${block.id}: unbekannte Farbe.`);
    }
  }
  const proceduralRoof = (
    scene.roof?.mode === 'procedural-ring' &&
    assertPoint(scene.roof.center) &&
    Number.isFinite(scene.roof.depth) && scene.roof.depth > 0 &&
    assertPoint(scene.roof.innerEnvelope) &&
    Array.isArray(scene.roof.excludedBlockIds)
  );
  const explicitRoof = (
    scene.roof?.mode === 'explicit' &&
    Array.isArray(scene.roof.segments) &&
    scene.roof.segments.every(segment =>
      typeof segment.id === 'string' &&
      Array.isArray(segment.quad) &&
      (segment.quad.length === 4 ||
       (scene.preview === true && scene.roof.ring &&
        segment.quad.length >= 4 && segment.quad.length <= 32)) &&
      segment.quad.every(assertPoint) &&
      Array.isArray(segment.heights) && segment.heights.length === segment.quad.length &&
      segment.heights.every(Number.isFinite)) &&
    (!scene.roof.ring || (
      Array.isArray(scene.roof.ring.outer) && scene.roof.ring.outer.length >= 4 &&
      scene.roof.ring.outer.every(assertPoint) &&
      Array.isArray(scene.roof.ring.inner) && scene.roof.ring.inner.length >= 4 &&
      scene.roof.ring.inner.every(assertPoint) &&
      Number.isFinite(scene.roof.ring.zInner) &&
      Number.isFinite(scene.roof.ring.zOuter) &&
      scene.roof.ring.zOuter > scene.roof.ring.zInner
    ))
  );
  if (!proceduralRoof && !explicitRoof) {
    throw new Error('Unbekannter Dachmodus.');
  }
  return scene;
}

export async function loadLiveScene(sceneUrl, fetchImpl = fetch) {
  const response = await fetchImpl(sceneUrl, {headers: {Accept: 'application/json'}});
  let payload;
  try {
    payload = await response.json();
  } catch (_error) {
    throw new Error('Die Stadion-Scene konnte nicht gelesen werden.');
  }
  if (!response.ok) throw new Error(payload.error || 'Die Stadion-Scene konnte nicht geladen werden.');
  return validateScene(payload);
}

function backMidpoint(block) {
  return [
    (block.quad[2][0] + block.quad[3][0]) / 2,
    (block.quad[2][1] + block.quad[3][1]) / 2,
  ];
}

function angleDistance(a, b) {
  return Math.abs(((a - b) + Math.PI * 3) % (Math.PI * 2) - Math.PI);
}

/*
 * Same deterministic radial-overlap rule as editor.js. The canonical live
 * quad is front-first, so its back edge (3 -> 2) corresponds to the editor's
 * historical outer edge (0 -> 1).
 */
export function proceduralRoofRing(blocks, center = [0, 0]) {
  const info = blocks.map(block => {
    const left = block.quad[3];
    const right = block.quad[2];
    const midpoint = backMidpoint(block);
    let lo = Math.atan2(left[1] - center[1], left[0] - center[0]);
    let hi = Math.atan2(right[1] - center[1], right[0] - center[0]);
    let width = (hi - lo + Math.PI * 3) % (Math.PI * 2) - Math.PI;
    if (width < 0) {
      [lo, hi] = [hi, lo];
      width = -width;
    }
    return {
      block, lo, width,
      radius: Math.hypot(midpoint[0] - center[0], midpoint[1] - center[1]),
    };
  });
  const outer = info.filter(candidate => !info.some(other => {
    if (other.block.id === candidate.block.id || other.radius <= candidate.radius + 2) return false;
    const candidateMid = candidate.lo + candidate.width / 2;
    const otherMid = other.lo + other.width / 2;
    return angleDistance(candidateMid, otherMid) <
      (candidate.width + other.width) / 2 * 0.6;
  }));
  return outer.map(value => value.block).sort((a, b) => {
    const pa = backMidpoint(a);
    const pb = backMidpoint(b);
    return Math.atan2(pa[1] - center[1], pa[0] - center[0]) -
      Math.atan2(pb[1] - center[1], pb[0] - center[0]);
  });
}

function stretchEdge(left, right, factor = 1.09) {
  const mx = (left[0] + right[0]) / 2;
  const my = (left[1] + right[1]) / 2;
  return [
    [mx + (left[0] - mx) * factor, my + (left[1] - my) * factor],
    [mx + (right[0] - mx) * factor, my + (right[1] - my) * factor],
  ];
}

function clampRoofInner(point, target, scene) {
  const dx = target[0] - point[0];
  const dy = target[1] - point[1];
  const length = Math.hypot(dx, dy) || 1;
  // Same sixth-power pitch envelope and six-metre clearance as editor.js.
  // In the canonical scene fieldC is the pitch-frame origin [0, 0]; the
  // outline-derived roof.center is only used to select the radial outer ring.
  const [innerA, innerB] = scene.roof.innerEnvelope;
  const angle = Math.atan2(point[1], point[0]);
  const fieldRadius = (
    (Math.abs(Math.cos(angle)) / innerA) ** 6 +
    (Math.abs(Math.sin(angle)) / innerB) ** 6
  ) ** (-1 / 6);
  const maxLength = Math.max(6, Math.hypot(point[0], point[1]) - fieldRadius - 6);
  const factor = Math.min(1, maxLength / length);
  return [point[0] + dx * factor, point[1] + dy * factor];
}

export function buildProceduralRoof(scene) {
  if (scene.roof?.mode === 'explicit') {
    return scene.roof.segments.map(segment => ({
      id: segment.id,
      points: segment.quad.map((point, index) => [
        point[0], point[1], segment.heights[index],
      ]),
    }));
  }
  if (scene.roof?.mode !== 'procedural-ring') return [];
  const excluded = new Set(scene.roof.excludedBlockIds);
  return proceduralRoofRing(scene.blocks, scene.roof.center)
    .filter(block => !excluded.has(block.id))
    .map(block => {
    const [outerLeft, outerRight] = stretchEdge(block.quad[3], block.quad[2]);
    const depth = scene.roof.depth;
    const innerLeftRaw = clampRoofInner(block.quad[3], [
      block.quad[3][0] + (block.quad[0][0] - block.quad[3][0]) * depth,
      block.quad[3][1] + (block.quad[0][1] - block.quad[3][1]) * depth,
    ], scene);
    const innerRightRaw = clampRoofInner(block.quad[2], [
      block.quad[2][0] + (block.quad[1][0] - block.quad[2][0]) * depth,
      block.quad[2][1] + (block.quad[1][1] - block.quad[2][1]) * depth,
    ], scene);
    const [innerLeft, innerRight] = stretchEdge(innerLeftRaw, innerRightRaw);
    const zOuter = block.z1 + 3;
    const zInner = block.z1 - (block.z1 - block.z0) * 0.3;
    return {
      id: block.id,
      points: [
        [outerLeft[0], outerLeft[1], zOuter],
        [outerRight[0], outerRight[1], zOuter],
        [innerRight[0], innerRight[1], zInner],
        [innerLeft[0], innerLeft[1], zInner],
      ],
    };
    });
}

function vectorSubtract(a, b) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function normalize(value) {
  const length = Math.hypot(...value) || 1;
  return value.map(item => item / length);
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function createProjector(width, height, camera) {
  const position = [
    Math.sin(camera.orbit) * camera.distance,
    -Math.cos(camera.orbit) * camera.distance,
    camera.height,
  ];
  const target = [0, 8, 7];
  const forward = normalize(vectorSubtract(target, position));
  const right = normalize(cross(forward, [0, 0, 1]));
  const up = normalize(cross(right, forward));
  const focal = Math.min(width, height) * camera.zoom;
  return point => {
    const relative = vectorSubtract(point, position);
    const depth = dot(relative, forward);
    if (depth <= 1) return null;
    return [
      width / 2 + dot(relative, right) * focal / depth,
      height * 0.54 - dot(relative, up) * focal / depth,
      depth,
    ];
  };
}

function polygonVisible(points, width, height) {
  if (points.some(point => !point)) return false;
  const xs = points.map(point => point[0]);
  const ys = points.map(point => point[1]);
  return Math.max(...xs) >= -2 && Math.min(...xs) <= width + 2 &&
    Math.max(...ys) >= -2 && Math.min(...ys) <= height + 2;
}

function drawPolygon(context, points, fill, stroke = null) {
  context.beginPath();
  points.forEach((point, index) => {
    if (index) context.lineTo(point[0], point[1]);
    else context.moveTo(point[0], point[1]);
  });
  context.closePath();
  context.fillStyle = fill;
  context.fill();
  if (stroke) {
    context.strokeStyle = stroke;
    context.stroke();
  }
}

function shade(hex, factor) {
  const clean = hex.replace('#', '');
  const value = parseInt(clean, 16);
  const channel = shift => Math.max(0, Math.min(255, Math.round(((value >> shift) & 255) * factor)));
  return `rgb(${channel(16)},${channel(8)},${channel(0)})`;
}

function pitchItem(scene) {
  const halfLength = scene.pitch.length / 2;
  const halfWidth = scene.pitch.width / 2;
  return {
    kind: 'pitch',
    depthPoint: [0, 0, 0],
    points: [
      [-halfLength, -halfWidth, 0],
      [halfLength, -halfWidth, 0],
      [halfLength, halfWidth, 0],
      [-halfLength, halfWidth, 0],
    ],
  };
}

function seatItems(scene) {
  const items = [];
  for (const block of scene.blocks) {
    for (let row = 0; row < block.rows; row += 1) {
      const v0 = row / block.rows;
      const v1 = (row + 1) / block.rows;
      const z0 = block.z0 + (block.z1 - block.z0) * v0;
      const z1 = block.z0 + (block.z1 - block.z0) * v1;
      for (let seat = 0; seat < block.seats; seat += 1) {
        const u0 = seat / block.seats;
        const u1 = (seat + 1) / block.seats;
        const frontLeft = bilinearPoint(block.quad, u0, v0);
        const frontRight = bilinearPoint(block.quad, u1, v0);
        const backRight = bilinearPoint(block.quad, u1, v1);
        const backLeft = bilinearPoint(block.quad, u0, v1);
        const points = [
          [...frontLeft, z0], [...frontRight, z0],
          [...backRight, z1], [...backLeft, z1],
        ];
        items.push({
          kind: 'seat',
          points,
          cullPoint: backMidpoint(block),
          colour: scene.palette[block._colours[row * block.seats + seat]],
          depthPoint: [
            (frontLeft[0] + backRight[0]) / 2,
            (frontLeft[1] + backRight[1]) / 2,
            (z0 + z1) / 2,
          ],
        });
      }
    }
  }
  return items;
}

export class StadiumLiveRenderer {
  constructor(canvas, scene) {
    this.canvas = canvas;
    this.context = canvas.getContext('2d', {alpha: false});
    this.scene = validateScene(scene);
    this.camera = {orbit: 0, distance: 155, height: 45, zoom: 1.3};
    this.items = [
      pitchItem(scene),
      ...buildProceduralRoof(scene).map(roof => ({
        kind: 'roof', points: roof.points,
        cullPoint: [
          (roof.points[0][0] + roof.points[1][0]) / 2,
          (roof.points[0][1] + roof.points[1][1]) / 2,
        ],
        depthPoint: roof.points.reduce((sum, point) =>
          sum.map((value, index) => value + point[index] / roof.points.length), [0, 0, 0]),
      })),
      ...seatItems(scene),
    ];
    this._bindCamera();
    this.render();
  }

  _bindCamera() {
    let drag = null;
    this.canvas.addEventListener('pointerdown', event => {
      drag = {x: event.clientX, orbit: this.camera.orbit};
      this.canvas.setPointerCapture(event.pointerId);
    });
    this.canvas.addEventListener('pointermove', event => {
      if (!drag) return;
      this.camera.orbit = drag.orbit + (event.clientX - drag.x) * 0.006;
      this.render();
    });
    this.canvas.addEventListener('pointerup', () => { drag = null; });
    this.canvas.addEventListener('wheel', event => {
      event.preventDefault();
      this.camera.zoom = Math.max(0.72, Math.min(2.25, this.camera.zoom * Math.exp(-event.deltaY * 0.001)));
      this.render();
    }, {passive: false});
    this.canvas.addEventListener('dblclick', () => {
      this.camera = {orbit: 0, distance: 155, height: 45, zoom: 1.3};
      this.render();
    });
    new ResizeObserver(() => this.render()).observe(this.canvas);
  }

  render() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, this.canvas.clientWidth);
    const height = Math.max(1, this.canvas.clientHeight);
    const pixelWidth = Math.round(width * ratio);
    const pixelHeight = Math.round(height * ratio);
    if (this.canvas.width !== pixelWidth || this.canvas.height !== pixelHeight) {
      this.canvas.width = pixelWidth;
      this.canvas.height = pixelHeight;
    }
    const context = this.context;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.fillStyle = '#03070c';
    context.fillRect(0, 0, width, height);
    const project = createProjector(width, height, this.camera);
    const cameraDirection = [
      Math.sin(this.camera.orbit),
      -Math.cos(this.camera.orbit),
    ];
    const visible = [];
    for (const item of this.items) {
      // The endpoint supplies the complete bowl. Visibility remains a
      // client concern: remove the stand directly behind the live camera.
      if (
        item.cullPoint &&
        item.cullPoint[0] * cameraDirection[0] +
          item.cullPoint[1] * cameraDirection[1] > EPSILON
      ) continue;
      const points = item.points.map(project);
      if (!polygonVisible(points, width, height)) continue;
      const center = project(item.depthPoint);
      if (center) visible.push({...item, screenPoints: points, depth: center[2]});
    }
    visible.sort((a, b) => b.depth - a.depth);
    context.lineWidth = 0.45;
    for (const item of visible) {
      if (item.kind === 'pitch') {
        drawPolygon(context, item.screenPoints, '#0d4326', 'rgba(235,255,245,.65)');
      } else if (item.kind === 'roof') {
        drawPolygon(context, item.screenPoints, 'rgba(26,58,68,.88)', 'rgba(34,230,255,.25)');
      } else {
        const heightShade = 0.78 + (item.depthPoint[2] / 80);
        drawPolygon(context, item.screenPoints, shade(item.colour, heightShade));
      }
    }
  }
}

export class StadiumCanvasErrorRenderer {
  constructor(canvas, error) {
    this.canvas = canvas;
    this.error = error;
    this.render();
    if (typeof ResizeObserver !== 'undefined') {
      this.observer = new ResizeObserver(() => this.render());
      this.observer.observe(canvas);
    }
  }

  render() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, this.canvas.clientWidth);
    const height = Math.max(1, this.canvas.clientHeight);
    this.canvas.width = Math.round(width * ratio);
    this.canvas.height = Math.round(height * ratio);
    const context = this.canvas.getContext('2d', {alpha: false});
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.fillStyle = '#03070c';
    context.fillRect(0, 0, width, height);
    context.strokeStyle = 'rgba(34,230,255,.18)';
    context.strokeRect(width * .15, height * .2, width * .7, height * .6);
    context.fillStyle = '#8ea2af';
    context.font = '600 12px system-ui, sans-serif';
    context.textAlign = 'center';
    context.fillText('STADIONANSICHT NICHT VERFÜGBAR', width / 2, height / 2 - 4);
    context.fillStyle = '#607481';
    context.font = '11px system-ui, sans-serif';
    context.fillText(this.error?.message || 'Die Live Scene konnte nicht geladen werden.',
      width / 2, height / 2 + 18);
  }
}

async function mount(stage) {
  const status = stage.querySelector('.live-stage__status');
  try {
    const {mountStadiumStage} = await stageAdapterPromise;
    const scene = await loadLiveScene(stage.dataset.sceneUrl);
    const canvas = stage.querySelector('canvas');
    const controls = {
      camera: stage.dataset.camera || 'orbit',
      day: stage.dataset.day === 'true',
      floodlight: stage.dataset.floodlight === 'true',
      exposure: Number(stage.dataset.exposure || 1),
    };
    const mounted = await mountStadiumStage({
      element: stage.querySelector('[data-stadium-stage]'), canvas, scene, ...controls,
      mode: stage.dataset.mode || 'live',
      fallback: fallbackCanvas => new StadiumLiveRenderer(fallbackCanvas, scene),
    });
    stage._stadiumStage = mounted;
    const camera = stage.querySelector('[data-stage-camera]');
    const day = stage.querySelector('[data-stage-day]');
    const floodlight = stage.querySelector('[data-stage-floodlight]');
    const exposure = stage.querySelector('[data-stage-exposure]');
    const updateCamera = () => {
      stage.dataset.camera = camera?.value || 'orbit';
      if (stage._stadiumStage?.kind === 'three') {
        stage._stadiumStage.update({
          camera: stage.dataset.camera,
        }).catch(() => {});
      }
    };
    const updateDay = () => {
      stage.dataset.day = String(Boolean(day?.checked));
      stage._stadiumStage?.update({
        day: Boolean(day?.checked),
      }).catch(() => {});
    };
    const updateFloodlight = () => {
      stage.dataset.floodlight = String(Boolean(floodlight?.checked));
      stage._stadiumStage?.update({
        floodlight: Boolean(floodlight?.checked),
      }).catch(() => {});
    };
    const updateExposure = () => {
      stage.dataset.exposure = exposure?.value || '1';
      stage._stadiumStage?.update({
        exposure: Number(stage.dataset.exposure),
      }).catch(() => {});
    };
    [[camera, updateCamera], [day, updateDay]].forEach(([control, handler]) => {
      if (control) control.addEventListener('input', handler);
    });
    floodlight?.addEventListener('input', updateFloodlight);
    exposure?.addEventListener('input', updateExposure);
    status.hidden = true;
  } catch (error) {
    stage.classList.add('stage-fallback');
    new StadiumCanvasErrorRenderer(stage.querySelector('canvas'), error);
    status.textContent = error.message;
    status.classList.add('is-error');
  }
}

if (typeof document !== 'undefined') {
  document.querySelectorAll('[data-stadium-live-mode]').forEach(mount);
}