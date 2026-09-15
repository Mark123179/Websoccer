const PITCH = {length: 105, width: 68};

const midpoint = (left, right) => [
  (left[0] + right[0]) / 2,
  (left[1] + right[1]) / 2,
];

function pitchDistance(point) {
  const dx = Math.max(Math.abs(point[0]) - PITCH.length / 2, 0);
  const dy = Math.max(Math.abs(point[1]) - PITCH.width / 2, 0);
  return Math.hypot(dx, dy);
}

function orientedCorners(quad) {
  const first = [quad[0], quad[1]];
  const second = [quad[2], quad[3]];
  const d1 = pitchDistance(midpoint(...first));
  const d2 = pitchDistance(midpoint(...second));
  let front = d1 <= d2 ? first : second;
  let back = d1 <= d2 ? second : first;
  const frontMid = midpoint(...front);
  const backMid = midpoint(...back);
  const normal = [backMid[0] - frontMid[0], backMid[1] - frontMid[1]];
  const left = [-normal[1], normal[0]];
  const dot = point => point[0] * left[0] + point[1] * left[1];
  if (dot(front[0]) < dot(front[1])) front = [front[1], front[0]];
  if (dot(back[0]) < dot(back[1])) back = [back[1], back[0]];
  return {A: front[0], B: front[1], C: back[1], D: back[0]};
}

const lerp = (left, right, amount) => [
  left[0] + (right[0] - left[0]) * amount,
  left[1] + (right[1] - left[1]) * amount,
];

export function blockSupportQuads(block) {
  const {A, B, C, D} = orientedCorners(block.quad);
  const wallBase = Number.isFinite(Number(block.wallBaseZ))
    ? Math.min(Number(block.z0), Number(block.wallBaseZ))
    : 0;
  const point = (u, v, z) => [...lerp(lerp(A, B, u), lerp(D, C, u), v), z];
  return {
    wallBase,
    underside: wallBase > 0 ? [
      point(0, 0, block.z0), point(1, 0, block.z0),
      point(1, 1, wallBase), point(0, 1, wallBase),
    ] : null,
    sideWalls: [0, 1].map(side => [
      point(side, 0, block.z0), point(side, 1, block.z1),
      point(side, 1, wallBase), point(side, 0, wallBase),
    ]),
  };
}