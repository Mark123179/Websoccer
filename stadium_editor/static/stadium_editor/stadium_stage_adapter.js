/*
 * Shared adapter for the supplied stadium_stage.js black box.
 * Runtime consumers only pass canonical Live Scenes to this module.
 */
export const STADIUM_STAGE_CONFIG = Object.freeze({
  enabled: true,
  module: './stage/stadium_stage.js',
});

let stageModulePromise;
let threeModulePromise;

function loadStageModule() {
  if (!stageModulePromise) {
    stageModulePromise = import(STADIUM_STAGE_CONFIG.module).catch(error => {
      stageModulePromise = null;
      throw error;
    });
  }
  return stageModulePromise;
}

function loadThreeModule() {
  if (!threeModulePromise) {
    threeModulePromise = import('three').catch(error => {
      threeModulePromise = null;
      throw error;
    });
  }
  return threeModulePromise;
}

export function sceneRotationQuarterTurn(scene) {
  const main = scene.mainStand || 'SUED';
  const points = scene.blocks
    .filter(block => block.stand === main)
    .flatMap(block => block.quad);
  if (!points.length) return 0;
  const center = points.reduce(
    (sum, point) => [sum[0] + point[0] / points.length,
      sum[1] + point[1] / points.length],
    [0, 0],
  );
  const theta = Math.atan2(center[1], center[0]);
  const phi = Math.PI / 2 - theta;
  return Math.round(phi / (Math.PI / 2)) * (Math.PI / 2);
}

export function alignPitchStripeMeshes(THREE, pitchGroup, phi) {
  const stripes = pitchGroup.children.slice(0, 10);
  const stripeGroup = new THREE.Group();
  stripes.forEach(stripe => {
    pitchGroup.remove(stripe);
    stripeGroup.add(stripe);
  });
  stripeGroup.rotation.y = phi;
  pitchGroup.add(stripeGroup);
  return stripeGroup;
}

function withPitchRotation(THREE, scene, factory) {
  const phi = sceneRotationQuarterTurn(scene);
  if (Math.abs(phi) < 1e-7) return factory();
  const originalAdd = THREE.Scene.prototype.add;
  THREE.Scene.prototype.add = function addWithAlignedPitch(...objects) {
    objects.forEach(object => {
      const children = object?.isGroup ? object.children : [];
      const pitchStripes = children.length >= 10 &&
        children.slice(0, 10).every(child => child.geometry?.type === 'PlaneGeometry');
      if (pitchStripes) alignPitchStripeMeshes(THREE, object, phi);
    });
    return originalAdd.apply(this, objects);
  };
  try {
    return factory();
  } finally {
    THREE.Scene.prototype.add = originalAdd;
  }
}

function webglAvailable() {
  try {
    const canvas = document.createElement('canvas');
    return Boolean(window.WebGLRenderingContext &&
      (canvas.getContext('webgl2') || canvas.getContext('webgl')));
  } catch (_error) {
    return false;
  }
}

function rle(values) {
  const runs = [];
  values.forEach(value => {
    const last = runs[runs.length - 1];
    if (last && last[1] === value) last[0] += 1;
    else runs.push([1, value]);
  });
  return runs;
}

function editorRowRunsRightToLeft(block, geometry) {
  const center = geometry?.meta?.fieldC || [0, 0];
  const theta = Number(geometry?.meta?.axisTheta) || 0;
  const ct = Math.cos(theta);
  const st = Math.sin(theta);
  const transformed = block.quad.map(point => {
    const dx = point[0] - center[0];
    const dy = point[1] - center[1];
    return [dx * ct + dy * st, -dx * st + dy * ct];
  });
  const centroid = transformed.reduce(
    (sum, point) => [sum[0] + point[0] / 4, sum[1] + point[1] / 4], [0, 0],
  );
  const radius = Math.hypot(...centroid) || 1;
  const left = [-centroid[1] / radius, centroid[0] / radius];
  const lateral = index => transformed[index][0] * left[0] +
    transformed[index][1] * left[1];
  return lateral(3) < lateral(2);
}

