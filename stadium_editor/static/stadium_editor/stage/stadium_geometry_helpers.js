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

function pointSegmentDistance(point, left, right) {
  const dx = right[0] - left[0];
  const dy = right[1] - left[1];
  const lengthSq = dx * dx + dy * dy || 1;
  const amount = Math.max(0, Math.min(1,
    ((point[0] - left[0]) * dx + (point[1] - left[1]) * dy) / lengthSq,
  ));
  return Math.hypot(
    point[0] - (left[0] + dx * amount),
    point[1] - (left[1] + dy * amount),
  );
}

export function facadeEdgeTopHeights(edge, blocks, margin = 2.5) {
  const samples = blocks
    .filter(block => Array.isArray(block.quad) && block.quad.length === 4)
    .map(block => {
      const {C, D} = orientedCorners(block.quad);
      return {left: D, right: C, height: Number(block.z1) + margin};
    })
    .filter(sample => Number.isFinite(sample.height));
  return edge.map(point => {
    if (!samples.length) return margin;
    const distances = samples.map(sample => ({
      sample,
      distance: pointSegmentDistance(point, sample.left, sample.right),
    }));
    const nearest = Math.min(...distances.map(item => item.distance));
    const local = distances.filter(item => item.distance <= nearest + 6);
    let weightedHeight = 0;
    let totalWeight = 0;
    for (const item of local) {
      const weight = 1 / ((item.distance - nearest + 0.75) ** 2);
      weightedHeight += item.sample.height * weight;
      totalWeight += weight;
    }
    return weightedHeight / totalWeight;
  });
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