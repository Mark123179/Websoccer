// Optional, source-declared terrain only. Coordinates of the cutout are model x,z.
import {validateElevationGrid} from './measured_ground.js?v=1';
const EPS = 1e-8;
const cross = (a, b, c) =>
  (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const onSegment = (a, b, p) => Math.abs(cross(a, b, p)) <= EPS &&
  p[0] >= Math.min(a[0], b[0]) - EPS && p[0] <= Math.max(a[0], b[0]) + EPS &&
  p[1] >= Math.min(a[1], b[1]) - EPS && p[1] <= Math.max(a[1], b[1]) + EPS;
const edges = polygon => polygon.map((p, i) => [p, polygon[(i + 1) % polygon.length]]);
const intersects = (a, b, c, d) =>
  (cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0) ||
  onSegment(a, b, c) || onSegment(a, b, d) || onSegment(c, d, a) || onSegment(c, d, b);

function pointInEdges(p, lines) {
  let inside = false;
  for (const [a, b] of lines) {
    if (onSegment(a, b, p)) return true;
    if ((a[1] > p[1]) !== (b[1] > p[1]) &&
        p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0])
      inside = !inside;
  }
  return inside;
}

export function pointInGroundCutout(p, polygon) {
  return pointInEdges(p, edges(polygon));
}

export function validateSurroundingsGround(data = {}) {
  const elevation = Object.hasOwn(data, 'groundElevation') ?
    validateElevationGrid(data.groundElevation) : null;
  const hasLevel = Object.hasOwn(data, 'groundLevel');
  const hasCutout = Object.hasOwn(data, 'groundCutout');
  if (elevation && (!hasLevel || !hasCutout))
    throw new Error('groundElevation benötigt groundLevel und groundCutout.');
  if (!hasLevel && !hasCutout) return {level: 0, cutout: null};
  if (!hasLevel || typeof data.groundLevel !== 'number' ||
      !Number.isFinite(data.groundLevel) || Math.abs(data.groundLevel) > 30)
    throw new Error('groundLevel benötigt eine endliche Höhe zwischen −30 und 30 Metern.');
  if (!hasCutout) {
    if (data.groundLevel !== 0)
      throw new Error('Eine veränderte groundLevel benötigt eine groundCutout-Aussparung.');
    return {level: 0, cutout: null};
  }
  const raw = data.groundCutout;
  if (!Array.isArray(raw) || raw.length < 3 || raw.length > 257 ||
      raw.some(p => !Array.isArray(p) || p.length !== 2 ||
        p.some(n => typeof n !== 'number' || !Number.isFinite(n) || Math.abs(n) > 10000)))
    throw new Error('groundCutout benötigt 3–256 endliche Modellpunkte (x,z).');
  const cutout = raw.map(p => [...p]);
  if (cutout.length > 1 && cutout[0].every((v, i) => v === cutout.at(-1)[i]))
    cutout.pop();
  if (cutout.length < 3 || cutout.length > 256 ||
      new Set(cutout.map(p => JSON.stringify(p))).size !== cutout.length)
    throw new Error('groundCutout enthält doppelte oder zu wenige Punkte.');
  const lines = edges(cutout);
  for (let i = 0; i < lines.length; i++) {
    const [a, b] = lines[i], c = cutout[(i + 2) % cutout.length];
    if (Math.abs(cross(a, b, c)) <= EPS &&
        (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0)
      throw new Error('groundCutout enthält eine rücklaufende Kante.');
    for (let j = i + 1; j < lines.length; j++) {
      if (j === i + 1 || (i === 0 && j === lines.length - 1)) continue;
      if (intersects(...lines[i], ...lines[j]))
        throw new Error('groundCutout enthält eine Selbstüberschneidung.');
    }
  }
  if (Math.abs(lines.reduce((sum, [a, b]) => sum + a[0] * b[1] - b[0] * a[1], 0)) <= EPS)
    throw new Error('groundCutout besitzt keine Fläche.');
  return {level: data.groundLevel, cutout, ...(elevation ? {elevation} : {})};
}

// Fail closed for crossings, including edges crossing with every vertex outside,
// or a surrounding polygon enclosing the entire hole. No source data are erased.
function polygonRelation(points, cutout, cutoutEdges) {
  if (!cutout) return 'outside';
  const lines = edges(points);
  const hits = points.map(p => pointInEdges(p, cutoutEdges));
  const crossing = lines.some(([a, b]) =>
    cutoutEdges.some(([c, d]) => intersects(a, b, c, d)));
  if (crossing) return 'overlap';
  if (hits.every(Boolean)) return 'inside';
  if (hits.some(Boolean) || cutout.some(p => pointInEdges(p, lines)))
    return 'overlap';
  return 'outside';
}

export function groundPolygonRelation(points, cutout) {
  return polygonRelation(points, cutout, cutout ? edges(cutout) : []);
}

// Cache only the already validated, source-declared cutout's edges. All boundary,
// winding and EPS decisions remain in the same functions used by public checks.
export function createGroundCutoutChecks(cutout) {
  const lines = cutout ? edges(cutout) : [];
  return {
    pointInside: p => !!cutout && pointInEdges(p, lines),
    polygonRelation: points => polygonRelation(points, cutout, lines),
  };
}
