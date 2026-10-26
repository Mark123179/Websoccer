(function attachElversbergCanopies(root) {
  function validRing(ring) {
    return Array.isArray(ring) && ring.length >= 3 &&
      ring.every(point => Array.isArray(point) && point.length >= 2 &&
        Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1])));
  }

  function bounds(ring) {
    return ring.reduce((box, point) => ({
      minX: Math.min(box.minX, point[0]), maxX: Math.max(box.maxX, point[0]),
      minY: Math.min(box.minY, point[1]), maxY: Math.max(box.maxY, point[1]),
    }), {minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity});
  }

  function pointInPolygon(point, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const a = polygon[i], b = polygon[j];
      if ((a[1] > point[1]) !== (b[1] > point[1]) &&
          point[0] < ((b[0] - a[0]) * (point[1] - a[1])) /
            (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }

  function vegetationCanopies(group, spacing = 8) {
    if (!validRing(group?.poly)) return [];
    const box = bounds(group.poly);
    const step = Math.max(5, spacing);
    const result = [];
    for (let y = box.minY + step / 2; y < box.maxY; y += step) {
      for (let x = box.minX + step / 2; x < box.maxX; x += step) {
        const seed = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
        const offset = seed - Math.floor(seed);
        const point = [
          x + (offset - .5) * step * .38,
          y + (offset - .5) * step * .24,
        ];
        if (pointInPolygon(point, group.poly)) {
          result.push({point, radius: 2.15 + offset * .85});
        }
      }
    }
    if (!result.length) {
      const point = group.poly.reduce((sum, value) => [
        sum[0] + Number(value[0]) / group.poly.length,
        sum[1] + Number(value[1]) / group.poly.length,
      ], [0, 0]);
      result.push({point, radius: 2.6});
    }
    return result;
  }

  root.ElversbergBlueprintCanopies = Object.freeze({vegetationCanopies});
})(globalThis);
