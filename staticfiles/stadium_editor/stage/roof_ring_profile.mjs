// The triangulated ShapeGeometry repeats contour vertices as Float32 values.
// Distinguish the pitch-side edge from the facade edge after that conversion.
export function ringVertexHeight(x, y, inner, zInner, zOuter) {
  return inner.some(point =>
    Math.abs(point.x - x) < 0.001 && Math.abs(point.y - y) < 0.001)
    ? zInner : zOuter;
}

export function ringFasciaHeights(zInner, fascia) {
  return {top: zInner, bottom: zInner - fascia};
}