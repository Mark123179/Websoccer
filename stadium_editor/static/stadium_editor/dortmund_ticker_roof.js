import {ROOF_NAMES} from './dortmund_concept.js?v=49';

// Inventory of the exported roof assembly, not a height-based filter:
// skin/ceiling, frame/catwalks, pylons/cables and roof-mounted equipment.
// Tall seating meshes deliberately remain outside this set.
export const TICKER_ROOF_NAMES = new Set([
  ...ROOF_NAMES,
  ...[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 16, 18, 19, 20, 21, 22, 23, 24, 27, 28, 31, 32]
    .map(index => `center3_${index}.001`),
]);

export function setTickerRoofVisibility(meshes, visible) {
  if (typeof visible !== 'boolean') throw new TypeError('Dachsichtbarkeit muss ein Boolean sein.');
  meshes.forEach(mesh => { mesh.visible = visible; });
}
