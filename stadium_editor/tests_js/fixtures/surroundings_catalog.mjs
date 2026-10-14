// Deterministic city-size stress catalogs, generated in memory (no large assets).
// Coordinates are editor coordinates; all ordinary features are outside the hole.
export function surroundingsCatalog({trees = 10000, surfaces = 1000,
  roads = 0, buildings = 0, cutoutVertices = 4} = {}) {
  const polygon = (i, count, radius = 4) => Array.from({length: count}, (_, j) => {
    const angle = j * Math.PI * 2 / count;
    return [300 + (i % 100) * 12 + Math.cos(angle) * radius,
      300 + Math.floor(i / 100) * 12 + Math.sin(angle) * radius];
  });
  return {
    groundLevel: 0,
    groundCutout: cutoutVertices === 4 ? [[-10,-10],[10,-10],[10,10],[-10,10]]
      : Array.from({length:cutoutVertices}, (_, i) => [
        Math.cos(i * Math.PI * 2 / cutoutVertices) * 100,
        Math.sin(i * Math.PI * 2 / cutoutVertices) * 100,
      ]),
    trees: Array.from({length:trees}, (_, i) => [200 + (i % 1000) * 3, 200 + Math.floor(i / 1000) * 3]),
    green: Array.from({length:surfaces}, (_, i) => polygon(i, 32)),
    water: Array.from({length:Math.floor(surfaces / 10)}, (_, i) => polygon(i, 48)),
    buildings: Array.from({length:buildings}, (_, i) => polygon(i, 8, 8)),
    buildingHeights: Array.from({length:buildings}, (_, i) => 6 + i % 35),
    roads: Array.from({length:roads}, (_, i) => ({
      w: 1 + i % 5,
      p: Array.from({length:16}, (_, j) => [400 + i % 100 * 30 + j * 6,
        400 + Math.floor(i / 100) * 30 + Math.sin(j / 2) * 12]),
    })),
  };
}

// Final entries prove the checker reaches every layer's end, not a sample.
export function appendLateConflicts(data) {
  data.green.push([[0,0],[1,0],[1,1],[0,1]]);
  data.water.push([[0,0],[1,0],[1,1],[0,1]]);
  data.roads.push({p:[[0,0]], w:2});
  data.buildings.push([[0,0],[1,0],[1,1],[0,1]]);
  data.trees.push([0,0]);
  return data;
}

export const LARGE_CATALOG = Object.freeze({
  trees: 100000, surfaces: 10000, roads: 2000, buildings: 2000, cutoutVertices: 64,
});