export function applyEditorDesign(scene, blocks, seatData, palette, geometry = null) {
  const next = structuredClone(scene);
  const colours = palette.map(item => Array.isArray(item) ? item[0] : item);
  if (colours.length) next.palette = colours;
  const sourceById = new Map(
    (blocks || []).map((block, index) => [String(block.id), {block, index}]),
  );
  next.blocks.forEach(target => {
    const source = sourceById.get(String(target.id));
    const values = source && seatData?.[source.index];
    if (!values || values.length !== target.rows * target.seats) return;
    let canonical = Array.from(values);
    if (geometry && editorRowRunsRightToLeft(source.block, geometry)) {
      canonical = Array.from({length: target.rows}, (_unused, row) =>
        canonical.slice(row * target.seats, (row + 1) * target.seats).reverse()
      ).flat();
    }
    target.rle = rle(canonical);
  });
  return next;
}

function midpoint(block) {
  return [
    (block.quad[2][0] + block.quad[3][0]) / 2,
    (block.quad[2][1] + block.quad[3][1]) / 2,
  ];
}

function angleDistance(left, right) {
  return Math.abs(((left - right) + Math.PI * 3) % (Math.PI * 2) - Math.PI);
}

function proceduralRoofSegments(scene) {
  if (scene.roof?.mode !== 'procedural-ring') return [];
  const center = scene.roof.center || [0, 0];
  const excluded = new Set(scene.roof.excludedBlockIds || []);
  const info = scene.blocks.map(block => {
    let lo = Math.atan2(block.quad[3][1] - center[1], block.quad[3][0] - center[0]);
    let hi = Math.atan2(block.quad[2][1] - center[1], block.quad[2][0] - center[0]);
    let width = (hi - lo + Math.PI * 3) % (Math.PI * 2) - Math.PI;
    if (width < 0) {
      [lo, hi] = [hi, lo];
      width = -width;
    }
    const mid = midpoint(block);
    return {block, lo, width, radius: Math.hypot(mid[0] - center[0], mid[1] - center[1])};
  });
  const outer = info.filter(candidate => !info.some(other => {
    if (other.block.id === candidate.block.id || other.radius <= candidate.radius + 2) return false;
    return angleDistance(
      candidate.lo + candidate.width / 2, other.lo + other.width / 2,
    ) < (candidate.width + other.width) / 2 * .6;
  }));
  const stretch = (left, right, factor = 1.09) => {
    const mx = (left[0] + right[0]) / 2;
    const my = (left[1] + right[1]) / 2;
    return [
      [mx + (left[0] - mx) * factor, my + (left[1] - my) * factor],
      [mx + (right[0] - mx) * factor, my + (right[1] - my) * factor],
    ];
  };
  const clampInner = (point, target) => {
    const dx = target[0] - point[0];
    const dy = target[1] - point[1];
    const length = Math.hypot(dx, dy) || 1;
    const [innerA, innerB] = scene.roof.innerEnvelope;
    const angle = Math.atan2(point[1], point[0]);
    const pitchRadius = (
      (Math.abs(Math.cos(angle)) / innerA) ** 6 +
      (Math.abs(Math.sin(angle)) / innerB) ** 6
    ) ** (-1 / 6);
    const maximum = Math.max(6, Math.hypot(...point) - pitchRadius - 6);
    const factor = Math.min(1, maximum / length);
    return [point[0] + dx * factor, point[1] + dy * factor];
  };
  return outer.filter(item => !excluded.has(item.block.id)).map(item => {
    const block = item.block;
    const [outerLeft, outerRight] = stretch(block.quad[3], block.quad[2]);
    const depth = scene.roof.depth;
    const innerLeftRaw = clampInner(block.quad[3], [
      block.quad[3][0] + (block.quad[0][0] - block.quad[3][0]) * depth,
      block.quad[3][1] + (block.quad[0][1] - block.quad[3][1]) * depth,
    ]);
    const innerRightRaw = clampInner(block.quad[2], [
      block.quad[2][0] + (block.quad[1][0] - block.quad[2][0]) * depth,
      block.quad[2][1] + (block.quad[1][1] - block.quad[2][1]) * depth,
    ]);
    const [innerLeft, innerRight] = stretch(innerLeftRaw, innerRightRaw);
    const outerHeight = block.z1 + 3;
    const innerHeight = block.z1 - (block.z1 - block.z0) * .3;
    return {
      id: `procedural-${block.id}`,
      quad: [outerLeft, outerRight, innerRight, innerLeft],
      heights: [outerHeight, outerHeight, innerHeight, innerHeight],
    };
  });
}

