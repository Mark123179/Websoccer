const ALLIANZ_SOURCE_SHA256 = '52c0d0916cc4e780bd9d3d4cc60363b134195125ce95cd7a34a87b2c4a48c0b3';
const ALLIANZ_ASSET_VERSION = '7bc8ec0fcf20c166';
const ALLIANZ_COVER_PATH_ID = '-2079065756245898804';

export function supportsAllianzPresentation(presentation, manifest) {
  return presentation?.clubFmiId === 915 &&
    manifest?.clubFmiId === 915 &&
    presentation?.sourceSha256 === ALLIANZ_SOURCE_SHA256 &&
    manifest?.sourceSha256 === ALLIANZ_SOURCE_SHA256 &&
    manifest?.assetVersion === ALLIANZ_ASSET_VERSION;
}

export function isConfirmedAllianzFacadeMaterial(entry, part) {
  if (entry?.name !== 'cover_1.003' || entry?.pathId !== ALLIANZ_COVER_PATH_ID ||
      part?.material !== 'view.006' || part?.texture != null ||
      !Array.isArray(entry.bounds) || entry.bounds.length !== 2) return false;
  const expected = [
    [-114.229, 36.8817, -129.998],
    [114.230, 52.1961, 129.998],
  ];
  return entry.bounds.every((point, side) => point.every((value, axis) =>
    Number.isFinite(value) && Math.abs(value - expected[side][axis]) < .02));
}

export function sourceMaterialFinish(materialName) {
  if (typeof materialName !== 'string') return null;
  if (/^st011_stfr\d/.test(materialName))
    return {role: 'steel-frame', roughness: .56, metalness: .24};
  if (/^st011_wall\d/.test(materialName))
    return {role: 'wall', roughness: .92, metalness: 0};
  return null;
}

export function splitFacadeTriangles(positions, indices, {
  minHeight = 36.8, maxHeight = 52.25, maxAbsNormalY = .97, minRadialFacing = .25,
} = {}) {
  const facade = [], remaining = [];
  for (let i = 0; i < indices.length; i += 3) {
    const ia = indices[i] * 3, ib = indices[i + 1] * 3, ic = indices[i + 2] * 3;
    const ax = positions[ia], ay = positions[ia + 1], az = positions[ia + 2];
    const abx = positions[ib] - ax, aby = positions[ib + 1] - ay, abz = positions[ib + 2] - az;
    const acx = positions[ic] - ax, acy = positions[ic + 1] - ay, acz = positions[ic + 2] - az;
    const nx = aby * acz - abz * acy;
    const ny = abz * acx - abx * acz;
    const nz = abx * acy - aby * acx;
    const normalLength = Math.hypot(nx, ny, nz);
    const cx = (ax + positions[ib] + positions[ic]) / 3;
    const cy = (ay + positions[ib + 1] + positions[ic + 1]) / 3;
    const cz = (az + positions[ib + 2] + positions[ic + 2]) / 3;
    const radialLength = Math.hypot(cx, cz);
    const outward = normalLength > 0 && radialLength > 0
      ? (nx * cx + nz * cz) / (normalLength * radialLength)
      : -1;
    const exteriorWall = cy >= minHeight && cy <= maxHeight &&
      normalLength > 0 && Math.abs(ny / normalLength) <= maxAbsNormalY &&
      outward >= minRadialFacing;
    (exteriorWall ? facade : remaining).push(indices[i], indices[i + 1], indices[i + 2]);
  }
  return {facadeIndices: facade, remainingIndices: remaining};
}

export function runtimeFixtureIntensity(fixture, allianz = false) {
  // Unity source intensities are not Three.js candela. Calibrate only the
  // confirmed Allianz runtime, retaining the original mount points and cones.
  const browserScale = allianz ? 64 : 8;
  return fixture.intensity * browserScale *
    Math.min(4, Math.sqrt(fixture.representedIds.length));
}

export function projectFacadeUv(positions, minHeight = 36.8, maxHeight = 52.2) {
  const uv = new Float32Array((positions.length / 3) * 2);
  for (let i = 0; i < positions.length; i += 3) {
    const angle = Math.atan2(positions[i + 2], positions[i]);
    uv[(i / 3) * 2] = (angle + Math.PI) / (2 * Math.PI);
    uv[(i / 3) * 2 + 1] = (positions[i + 1] - minHeight) / (maxHeight - minHeight);
  }
  return uv;
}

export function smoothstep(value) {
  const t = Math.max(0, Math.min(1, value));
  return t * t * (3 - 2 * t);
}

export function interpolate(from, to, progress) {
  return from + (to - from) * smoothstep(progress);
}

export function createTransitionController({
  initial,
  apply,
  onFrame = () => {},
  durationMs = 1500,
  reducedMotion = false,
  requestFrame = callback => requestAnimationFrame(callback),
  cancelFrame = handle => cancelAnimationFrame(handle),
  now = () => performance.now(),
}) {
  let current = {...initial};
  let frame = null;
  let disposed = false;
  let generation = 0;
  const commit = state => {
    apply({...state});
    onFrame({...state});
  };
  commit(current);

  const stopFrame = () => {
    if (frame !== null) cancelFrame(frame);
    frame = null;
  };

  const set = (next, {immediate = false} = {}) => {
    if (disposed) return;
    const target = {...current, ...next};
    if (Object.keys(target).every(key => target[key] === current[key])) return;
    stopFrame();
    const run = ++generation;
    const from = {...current};
    const instant = immediate || (typeof reducedMotion === 'function'
      ? reducedMotion()
      : reducedMotion);
    if (instant || durationMs <= 0) {
      current = target;
      commit(current);
      return;
    }
    const started = now();
    const tick = timestamp => {
      if (disposed || generation !== run) return;
      const progress = Math.max(0, Math.min(1, (timestamp - started) / durationMs));
      current = Object.fromEntries(Object.keys(target).map(key => [
        key,
        typeof target[key] === 'number' && typeof from[key] === 'number'
          ? interpolate(from[key], target[key], progress)
          : (progress >= 1 ? target[key] : from[key]),
      ]));
      commit(current);
      if (progress < 1) frame = requestFrame(tick);
      else frame = null;
    };
    frame = requestFrame(tick);
  };

  return {
    set,
    get current() { return {...current}; },
    dispose() {
      if (disposed) return;
      disposed = true;
      generation++;
      stopFrame();
    },
  };
}
