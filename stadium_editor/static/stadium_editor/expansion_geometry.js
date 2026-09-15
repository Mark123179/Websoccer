(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.StadiumExpansionGeometry = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  function angleDistance(left, right) {
    return Math.abs(((left - right) + Math.PI * 3) % (Math.PI * 2) - Math.PI);
  }

  function pitchLocal(point, geometry) {
    const [cx, cy] = geometry?.meta?.fieldC || [geometry?._cx || 0, geometry?._cy || 0];
    const theta = Number(geometry?.meta?.axisTheta) || 0;
    const dx = point[0] - cx;
    const dy = point[1] - cy;
    const ct = Math.cos(theta);
    const st = Math.sin(theta);
    return [dx * ct + dy * st, -dx * st + dy * ct];
  }

  function quadPoint(quad, u, v) {
    const top = [
      quad[0][0] + (quad[1][0] - quad[0][0]) * u,
      quad[0][1] + (quad[1][1] - quad[0][1]) * u,
    ];
    const bottom = [
      quad[3][0] + (quad[2][0] - quad[3][0]) * u,
      quad[3][1] + (quad[2][1] - quad[3][1]) * u,
    ];
    return [
      bottom[0] + (top[0] - bottom[0]) * (1 - v),
      bottom[1] + (top[1] - bottom[1]) * (1 - v),
    ];
  }

  function blockExpansionInfo(block, geometry) {
    const outer = quadPoint(block.quad, .5, 1);
    const inner = quadPoint(block.quad, .5, 0);
    const center = block.quad.reduce((sum, point) => [
      sum[0] + point[0] / 4, sum[1] + point[1] / 4,
    ], [0, 0]);
    const localOuter = pitchLocal(outer, geometry);
    const localCenter = pitchLocal(center, geometry);
    return {
      block,
      outer,
      inner,
      angle: Math.atan2(localCenter[1], localCenter[0]),
      radius: Math.hypot(localOuter[0], localOuter[1]),
    };
  }

  function outerEnvelope(blocks, geometry) {
    const info = blocks.map(block => blockExpansionInfo(block, geometry));
    return info.filter(candidate => !info.some(other => {
      if (other === candidate ||
          Number(other.block.z0) <= Number(candidate.block.z0)) return false;
      return Math.hypot(
        candidate.outer[0] - other.inner[0],
        candidate.outer[1] - other.inner[1],
      ) < 12;
    })).map(item => item.block);
  }

  function standAngles(baseBlocks, geometry) {
    const grouped = new Map();
    for (const block of baseBlocks) {
      const values = grouped.get(block.stand) || [];
      values.push(blockExpansionInfo(block, geometry).angle);
      grouped.set(block.stand, values);
    }
    return new Map(Array.from(grouped, ([stand, values]) => {
      const vector = values.reduce((sum, angle) => [
        sum[0] + Math.cos(angle), sum[1] + Math.sin(angle),
      ], [0, 0]);
      return [stand, Math.atan2(vector[1], vector[0])];
    }));
  }

  function expansionEnvelope(stand, blocks, baseBlocks, geometry) {
    const centers = standAngles(baseBlocks, geometry);
    const center = centers.get(stand);
    if (!Number.isFinite(center)) return [];
    return outerEnvelope(blocks, geometry).filter(block => {
      const angle = blockExpansionInfo(block, geometry).angle;
      const nearest = Array.from(centers.entries()).sort((left, right) => {
        const delta = angleDistance(angle, left[1]) - angleDistance(angle, right[1]);
        return Math.abs(delta) > 1e-9 ? delta : left[0].localeCompare(right[0]);
      })[0];
      return nearest?.[0] === stand;
    });
  }

  function snapshotBlocks(blocks) {
    return structuredClone(blocks);
  }

  function persistentBlockEntries(blocks) {
    return blocks.flatMap((block, index) => block.simulated ? [] : [{block, index}]);
  }

  return {
    angleDistance,
    blockExpansionInfo,
    expansionEnvelope,
    outerEnvelope,
    pitchLocal,
    persistentBlockEntries,
    snapshotBlocks,
    standAngles,
  };
}));