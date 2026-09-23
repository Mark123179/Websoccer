// Pure geometry/capacity model. Source positions are never mutated.
export const ORDER = ['back', 'right', 'front', 'left'];
export const LABELS = {back: 'Rücktribüne', front: 'Vordertribüne',
  left: 'Linke Tribüne', right: 'Rechte Tribüne'};

const clamp = (value, a, b) => Math.max(a, Math.min(b, value));

export function countState(data, steps) {
  const rows = {};
  let added = 0;
  for (const side of ORDER) {
    const source = data.sides[side];
    const count = steps[side] || 0;
    if (!Number.isInteger(count) || count < 0 ||
        count * source.rowsPerStep > source.maxRows) {
      throw new RangeError(`Ausbaustufe für ${side} außerhalb der gemessenen Grenze`);
    }
    rows[side] = count * source.rowsPerStep;
    added += rows[side] * source.template.length;
  }
  const total = data.baselineSeats + added;
  if (total > data.limit) throw new RangeError('120.000 Sitzplätze überschritten');
  return {rows, added, total};
}

export function nextStep(data, steps, side) {
  const next = {...steps, [side]: (steps[side] || 0) + 1};
  try {
    const result = countState(data, next);
    return {steps: next, count: result};
  } catch (error) {
    if (!(error instanceof RangeError)) throw error;
    return {steps, reason: error.message};
  }
}

// The same continuous displacement field is evaluated for each original
// vertex. At a corner, both adjacent sides act on the *same* source vertex,
// so separate roof triangles and their mating structure cannot open a seam.
export function warpPoint(point, data, rows, result = [0, 0, 0]) {
  const x = point[0], y = point[1], z = point[2];
  const vertical = clamp((y - 8) / 26, 0, 1);
  let dx = 0, dz = 0, rise = 0, weight = 0;
  for (const side of ORDER) {
    const rowCount = rows[side];
    if (!rowCount) continue;
    const section = data.sides[side];
    const radial = section.sign * (section.axis === 0 ? x : z);
    const band = Math.max(8, rowCount * data.rowDepth);
    const influence = clamp((radial - section.seatExtent + band) / band, 0, 1);
    if (!influence) continue;
    const outward = section.sign * rowCount * data.rowDepth * influence * vertical;
    if (section.axis === 0) dx += outward;
    else dz += outward;
    rise += rowCount * data.rowRise * influence;
    weight += influence;
  }
  result[0] = x + dx;
  result[1] = y + vertical * rise / Math.max(1, weight);
  result[2] = z + dz;
  return result;
}

export function warpPositions(source, data, rows, target) {
  const point = [0, 0, 0], moved = [0, 0, 0];
  for (let i = 0; i < source.length; i += 3) {
    point[0] = source[i]; point[1] = source[i + 1]; point[2] = source[i + 2];
    warpPoint(point, data, rows, moved);
    target[i] = moved[0]; target[i + 1] = moved[1]; target[i + 2] = moved[2];
  }
  return target;
}

// The repeating chair positions, including gaps between source sections and
// aisles, come exclusively from measured top rows, not a rectangular grid.
export function addedChairPositions(data, rows, side) {
  const info = data.sides[side], result = [];
  for (let row = 0; row < rows[side]; row++) {
    for (const template of info.template) {
      const p = [...template.position];
      // The source template is already occupied: start outside that row.
      p[info.axis] += info.sign * data.rowDepth * (row + 1);
      p[1] += data.rowRise * (row + 1);
      result.push({position: p, rotation: template.rotation,
        color: template.color});
    }
  }
  return result;
}

// Connect each new row to its measured original section edge. Each strip
// follows the original seat spacing and leaves actual source aisles unbridged.
export function terraceTriangles(data, rows, side) {
  const info = data.sides[side], across = info.axis === 0 ? 2 : 0;
  const vertices = [], sections = new Map();
  for (const seat of info.template) {
    if (!sections.has(seat.section)) sections.set(seat.section, []);
    sections.get(seat.section).push(seat.position);
  }
  for (const seats of sections.values()) {
    seats.sort((a, b) => a[across] - b[across]);
    for (let i = 1; i < seats.length; i++) {
      const a = seats[i - 1], b = seats[i];
      if (Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) > 1.2) continue;
      const shifted = (p, row) => {
        const result = [...p];
        result[info.axis] += info.sign * data.rowDepth * row;
        result[1] += data.rowRise * row - .32;
        return result;
      };
      for (let row = 1; row <= rows[side]; row++) {
        const innerA = shifted(a, row - 1), innerB = shifted(b, row - 1);
        const outerA = shifted(a, row), outerB = shifted(b, row);
        vertices.push(...innerA, ...outerA, ...innerB,
                      ...outerA, ...outerB, ...innerB);
      }
    }
  }
  return vertices;
}