function blackboxScene(scene) {
  if (scene.roof?.mode !== 'procedural-ring') return scene;
  const result = structuredClone(scene);
  result.roof = {mode: 'explicit', segments: proceduralRoofSegments(scene)};
  return result;
}

function createCanvas(element) {
  const canvas = document.createElement('canvas');
  canvas.className = 'stadium-stage__webgl';
  canvas.setAttribute('aria-hidden', 'true');
  element.replaceChildren(canvas);
  return canvas;
}

function dimensions(element) {
  const rect = element.getBoundingClientRect();
  return {
    width: Math.max(1, Math.round(rect.width || element.clientWidth || 960)),
    height: Math.max(1, Math.round(rect.height || element.clientHeight || 540)),
  };
}

function cameraName(value) {
  return ['match', 'orbit', 'seat'].includes(value) ? value : 'orbit';
}

export async function mountStadiumStage({
  element, canvas: fallbackCanvas, scene, fallback, mode = 'live',
  camera = 'orbit', day = false, exposure = 1, onReady,
} = {}) {
  let fallbackRenderer = null;
  let stage = null;
  let resizeTimer = 0;
  let disposed = false;
  let rebuilding = Promise.resolve();
  const state = {
    scene,
    camera: cameraName(camera),
    day: Boolean(day),
    exposure: Number(exposure) || 1,
    orbit: {azimuth: 40, elevation: 32, distance: 0, fov: 38, targetZ: 8},
  };

  const showFallback = reason => {
    element?.parentElement?.classList.remove('stage-three', 'stage-three-ready');
    element?.replaceChildren();
    if (element) delete element.stadiumProject;
    if (typeof fallback === 'function' && fallbackCanvas && !fallbackRenderer) {
      fallbackRenderer = fallback(fallbackCanvas, scene, reason);
    }
    return {kind: 'canvas', renderer: fallbackRenderer, reason};
  };

  if (!STADIUM_STAGE_CONFIG.enabled || !element || !scene || !webglAvailable()) {
    return showFallback(new Error('WebGL-Stadionbühne ist nicht verfügbar.'));
  }

  try {
    const [mod, THREE] = await Promise.all([loadStageModule(), loadThreeModule()]);
    if (typeof mod.createStadiumStage !== 'function') {
      throw new Error('Stadium stage API fehlt.');
    }

    const build = async () => {
      if (disposed) return;
      const oldStage = stage;
      const webglCanvas = createCanvas(element);
      const size = dimensions(element);
      const options = {
        canvas: webglCanvas,
        scene: blackboxScene(state.scene),
        ...size,
        drawPitch: true,
        view: state.camera,
        orbit: state.orbit,
        lighting: state.day ? 'day' : 'night',
      };
      stage = withPitchRotation(
        THREE, options.scene, () => mod.createStadiumStage(options),
      );
      if (state.camera === 'seat' && !options.seat) {
        const block = options.scene.blocks?.[0];
        const seat = block && stage.seatAt(
          block.id, Math.floor(block.rows / 2), Math.floor(block.seats / 2),
        );
        if (seat) {
          stage.dispose();
          stage = withPitchRotation(
            THREE, options.scene, () => mod.createStadiumStage({...options, seat}),
          );
        }
      }
      if (stage.renderer) stage.renderer.toneMappingExposure = state.exposure;
      stage.render();
      oldStage?.dispose();
      element.parentElement?.classList.add('stage-three');
      element.stadiumProject = (...point) => stage.project(...point);
      element.dispatchEvent(new CustomEvent('stadiumstage:ready', {
        detail: {project: element.stadiumProject, mode},
      }));
    };

    const rebuild = patch => {
      const nextOrbit = patch.orbit ? {...state.orbit, ...patch.orbit} : state.orbit;
      Object.assign(state, patch);
      state.orbit = nextOrbit;
      rebuilding = rebuilding.then(build).catch(error => {
        showFallback(error);
        throw error;
      });
      return rebuilding;
    };

    await build();

    let drag = null;
    element.addEventListener('pointerdown', event => {
      if (state.camera !== 'orbit') return;
      drag = {x: event.clientX, y: event.clientY,
        azimuth: state.orbit.azimuth, elevation: state.orbit.elevation};
      element.setPointerCapture(event.pointerId);
    });
    element.addEventListener('pointermove', event => {
      if (!drag || !stage?.camera) return;
      state.orbit.azimuth = drag.azimuth + (event.clientX - drag.x) * .25;
      state.orbit.elevation = Math.max(8, Math.min(
        78, drag.elevation - (event.clientY - drag.y) * .18,
      ));
      const targetY = state.orbit.targetZ;
      const radius = Math.hypot(
        stage.camera.position.x,
        stage.camera.position.y - targetY,
        stage.camera.position.z,
      );
      const azimuth = state.orbit.azimuth * Math.PI / 180;
      const elevation = state.orbit.elevation * Math.PI / 180;
      stage.camera.position.set(
        Math.sin(azimuth) * Math.cos(elevation) * radius,
        Math.sin(elevation) * radius + state.orbit.targetZ,
        Math.cos(azimuth) * Math.cos(elevation) * radius,
      );
      stage.camera.lookAt(0, state.orbit.targetZ, 0);
      stage.render();
    });
    element.addEventListener('pointerup', () => { drag = null; });
    element.addEventListener('wheel', event => {
      if (state.camera !== 'orbit' || !stage?.camera) return;
      event.preventDefault();
      state.orbit.fov = Math.max(24, Math.min(
        72, state.orbit.fov * Math.exp(event.deltaY * .001),
      ));
      clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => rebuild({}).catch(() => {}), 80);
    }, {passive: false});
    element.addEventListener('dblclick', () => {
      state.orbit = {azimuth: 40, elevation: 32, distance: 0, fov: 38, targetZ: 8};
      rebuild({}).catch(() => {});
    });

    const observer = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => rebuild({}).catch(() => {}), 120);
    });
    observer.observe(element);

    const api = {
      kind: 'three',
      get stage() { return stage; },
      update(next = {}) {
        const patch = {...next};
        if ('floodlight' in patch && !('day' in patch)) patch.day = !patch.floodlight;
        if ('camera' in patch) patch.camera = cameraName(patch.camera);
        const onlyExposure = Object.keys(patch).every(key => key === 'exposure');
        if (onlyExposure && stage?.renderer) {
          state.exposure = Number(patch.exposure) || 1;
          stage.renderer.toneMappingExposure = state.exposure;
          stage.render();
          return Promise.resolve();
        }
        return rebuild(patch);
      },
      project(...point) { return stage?.project(...point); },
      dispose() {
        disposed = true;
        clearTimeout(resizeTimer);
        observer.disconnect();
        stage?.dispose();
        element.replaceChildren();
      },
    };
    if (typeof onReady === 'function') onReady(api);
    return api;
  } catch (error) {
    return showFallback(error);
  }
}

export {loadStageModule};