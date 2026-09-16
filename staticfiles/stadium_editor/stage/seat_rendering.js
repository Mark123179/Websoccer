function vector(from, to) {
  return [to[0] - from[0], to[1] - from[1], to[2] - from[2]];
}

function midpoint(left, right) {
  return [
    (left[0] + right[0]) / 2,
    (left[1] + right[1]) / 2,
    (left[2] + right[2]) / 2,
  ];
}

function normalized(value) {
  const length = Math.hypot(...value);
  if (!Number.isFinite(length) || length <= 1e-9) {
    throw new Error('Sitzbasis enthält eine Kante ohne Länge.');
  }
  return value.map(component => component / length);
}

function cross(left, right) {
  return [
    left[1] * right[2] - left[2] * right[1],
    left[2] * right[0] - left[0] * right[2],
    left[0] * right[1] - left[1] * right[0],
  ];
}

export function decodeSeatRle(rle, total, paletteSize, maxRuns = 10_000) {
  if (!Array.isArray(rle) || rle.length > maxRuns ||
      !Number.isInteger(total) || total < 1 ||
      !Number.isInteger(paletteSize) || paletteSize < 1 || paletteSize > 256) {
    throw new Error('Ungültige Sitzfolge.');
  }
  const values = new Uint8Array(total);
  let cursor = 0;
  for (const pair of rle) {
    if (!Array.isArray(pair) || pair.length !== 2 ||
        !Number.isInteger(pair[0]) || pair[0] < 1 || pair[0] > 65_535 ||
        !Number.isInteger(pair[1]) || pair[1] < 0 || pair[1] >= paletteSize ||
        cursor + pair[0] > total) {
      throw new Error('Ungültige Sitzfolge.');
    }
    values.fill(pair[1], cursor, cursor + pair[0]);
    cursor += pair[0];
  }
  if (cursor !== total) throw new Error('Ungültige Sitzfolge.');
  return values;
}

export function buildSeatRenderPlan({
  width, depth, rowPitch, seatPitch, rows, seats, rle, paletteSize,
}) {
  if (![width, depth, rowPitch, seatPitch].every(
    value => Number.isFinite(value) && value > 0
  ) || !Number.isInteger(rows) || rows < 1 ||
      !Number.isInteger(seats) || seats < 1) {
    throw new Error('Ungültiges Sitzraster.');
  }
  const renderRows = Math.max(1, Math.round(depth / rowPitch));
  const renderCols = Math.max(1, Math.round(width / seatPitch));
  const source = decodeSeatRle(rle, rows * seats, paletteSize);
  const colours = new Uint8Array(renderRows * renderCols);
  for (let row = 0; row < renderRows; row++) {
    const sourceRow = Math.min(rows - 1, Math.floor((row + .5) / renderRows * rows));
    for (let col = 0; col < renderCols; col++) {
      const sourceCol = Math.min(seats - 1, Math.floor((col + .5) / renderCols * seats));
      colours[row * renderCols + col] = source[sourceRow * seats + sourceCol];
    }
  }
  return {rows: renderRows, cols: renderCols, count: colours.length, colours};
}

export function seatBasis(frontLeft, frontRight, backLeft, backRight) {
  let right = normalized(vector(frontLeft, frontRight));
  const back = normalized(vector(
    midpoint(frontLeft, frontRight),
    midpoint(backLeft, backRight),
  ));
  let up = normalized(cross(back, right));
  if (up[1] < 0) {
    right = right.map(value => -value);
    up = normalized(cross(back, right));
  }
  return {right, up, back};
}