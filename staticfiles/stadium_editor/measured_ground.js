// Opt-in, source-attributed elevation grid in model x/z. No network or inference.
export function validateElevationGrid(grid) {
  if (!grid || typeof grid !== 'object' || Array.isArray(grid) ||
      !Array.isArray(grid.origin) || grid.origin.length !== 2 ||
      !grid.origin.every(n => Number.isFinite(n) && Math.abs(n) <= 10000) ||
      !Number.isFinite(grid.step) || grid.step < 5 || grid.step > 100 ||
      !Number.isInteger(grid.cols) || !Number.isInteger(grid.rows) ||
      grid.cols < 2 || grid.rows < 2 || grid.cols > 257 || grid.rows > 257 ||
      !Array.isArray(grid.values) || grid.values.length !== grid.cols * grid.rows ||
      !grid.values.every(n => Number.isFinite(n) && Math.abs(n) <= 100) ||
      typeof grid.source !== 'string' || !grid.source.trim())
    throw new Error('groundElevation benötigt ein belegtes, vollständiges Modellhöhenraster.');
  return grid;
}

// Piecewise-linear cells, same diagonal used by drapeTriangles. Values are
// offsets from groundLevel; outside coverage is an error, never extrapolated.
export function elevationSampler(grid) {
  if (!grid) return () => 0;
  const {origin: [x0, z0], step, cols, rows, values} = validateElevationGrid(grid);
  return (x, z) => {
    const u = (x - x0) / step, v = (z - z0) / step;
    if (u < -1e-7 || v < -1e-7 || u > cols - 1 + 1e-7 || v > rows - 1 + 1e-7)
      throw new Error('Umfeld liegt außerhalb der belegten groundElevation-Abdeckung.');
    const i = Math.min(cols - 2, Math.max(0, Math.floor(u)));
    const j = Math.min(rows - 2, Math.max(0, Math.floor(v)));
    const a = u - i, b = v - j, k = j * cols + i;
    const h00 = values[k], h10 = values[k + 1], h01 = values[k + cols], h11 = values[k + cols + 1];
    return a >= b ? h00 + a * (h10 - h00) + b * (h11 - h10) :
      h00 + b * (h01 - h00) + a * (h11 - h01);
  };
}

function clip(poly, a, b) {
  const side = p => (b[0]-a[0])*(p[2]-a[1]) - (b[1]-a[1])*(p[0]-a[0]);
  const out = [];
  for (let i = 0; i < poly.length; i++) {
    const p = poly[i], q = poly[(i+1)%poly.length], sp = side(p), sq = side(q);
    if (sp >= -1e-8) out.push(p);
    if ((sp < -1e-8 && sq > 1e-8) || (sp > 1e-8 && sq < -1e-8)) {
      const t = sp / (sp - sq);
      out.push(p.map((n, k) => n + t * (q[k]-n)));
    }
  }
  return out;
}

// Split at every grid cell AND its diagonal. The ground and every mapped
// surface therefore use identical planes, avoiding buried roads/green areas.
export function drapeTriangles(vertices, grid, sample) {
  const out = [], {origin:[x0,z0], step, cols, rows} = grid;
  for (let t = 0; t < vertices.length; t += 9) {
    const tri = [vertices.slice(t,t+3),vertices.slice(t+3,t+6),vertices.slice(t+6,t+9)];
    tri.forEach(([x,,z]) => sample(x,z));
    const ix = tri.map(p => (p[0]-x0)/step), iz = tri.map(p => (p[2]-z0)/step);
    for (let j = Math.max(0,Math.floor(Math.min(...iz))); j <= Math.min(rows-2,Math.floor(Math.max(...iz))); j++)
      for (let i = Math.max(0,Math.floor(Math.min(...ix))); i <= Math.min(cols-2,Math.floor(Math.max(...ix))); i++) {
        const x = x0+i*step, z = z0+j*step;
        for (const cell of [
          [[x,z],[x+step,z],[x+step,z+step]],
          [[x,z],[x+step,z+step],[x,z+step]],
        ]) {
          let poly = tri;
          for (let e = 0; e < 3 && poly.length; e++) poly = clip(poly,cell[e],cell[(e+1)%3]);
          for (let k = 1; k < poly.length-1; k++) {
            const face = [poly[0],poly[k],poly[k+1]];
            const area = (face[1][0]-face[0][0])*(face[2][2]-face[0][2]) -
              (face[1][2]-face[0][2])*(face[2][0]-face[0][0]);
            if (Math.abs(area) < 1e-9) continue;
            for (const [px,py,pz] of face) out.push(px, py+sample(px,pz), pz);
          }
        }
      }
  }
  return out;
}

export function drapeLines(vertices, grid, sample) {
  const out = [], {origin:[x0,z0], step} = grid;
  for (let i = 0; i < vertices.length; i += 6) {
    const a = vertices.slice(i,i+3), b = vertices.slice(i+3,i+6), cuts = [0,1];
    // x/z cell edges and x-z diagonal family.
    for (const [start,end,origin] of [[a[0],b[0],x0],[a[2],b[2],z0],
      [a[0]-a[2],b[0]-b[2],x0-z0]]) {
      if (start === end) continue;
      for (let k = Math.ceil((Math.min(start,end)-origin)/step);
        k <= Math.floor((Math.max(start,end)-origin)/step); k++) {
        const t = (origin+k*step-start)/(end-start);
        if (t > 0 && t < 1) cuts.push(t);
      }
    }
    cuts.sort((x,y)=>x-y);
    for (let k = 1; k < cuts.length; k++) for (const t of [cuts[k-1],cuts[k]]) {
      const p = a.map((v,j)=>v+t*(b[j]-v));
      out.push(p[0],p[1]+sample(p[0],p[2]),p[2]);
    }
  }
  return out;
}
