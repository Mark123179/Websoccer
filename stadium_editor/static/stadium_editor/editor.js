/* BLUEPRINT Stadion-Editor — Prototyp V0
   2D bearbeiten · 3D ansehen · Pressen statt malen. */
'use strict';

const EDITOR = window.STADIUM_EDITOR;

/* ── Palette: Index 0 = Beton/ungestaltet ─────────────────────── */
let PALETTE = [
  ['#3a4148','Beton'],      ['#f4f6f8','Weiß'],     ['#101216','Schwarz'],  ['#c8102e','Rot'],
  ['#7a0c1e','Dunkelrot'],  ['#1554b8','Blau'],     ['#0a2a6b','Dunkelblau'],['#6fb7e8','Himmelblau'],
  ['#ffd400','Gelb'],       ['#f07818','Orange'],   ['#1d9e50','Grün'],     ['#0c5a2e','Dunkelgrün'],
  ['#9aa3ab','Hellgrau'],   ['#6b4a2b','Braun'],    ['#7a3fa0','Violett'],  ['#22e6ff','Cyan'],
];
let PAL_RGB = PALETTE.map(p => {
  const h = p[0]; return [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
});
/* sRGB → Lab für die Quantisierung beim Pressen */
function rgb2lab(r,g,b){
  let [x,y,z] = [r/255,g/255,b/255].map(v => v>.04045 ? Math.pow((v+.055)/1.055,2.4) : v/12.92);
  const X=(x*.4124+y*.3576+z*.1805)/.95047, Y=x*.2126+y*.7152+z*.0722, Z=(x*.0193+y*.1192+z*.9505)/1.08883;
  const f=t => t>.008856 ? Math.cbrt(t) : 7.787*t+16/116;
  const fx=f(X),fy=f(Y),fz=f(Z);
  return [116*fy-16, 500*(fx-fy), 200*(fy-fz)];
}
let PAL_LAB = PAL_RGB.map(c => rgb2lab(...c));
function addCustomColor(hex){
  if(PALETTE.length >= 64) return toast('Palette voll (64 Farben).');
  if(PALETTE.some(p=>p[0].toLowerCase()===hex.toLowerCase())){
    col1 = PALETTE.findIndex(p=>p[0].toLowerCase()===hex.toLowerCase());
    syncPal(); return;
  }
  PALETTE.push([hex, 'Eigene']);
  const rgb = [parseInt(hex.slice(1,3),16), parseInt(hex.slice(3,5),16), parseInt(hex.slice(5,7),16)];
  PAL_RGB.push(rgb); PAL_LAB.push(rgb2lab(...rgb));
  buildPaletteUI(); col1 = PALETTE.length-1; syncPal();
  fillPreviewCache.clear();
  toast(`Farbe ${hex} zur Palette hinzugefügt.`);
}
const BAYER4 = [[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]];
function ditherShift(x, y){
  const amt = overlay && overlay.kind==='image' ? +(document.getElementById('imgDither')?.value||0) : 0;
  if(amt<=0) return 0;
  return (BAYER4[y&3][x&3]/16 - .469) * amt/100 * 72;
}
function nearestColor(r,g,b){
  const l = rgb2lab(r,g,b); let best=1, bd=1e9;      // Beton (0) wird nie gepresst
  for(let i=1;i<PAL_LAB.length;i++){
    const p=PAL_LAB[i], d=(l[0]-p[0])**2+(l[1]-p[1])**2+(l[2]-p[2])**2;
    if(d<bd){bd=d;best=i;}
  }
  return best;
}

/* ── Daten & Zustand ──────────────────────────────────────────── */
let D, blocks, seatData, baseData, texCache;
let pressings = [];            // gepresste Objekte
let pressId = 1;
const selection = new Set();
let tool = 'fill', col1 = 3, col2 = 1;           // Start: Rot / Weiß
let view = '2d', yaw3d = 0, tilt3d = 54, roofOn = true, dotMode = true;
let overlay = null;                               // {kind:'text'|'image', canvas, wx, wy, scale, rot}
const undoStack = [], redoStack = [];

/* Die Geometrie bestimmt die Form; die vom Server zugewiesene Kapazität
   bestimmt, wie viele Sitzpunkte ein Block tatsächlich zeigt. */
function renderableBlock(block, index){
  const geometryRows = Math.max(1, Number(block.rows) || 1);
  const geometrySeats = Math.max(1, Number(block.seats) || 1);
  const capacity = Math.max(0, Number.isFinite(Number(block.capacity))
    ? Number(block.capacity) : geometryRows * geometrySeats);
  const seats = Math.max(1, Math.min(geometrySeats, capacity || 1));
  const rows = Math.max(1, Math.ceil(capacity / seats));
  return Object.assign({}, block, {
    id: index,
    geometryRows,
    geometrySeats,
    capacity,
    rows,
    seats,
  });
}
function isRenderableSeat(block, row, seat){
  return row * block.seats + seat < block.capacity;
}

/* ── Canvas-Setup ─────────────────────────────────────────────── */
const stage = document.getElementById('stage');
const cvBase = document.getElementById('cvBase'),
      cvBlocks = document.getElementById('cvBlocks'),
      cvOverlay = document.getElementById('cvOverlay');
let W, H;
function resize(){
  W = stage.clientWidth; H = stage.clientHeight;
  for(const c of [cvBase,cvBlocks,cvOverlay]){ c.width=W; c.height=H; }
  fitView(); renderAll();
}
/* Welt → Screen (2D): Stadion mittig, Blaupause sichtbar */
let SC = 1, CX = 0, CY = 0;
function fitView(){
  const R = 430 * (D ? D.meta.maxR/138 : 1);      // relative Stadiongröße konstant halten
  SC = Math.min(W, H) / (2*R) * 1.55;
  CX = W/2; CY = H/2 + 6;
}
const w2s = (x,y) => [CX + x*SC, CY - y*SC];
const s2w = (px,py) => [(px-CX)/SC, (CY-py)/SC];

/* ── Geometrie-Helfer ─────────────────────────────────────────── */
function quadPoint(q, u, v){                      // v=0 innen (D-C), v=1 außen (A-B)
  const [A,B,C,Dq] = q;
  const ix = Dq[0] + u*(C[0]-Dq[0]), iy = Dq[1] + u*(C[1]-Dq[1]);
  const ox = A[0]  + u*(B[0]-A[0]),  oy = A[1]  + u*(B[1]-A[1]);
  return [ix + v*(ox-ix), iy + v*(oy-iy)];
}
function pointInQuad(q, x, y){
  let inside = false;
  for(let i=0,j=3;i<4;j=i++){
    const [xi,yi]=q[i], [xj,yj]=q[j];
    if((yi>y)!==(yj>y) && x < (xj-xi)*(y-yi)/(yj-yi)+xi) inside=!inside;
  }
  return inside;
}
function blockAt(wx, wy){
  for(const b of blocks) if(pointInQuad(b.quad, wx, wy)) return b;
  return null;
}

/* ── Texturen: pro Block ein Mini-Canvas (seats × rows px) ────── */
function restoreSavedDesign(savedDesign){
  if(!savedDesign || typeof savedDesign !== 'object') return;
  if(Array.isArray(savedDesign.palette) && savedDesign.palette.length){
    PALETTE = savedDesign.palette.filter(hex => /^#[0-9a-f]{6}$/i.test(hex)).map(hex => [hex, 'Gespeichert']);
    if(!PALETTE.length) return;
    PAL_RGB = PALETTE.map(p => [parseInt(p[0].slice(1,3),16),parseInt(p[0].slice(3,5),16),parseInt(p[0].slice(5,7),16)]);
    PAL_LAB = PAL_RGB.map(c => rgb2lab(...c));
  }
  if(!Array.isArray(savedDesign.blocks)) return;
  for(const saved of savedDesign.blocks){
    const index = Number(saved.id);
    if(!Number.isInteger(index) || !seatData[index] || !Array.isArray(saved.rle)) continue;
    let cursor = 0;
    for(const pair of saved.rle){
      const n = Number(pair?.[0]), color = Number(pair?.[1]);
      if(!Number.isInteger(n) || n < 0 || !Number.isInteger(color) || color < 0 || color >= PALETTE.length) break;
      seatData[index].fill(color, cursor, Math.min(cursor + n, seatData[index].length));
      cursor += n;
      if(cursor >= seatData[index].length) break;
    }
  }
}
function initStadium(stadium, savedDesign){
  D = stadium;
  blocks = D.blocks.map(renderableBlock);
  seatData = blocks.map(b => new Uint8Array(b.rows * b.seats));
  baseData = blocks.map(b => new Uint8Array(b.rows * b.seats));
  restoreSavedDesign(savedDesign);
  pressings = [];
  texCache = blocks.map(b => {
    const c = document.createElement('canvas');
    c.width = b.seats; c.height = b.rows; return c;
  });
  blocks.forEach((_,i) => updateTexture(i));
  let cx=0, cy=0;
  for(const p of D.outline){ cx+=p[0]; cy+=p[1]; }
  D._cx = cx/D.outline.length; D._cy = cy/D.outline.length;
  selection.clear(); overlay = null;
  undoStack.length = 0; redoStack.length = 0;
  fillPreviewCache.clear();
  if(document.getElementById('pressList')) syncPressList();
  const title = document.getElementById('stadiumTitle');
  if(title) title.innerHTML =
    `${D.meta.name} <span>${D.meta.club || ''} · ${Number(D.capacity_total || D.meta.capacity || 0).toLocaleString('de-DE')} Plätze</span>`;
  if(typeof syncUndoButtons==='function') syncUndoButtons();
  if(typeof syncSel==='function') syncSel();
}
function updateTexture(i){
  const b = blocks[i], c = texCache[i], ctx = c.getContext('2d');
  const img = ctx.createImageData(b.seats, b.rows);
  const data = seatData[i];
  for(let r=0; r<b.rows; r++) for(let s=0; s<b.seats; s++){
    const ci = isRenderableSeat(b, r, s) ? data[r*b.seats+s] : 0, [R,G,Bc] = PAL_RGB[ci];
    const o = ((b.rows-1-r)*b.seats + s)*4;       // Zeile 0 (innen) unten im Bild
    img.data[o]=R; img.data[o+1]=G; img.data[o+2]=Bc; img.data[o+3]=255;
  }
  ctx.putImageData(img, 0, 0);
}
/* Texturiertes Quad via 2 Dreiecke (nicht-affin robust) */
function drawTexturedQuad(ctx, tex, p){           // p = [A,B,C,D] in Screen-Koordinaten
  const w = tex.width, h = tex.height;
  // Textur-Ecken: A=(0,0) B=(w,0) C=(w,h) D=(0,h)   (A-B = außen = Bildzeile 0)
  const tri = (s0,s1,s2, t0,t1,t2) => {
    ctx.save(); ctx.beginPath();
    ctx.moveTo(s0[0],s0[1]); ctx.lineTo(s1[0],s1[1]); ctx.lineTo(s2[0],s2[1]);
    ctx.closePath(); ctx.clip();
    const d = t1[0]*t2[1]-t2[0]*t1[1] - (t0[0]*(t2[1]-t1[1]) + t0[1]*(t1[0]-t2[0]));
    if(Math.abs(d) > 1e-6){
      const a=(s1[0]*t2[1]-s2[0]*t1[1]-t0[1]*(s1[0]-s2[0])-(s0[0]*(t2[1]-t1[1])+t0[1]*s0[0]*0))/d;
      // stabile affine Lösung über Matrixinversion:
      const m = invAffine(t0,t1,t2, s0,s1,s2);
      ctx.transform(m[0],m[1],m[2],m[3],m[4],m[5]);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(tex, 0, 0);
    }
    ctx.restore();
  };
  const A=p[0],B=p[1],C=p[2],Dq=p[3];
  tri(A,B,C, [0,0],[w,0],[w,h]);
  tri(A,C,Dq, [0,0],[w,h],[0,h]);
}
function invAffine(t0,t1,t2, s0,s1,s2){
  const [x0,y0]=t0,[x1,y1]=t1,[x2,y2]=t2;
  const det = x0*(y1-y2) - y0*(x1-x2) + (x1*y2-x2*y1);
  if(Math.abs(det)<1e-9) return [1,0,0,1,0,0];
  const a=(s0[0]*(y1-y2)+s1[0]*(y2-y0)+s2[0]*(y0-y1))/det;
  const c=(s0[0]*(x2-x1)+s1[0]*(x0-x2)+s2[0]*(x1-x0))/det;
  const e=(s0[0]*(x1*y2-x2*y1)+s1[0]*(x2*y0-x0*y2)+s2[0]*(x0*y1-x1*y0))/det;
  const b=(s0[1]*(y1-y2)+s1[1]*(y2-y0)+s2[1]*(y0-y1))/det;
  const d=(s0[1]*(x2-x1)+s1[1]*(x0-x2)+s2[1]*(x1-x0))/det;
  const f=(s0[1]*(x1*y2-x2*y1)+s1[1]*(x2*y0-x0*y2)+s2[1]*(x0*y1-x1*y0))/det;
  return [a,b,c,d,e,f];
}

/* Jeder Sitz als Einzelpunkt — der Kartenchoreo-Look */
function drawBlockDots(ctx, i, proj){
  const b = blocks[i], d = seatData[i];
  const P00 = proj(0,0), P10 = proj(1,0), P01 = proj(0,1);
  const dw = Math.hypot(P10[0]-P00[0], P10[1]-P00[1]) / b.seats;
  const dh = Math.hypot(P01[0]-P00[0], P01[1]-P00[1]) / b.rows;
  const dot = Math.max(.7, Math.min(3.6, Math.min(dw, dh)*.62));
  /* sehr dunkle Grundfläche hält die Silhouette */
  const q = [proj(0,1), proj(1,1), proj(1,0), proj(0,0)];
  ctx.beginPath(); q.forEach((s,k)=> k?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]));
  ctx.closePath(); ctx.fillStyle='rgba(6,11,16,.85)'; ctx.fill();
  let last = -1;
  const h = dot/2;
  for(let r=0;r<b.rows;r++){
    const v = (r+.5)/b.rows;
    for(let s=0;s<b.seats;s++){
      if(!isRenderableSeat(b, r, s)) continue;
      const ci = d[r*b.seats+s];
      const p = proj((s+.5)/b.seats, v);
      if(ci!==last){ ctx.fillStyle = ci===0 ? 'rgba(96,106,116,.8)' : PALETTE[ci][0]; last=ci; }
      ctx.fillRect(p[0]-h, p[1]-h, dot, dot);
    }
  }
}

/* ── Basis-Layer: Blaupause + Spielfeld ───────────────────────── */
function renderBase(){
  const ctx = cvBase.getContext('2d');
  ctx.clearRect(0,0,W,H);
  ctx.fillStyle = '#03070c'; ctx.fillRect(0,0,W,H);
  // dezentes Raster
  ctx.strokeStyle = 'rgba(34,230,255,.05)'; ctx.lineWidth = 1;
  for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
  for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
  const path = pts => { ctx.beginPath(); pts.forEach((p,i)=>{const s=w2s(p[0],p[1]); i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);}); };
  // Grün
  for(const g of D.bg.green){ path(g); ctx.closePath(); ctx.fillStyle='rgba(48,242,156,.045)'; ctx.fill(); }
  // Wasser
  for(const g of D.bg.water){ path(g); ctx.closePath(); ctx.fillStyle='rgba(34,140,255,.08)'; ctx.fill(); }
  // Straßen
  for(const r of D.bg.roads){
    path(r.p); ctx.strokeStyle=`rgba(34,230,255,${r.w===3?.30:r.w===2?.22:.13})`;
    ctx.lineWidth=r.w*.9; ctx.stroke();
  }
  // Gebäude
  for(const g of D.bg.buildings){ path(g); ctx.closePath(); ctx.strokeStyle='rgba(34,230,255,.4)'; ctx.lineWidth=1; ctx.stroke(); }
  drawPitch(ctx, w2s, 1);
}
function drawPitch(ctx, toScreen, alpha){
  const th = D.meta.axisTheta, ct = Math.cos(th), st = Math.sin(th);
  const fc = D.meta.fieldC || [0,0];
  const F = (u,v) => { const wx=fc[0]+u*ct-v*st, wy=fc[1]+u*st+v*ct; return toScreen(wx,wy); };
  const line = pts => { ctx.beginPath(); pts.forEach((p,i)=>{const s=F(p[0],p[1]); i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);}); };
  const poly = pts => { line(pts); ctx.closePath(); };
  const arc = (cu,cv,r,a0,a1,close=false) => {
    ctx.beginPath();
    const n = 40;
    for(let i=0;i<=n;i++){ const a=a0+(a1-a0)*i/n;
      const s=F(cu+r*Math.cos(a), cv+r*Math.sin(a));
      i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]); }
    if(close) ctx.closePath();
  };
  ctx.save(); ctx.globalAlpha = alpha;
  /* Auslaufzone */
  poly([[-57,-38.5],[57,-38.5],[57,38.5],[-57,38.5]]);
  ctx.fillStyle = '#07301b'; ctx.fill();
  /* Mähstreifen */
  const NS = 14, SW = 105/NS;
  for(let i=0;i<NS;i++){
    const u0=-52.5+i*SW, u1=u0+SW;
    poly([[u0,-34],[u1,-34],[u1,34],[u0,34]]);
    ctx.fillStyle = i%2 ? '#0d4526' : '#0a3a20'; ctx.fill();
  }
  /* Linien */
  ctx.strokeStyle = 'rgba(244,251,255,.78)'; ctx.lineWidth = 1.2;
  ctx.lineJoin='round';
  poly([[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34]]); ctx.stroke();
  line([[0,-34],[0,34]]); ctx.stroke();
  arc(0,0,9.15,0,Math.PI*2,true); ctx.stroke();
  for(const s of [1,-1]){
    /* Strafraum 16,5 m · 40,32 m */
    line([[s*52.5,-20.16],[s*36,-20.16],[s*36,20.16],[s*52.5,20.16]]); ctx.stroke();
    /* Torraum 5,5 m · 18,32 m */
    line([[s*52.5,-9.16],[s*47,-9.16],[s*47,9.16],[s*52.5,9.16]]); ctx.stroke();
    /* Strafraumbogen um den Elfmeterpunkt — nur außerhalb des Strafraums */
    const a = Math.acos(-0.601);                       // ≈127°
    if(s>0) arc(41.5,0, 9.15, a, 2*Math.PI - a);
    else    arc(-41.5,0, 9.15, -(Math.PI-a), Math.PI-a);
    ctx.stroke();
    /* Elfmeterpunkt */
    const ps = F(s*41.5,0);
    ctx.beginPath(); ctx.arc(ps[0],ps[1],1.6,0,Math.PI*2);
    ctx.fillStyle='rgba(244,251,255,.78)'; ctx.fill();
    /* Eckbögen */
    for(const q of [1,-1]){
      const base = s>0 ? Math.PI : 0;
      const start = s>0 ? (q>0?Math.PI:Math.PI/2) : (q>0?-Math.PI/2:0);
      arc(s*52.5, q*34, 1.2, start+(s>0?0:0)+(q>0?0:0)+(s>0?(q>0?0:-0):0)+0, start+Math.PI/2);
      ctx.stroke();
    }
    /* Tor 7,32 m, angedeutet hinter der Torlinie */
    poly([[s*52.5,-3.66],[s*54.4,-3.66],[s*54.4,3.66],[s*52.5,3.66]]);
    ctx.strokeStyle='rgba(244,251,255,.55)'; ctx.stroke();
    ctx.fillStyle='rgba(244,251,255,.10)'; ctx.fill();
    ctx.strokeStyle='rgba(244,251,255,.78)';
  }
  /* Mittelpunkt */
  const mp = F(0,0);
  ctx.beginPath(); ctx.arc(mp[0],mp[1],1.6,0,Math.PI*2);
  ctx.fillStyle='rgba(244,251,255,.78)'; ctx.fill();
  ctx.restore();
}

function treeSeed(t){ const v = Math.sin(t[0]*12.9898 + t[1]*78.233)*43758.5453; return v - Math.floor(v); }
function crownPath(ctx, cx, cy, r, seed){
  const n = 12;
  ctx.beginPath();
  for(let i=0;i<=n;i++){
    const a = i/n*Math.PI*2;
    const w = 1 + .17*Math.sin(a*3 + seed*9) + .11*Math.sin(a*5 + seed*17);
    const x = cx + Math.cos(a)*r*w, y = cy + Math.sin(a)*r*w;
    i?ctx.lineTo(x,y):ctx.moveTo(x,y);
  }
  ctx.closePath();
}
function drawTrees(ctx, toScreen){
  if(!D.bg.trees) return;
  for(const t of D.bg.trees){
    const s = toScreen(t[0], t[1]);
    if(s[0]<-14||s[1]<-14||s[0]>W+14||s[1]>H+14) continue;
    const sd = treeSeed(t);
    const r = Math.max(2, (2.0 + sd*1.7) * SC);
    /* Außenkrone: gefüllt + Kontur */
    crownPath(ctx, s[0], s[1], r, sd);
    ctx.fillStyle='rgba(16,64,42,.55)'; ctx.fill();
    ctx.strokeStyle='rgba(48,242,156,.45)'; ctx.lineWidth=.9; ctx.stroke();
    /* Innenkrone: versetzte zweite Welle = Volumen */
    crownPath(ctx, s[0]+r*.14, s[1]-r*.12, r*.55, sd*3.1);
    ctx.strokeStyle='rgba(48,242,156,.28)'; ctx.lineWidth=.7; ctx.stroke();
  }
}

/* ── Block-Layer 2D ───────────────────────────────────────────── */
function renderBlocks(){
  const ctx = cvBlocks.getContext('2d');
  ctx.clearRect(0,0,W,H);
  for(let i=0;i<blocks.length;i++){
    const b = blocks[i];
    const p = b.quad.map(pt => w2s(pt[0],pt[1]));
    if(dotMode){
      drawBlockDots(ctx, i, (u,v)=>{ const w=quadPoint(b.quad,u,v); return w2s(w[0],w[1]); });
      strokeBlockBorder(ctx, b, p, .5);
    } else {
      drawTexturedQuad(ctx, texCache[i], p);
      strokeBlockBorder(ctx, b, p, 1);
    }
  }
}
function strokeBlockBorder(ctx, b, p, lw){
  ctx.beginPath();
  p.forEach((s,i)=> i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]));
  ctx.closePath();
  ctx.setLineDash(b.type==='STEH' ? [4,3] : []);
  ctx.strokeStyle = b.type==='VIP' ? 'rgba(233,199,131,.85)' : 'rgba(34,230,255,.4)';
  ctx.lineWidth = lw;
  ctx.stroke();
  ctx.setLineDash([]);
}

/* ── Overlay: Hover, Auswahl, Press-Vorlage ───────────────────── */
let hoverBlock = null, dragOverlay = false, dragOff = [0,0];
function renderOverlay(){
  const ctx = cvOverlay.getContext('2d');
  ctx.clearRect(0,0,W,H);
  if(view!=='2d') return;
  const livePrev = (tool==='fill'||tool==='pattern') && selection.size;
  for(const id of selection){
    const b = blocks[id], p = b.quad.map(pt=>w2s(pt[0],pt[1]));
    if(livePrev){
      ctx.globalAlpha = .93;
      drawTexturedQuad(ctx, fillPreviewTex(id), p);
      ctx.globalAlpha = 1;
    }
    ctx.beginPath(); p.forEach((s,i)=> i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1])); ctx.closePath();
    if(!livePrev){ ctx.fillStyle='rgba(34,230,255,.14)'; ctx.fill(); }
    ctx.setLineDash(livePrev ? [7,5] : []);
    ctx.strokeStyle='#22e6ff'; ctx.lineWidth=2; ctx.stroke();
    ctx.setLineDash([]);
  }
  if(hoverBlock !== null && !selection.has(hoverBlock)){
    const b = blocks[hoverBlock], p = b.quad.map(pt=>w2s(pt[0],pt[1]));
    ctx.beginPath(); p.forEach((s,i)=> i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1])); ctx.closePath();
    ctx.strokeStyle='rgba(34,230,255,.9)'; ctx.lineWidth=1.6; ctx.stroke();
  }
  if(overlay && overlay.preview){
    const s = w2s(overlay.wx, overlay.wy);
    ctx.save();
    ctx.translate(s[0], s[1]);
    ctx.rotate(-overlay.rot);
    const pw = overlay.canvas.width*overlay.scale*SC,
          ph = overlay.canvas.height*overlay.scale*SC;
    ctx.imageSmoothingEnabled = false;
    ctx.globalAlpha = .88;
    ctx.drawImage(overlay.preview, -pw/2, -ph/2, pw, ph);
    ctx.globalAlpha = 1;
    ctx.strokeStyle='rgba(233,199,131,.8)'; ctx.setLineDash([6,4]); ctx.lineWidth=1;
    ctx.strokeRect(-pw/2, -ph/2, pw, ph);
    ctx.restore();
  }
}

/* Vorschau-Textur für Füllen/Muster (gecacht) */
const fillPreviewCache = new Map();
function fillPreviewTex(id){
  const kind = tool==='pattern' ? document.getElementById('patternKind').value : 'solid';
  const w = tool==='pattern' ? +document.getElementById('patternW').value : 0;
  const key = `${id}|${kind}|${w}|${col1}|${col2}`;
  if(fillPreviewCache.has(key)) return fillPreviewCache.get(key);
  if(fillPreviewCache.size > 600) fillPreviewCache.clear();
  const b = blocks[id];
  const c = document.createElement('canvas'); c.width=b.seats; c.height=b.rows;
  const ictx = c.getContext('2d');
  const img = ictx.createImageData(b.seats, b.rows);
  for(let r=0;r<b.rows;r++) for(let s=0;s<b.seats;s++){
    let ci = col1;
    if(kind==='hstripe' && Math.floor(r/w)%2) ci = col2;
    if(kind==='vstripe' && Math.floor(s/w)%2) ci = col2;
    if(kind==='check'  && (Math.floor(r/w)+Math.floor(s/w))%2) ci = col2;
    if(kind==='frame') ci = (r<w||s<w||r>=b.rows-w||s>=b.seats-w) ? col2 : col1;
    const [R,G,Bc] = PAL_RGB[ci];
    const o = ((b.rows-1-r)*b.seats + s)*4;
    img.data[o]=R; img.data[o+1]=G; img.data[o+2]=Bc; img.data[o+3]=255;
  }
  ictx.putImageData(img,0,0);
  fillPreviewCache.set(key, c);
  return c;
}

/* ── 3D-Ansicht ───────────────────────────────────────────────── */
function render3D(){
  const ctx = cvBlocks.getContext('2d');
  const bctx = cvBase.getContext('2d');
  bctx.clearRect(0,0,W,H); ctx.clearRect(0,0,W,H);
  cvOverlay.getContext('2d').clearRect(0,0,W,H);
  bctx.fillStyle='#03070c'; bctx.fillRect(0,0,W,H);

  const yaw = yaw3d*Math.PI/180, tilt = tilt3d*Math.PI/180;
  const cy2 = Math.cos(yaw), sy2 = Math.sin(yaw);
  const cT = Math.cos(tilt), sT = Math.sin(tilt);
  const S3 = Math.min(W,H)/900 * 1.78 * (138/D.meta.maxR);
  const to3 = (x,y,z) => {
    const X = x*cy2 - y*sy2, Y = x*sy2 + y*cy2;
    return [W/2 + X*S3, H/2 + 95 + (Y*cT)*-S3 - z*sT*S3, Y];
  };
  // Blaupause flach am Boden
  const path3 = pts => { bctx.beginPath(); pts.forEach((p,i)=>{const s=to3(p[0],p[1],0); i?bctx.lineTo(s[0],s[1]):bctx.moveTo(s[0],s[1]);}); };
  for(const g of D.bg.green){ path3(g); bctx.closePath(); bctx.fillStyle='rgba(48,242,156,.04)'; bctx.fill(); }
  for(const r of D.bg.roads){ path3(r.p); bctx.strokeStyle=`rgba(34,230,255,${r.w===3?.22:.1})`; bctx.lineWidth=r.w*.8; bctx.stroke(); }
  for(const g of D.bg.buildings){ path3(g); bctx.closePath(); bctx.strokeStyle='rgba(34,230,255,.28)'; bctx.lineWidth=.8; bctx.stroke(); }
  // Bodenplatte: schließt Durchblicke bei flachen Winkeln
  bctx.beginPath();
  D.outline.forEach((p,i)=>{ const s=to3(p[0],p[1],0); i?bctx.lineTo(s[0],s[1]):bctx.moveTo(s[0],s[1]); });
  bctx.closePath(); bctx.fillStyle='#05090e'; bctx.fill();
  if(D.meta.track){
    const th = D.meta.axisTheta, fc = D.meta.fieldC || [0,0];
    const ct2=Math.cos(th), st2=Math.sin(th);
    bctx.beginPath();
    for(let k2=0;k2<=96;k2++){
      const al = 2*Math.PI*k2/96;
      const c=Math.cos(al), s=Math.sin(al);
      const t = ((Math.abs(c)/82)**6 + (Math.abs(s)/60)**6) ** (-1/6);
      const wx = fc[0] + t*(c*ct2 - s*st2), wy = fc[1] + t*(c*st2 + s*ct2);
      const p2 = to3(wx, wy, 0);
      k2 ? bctx.lineTo(p2[0],p2[1]) : bctx.moveTo(p2[0],p2[1]);
    }
    bctx.closePath(); bctx.fillStyle='#14406b'; bctx.fill();
    bctx.strokeStyle='rgba(140,190,230,.35)'; bctx.lineWidth=.8; bctx.stroke();
  }
  drawPitch(bctx, (x,y)=>to3(x,y,0), 1);

  // Äußerster Rang je Tribüne (nach Ausbauten dynamisch) trägt Fassade + Dach
  const outerSet = new Set();
  {
    // Äußerster Block je WINKELRICHTUNG: nichts überdeckt ihn radial von außen
    const cx = D._cx, cy = D._cy;
    const info = blocks.map(b=>{
      const a0 = Math.atan2(b.quad[0][1]-cy, b.quad[0][0]-cx);
      const a1 = Math.atan2(b.quad[1][1]-cy, b.quad[1][0]-cx);
      const m = quadPoint(b.quad,.5,1);
      let lo = a0, hi = a1;
      let d = (hi-lo+Math.PI*3) % (2*Math.PI) - Math.PI;   // signierte Breite
      if(d < 0){ const t=lo; lo=hi; hi=t; d=-d; }
      return { id:b.id, lo, w:d, r: Math.hypot(m[0]-cx, m[1]-cy) };
    });
    const overlaps = (A,B)=>{
      const mA = A.lo + A.w/2, mB = B.lo + B.w/2;
      const d = Math.abs(((mA-mB)+Math.PI*3) % (2*Math.PI) - Math.PI);
      return d < (A.w + B.w)/2 * 0.6;
    };
    for(const A of info){
      let covered = false;
      for(const B of info){
        if(B.id===A.id || B.r <= A.r + 2) continue;
        if(overlaps(A,B)){ covered = true; break; }
      }
      if(!covered) outerSet.add(A.id);
    }
  }
  // Paneele seitlich strecken, damit die Block-Fugen in Wand/Dach/Blende geschlossen sind
  const stretch = (P,Q,f=1.09) => {
    const mx2=(P[0]+Q[0])/2, my2=(P[1]+Q[1])/2;
    return [ [mx2+(P[0]-mx2)*f, my2+(P[1]-my2)*f], [mx2+(Q[0]-mx2)*f, my2+(Q[1]-my2)*f] ];
  };
  // Wand sichtbar, wenn ihre Außennormale zum Betrachter zeigt (robust bei flachen Winkeln)
  const facesCamera = (P,Q) => {
    const nx=(P[0]+Q[0])/2 - D._cx, ny=(P[1]+Q[1])/2 - D._cy;
    return (nx*sy2 + ny*cy2) < 0.02;
  };
  // Zeichenliste, painter's nach WELT-Tiefe (nicht Screen-Y — Höhe darf die Ordnung nicht kippen)
  // Fassaden-Ring: äußerste Blöcke im Winkel sortiert — Nachbarn definieren die Übergänge
  const ring = [...outerSet].map(id=>blocks[id]).sort((p,q)=>{
    const mp = quadPoint(p.quad,.5,1), mq = quadPoint(q.quad,.5,1);
    return Math.atan2(mp[1]-D._cy, mp[0]-D._cx) - Math.atan2(mq[1]-D._cy, mq[0]-D._cx);
  });
  // Dachprofil-Infos: Position innerhalb der Tribüne + Ecknachbarn
  const roofMeta = (D.meta && D.meta.roof) || {type:'ring'};
  const roofInfo = new Map();
  {
    const byStand = {};
    ring.forEach(b=>{ (byStand[b.stand]=byStand[b.stand]||[]).push(b); });
    for(const stn in byStand){
      const arr = byStand[stn];
      // Winkel entfalten (Süd läuft über ±π)
      const angs = arr.map(b=>{ const m=quadPoint(b.quad,.5,1);
        return Math.atan2(m[1]-D._cy, m[0]-D._cx); });
      const a0 = angs[0];
      const un = angs.map(a=>{ let d=a-a0; while(d<-Math.PI)d+=2*Math.PI;
        while(d>Math.PI)d-=2*Math.PI; return d; });
      const order = arr.map((b,i)=>i).sort((x,y)=>un[x]-un[y]);
      order.forEach((oi,pos)=>{
        const b = arr[oi];
        const ki = ring.indexOf(b);
        roofInfo.set(b.id, {
          tA: pos/arr.length, tB: (pos+1)/arr.length,
          gapL: ring[(ki-1+ring.length)%ring.length].stand !== b.stand,
          gapR: ring[(ki+1)%ring.length].stand !== b.stand,
        });
      });
    }
  }
  const items = [];
  for(let k=0;k<ring.length;k++){
    const b1 = ring[k], b2 = ring[(k+1)%ring.length];
    const P = b1.quad[1], Q = b2.quad[0];              // B des einen → A des nächsten
    const gd2 = (P[0]-Q[0])**2 + (P[1]-Q[1])**2;
    if(gd2 < .3) continue;                             // praktisch bündig
    if(b1.noroof && b2.noroof) continue;               // nur echte Blueprint-Tore bleiben offen
    const mid = [(P[0]+Q[0])/2, (P[1]+Q[1])/2];
    items.push({ kind:'gap', b1, b2, key: to3(mid[0],mid[1],0)[2] - .008 });
  }
  for(let i=0;i<blocks.length;i++){
    const b = blocks[i];
    const mid = quadPoint(b.quad,.5,1);
    const depth = to3(mid[0],mid[1],0)[2];
    items.push({ kind:'block', i, key: depth });
    if(b.z0 > 3) items.push({ kind:'soffit', i, key: depth + .002 });
    if(outerSet.has(b.id)){
      items.push({ kind:'wall', i, key: depth - .01 });
      if(roofOn && !b.noroof) items.push({ kind:'roof', i, key: depth - .005 });
    }
  }
  const ext = D.meta.exterior || null;
  if(ext && ext.towers){
    const zTop = Math.max(...ring.map(b=>b.z1)) + 7;
    for(let ti=0; ti<ext.towers; ti++){
      const a = -Math.PI + 2*Math.PI*(ti+.5)/ext.towers;
      // Fußpunkt: knapp außerhalb der Hülle in Richtung a
      let R = 0;
      for(const b of ring){ const m=quadPoint(b.quad,.5,1);
        const am=Math.atan2(m[1]-D._cy,m[0]-D._cx);
        if(Math.abs(((am-a)+Math.PI)%(2*Math.PI)-Math.PI) < .3)
          R = Math.max(R, Math.hypot(m[0]-D._cx, m[1]-D._cy)); }
      if(!R) continue;
      const P = [D._cx + (R+7)*Math.cos(a), D._cy + (R+7)*Math.sin(a)];
      items.push({ kind:'tower', P, r: 8, z: zTop, key: to3(P[0],P[1],0)[2] - .015 });
    }
  }
  if(roofOn && roofMeta.pylons){
    // Referenz SIP: Turmpaar an jeder Dach-Schrägecke, Füße = Eckblock-Außenecken,
    // Seile zu den Außenkanten der Nachbarblöcke — alles an realer Geometrie verankert
    const th = D.meta.axisTheta || 0, fc = D.meta.fieldC || [0,0];
    const zR = (roofMeta.level==='uniform'
      ? Math.max(...blocks.map(bb=>bb.z1)) : Math.max(...blocks.map(bb=>bb.z1)));
    const midOut = bb => [(bb.quad[0][0]+bb.quad[1][0])/2, (bb.quad[0][1]+bb.quad[1][1])/2];
    for(const dd of [Math.PI/4, 3*Math.PI/4, -Math.PI/4, -3*Math.PI/4]){
      const aw = th + dd;
      let ki = -1, best = 1e9;
      for(let k2=0;k2<ring.length;k2++){
        const m = midOut(ring[k2]);
        const a2 = Math.atan2(m[1]-fc[1], m[0]-fc[0]);
        const dA = Math.abs(((a2-aw)+Math.PI*3) % (2*Math.PI) - Math.PI);
        if(dA < best){ best = dA; ki = k2; }
      }
      if(ki < 0) continue;
      const eck = ring[ki];
      const defs = [
        { F: eck.quad[0], nbs: [ring[(ki-1+ring.length)%ring.length],
                                ring[(ki-2+ring.length)%ring.length]] },
        { F: eck.quad[1], nbs: [ring[(ki+1)%ring.length],
                                ring[(ki+2)%ring.length]] },
      ];
      for(const d2 of defs){
        const dx=d2.F[0]-fc[0], dy=d2.F[1]-fc[1], L=Math.hypot(dx,dy)||1;
        const ux=dx/L, uy=dy/L;
        const F = [d2.F[0]+ux*1.5, d2.F[1]+uy*1.5];
        const T = [F[0]+ux*4, F[1]+uy*4];
        const seile = d2.nbs.map(midOut);
        items.push({ kind:'mast', F, T, zT: zR+13, zR: zR+3, seile,
                     col: roofMeta.pylons, key: to3(F[0],F[1],0)[2] - .02 });
      }
    }
  }
  if(ext && ext.arch){
    const th = D.meta.axisTheta || 0, fc = D.meta.fieldC || [0,0];
    const ctA = Math.cos(th), stA = Math.sin(th);
    const span = (D.meta.maxR || 120) * 1.9, H = span * .42, off = -(D.meta.maxR||120)*.38;
    let prev = null;
    for(let i2=0;i2<=24;i2++){
      const u = -span/2 + span*i2/24;
      const z = H*Math.sin(Math.PI*i2/24);
      const wx = fc[0] + u*ctA - off*stA, wy = fc[1] + u*stA + off*ctA;
      const pt = [wx, wy, z];
      if(prev){
        const mid = [(prev[0]+pt[0])/2, (prev[1]+pt[1])/2];
        items.push({ kind:'archseg', p0: prev, p1: pt, key: to3(mid[0], mid[1], 0)[2] });
      }
      prev = pt;
    }
  }
  items.sort((a,b2)=>b2.key-a.key);      // großes rotY = hinten = zuerst

  for(const it of items){
    const b = it.i !== undefined ? blocks[it.i] : null;
    const [A,B,C,Dq] = b ? b.quad : [null,null,null,null];
    if(it.kind==='wall'){
      if(!facesCamera(A,B)) continue;
      const [As,Bs] = stretch(A,B);
      const zW = roofMeta.level==='uniform'
        ? Math.max(...blocks.map(bb=>bb.z1)) + 2 : b.z1;
      const p = [ to3(As[0],As[1],zW), to3(Bs[0],Bs[1],zW),
                  to3(Bs[0],Bs[1],0),    to3(As[0],As[1],0) ];
      const g = ctx.createLinearGradient(0,(p[0][1]+p[1][1])/2, 0,(p[2][1]+p[3][1])/2);
      g.addColorStop(0,'#10222f'); g.addColorStop(1,'#04090e');
      ctx.beginPath();
      p.forEach((s,k)=> k?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]));
      ctx.closePath();
      ctx.fillStyle = g; ctx.fill();
      ctx.strokeStyle='rgba(34,230,255,.28)'; ctx.lineWidth=.7; ctx.stroke();
      // leuchtende Oberkante
      ctx.beginPath(); ctx.moveTo(p[0][0],p[0][1]); ctx.lineTo(p[1][0],p[1][1]);
      ctx.strokeStyle='rgba(34,230,255,.55)'; ctx.lineWidth=1.4; ctx.stroke();
      continue;
    }
    if(it.kind==='soffit'){
      /* Blende unter der Vorderkante: schließt den Sichtspalt zwischen Rängen */
      const h = Math.min(b.z0 - .5, 6);
      const [Ds,Cs] = stretch(Dq,C);
      const p = [ to3(Ds[0],Ds[1],b.z0), to3(Cs[0],Cs[1],b.z0),
                  to3(Cs[0],Cs[1],b.z0-h), to3(Ds[0],Ds[1],b.z0-h) ];
      ctx.beginPath(); p.forEach((s,q)=> q?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]));
      ctx.closePath();
      ctx.fillStyle='#0a141d'; ctx.fill();
      ctx.strokeStyle='rgba(34,230,255,.22)'; ctx.lineWidth=.5; ctx.stroke();
      continue;
    }
    if(it.kind==='gap'){
      /* Übergangspaneel im Fassadenring: schließt Fugen und Höhensprünge zwischen Nachbarn */
      const P = it.b1.quad[1], Q = it.b2.quad[0];
      if(!facesCamera(P,Q)) continue;
      const p = [ to3(P[0],P[1],it.b1.z1), to3(Q[0],Q[1],it.b2.z1),
                  to3(Q[0],Q[1],0),        to3(P[0],P[1],0) ];
      const g = ctx.createLinearGradient(0,(p[0][1]+p[1][1])/2, 0,(p[2][1]+p[3][1])/2);
      g.addColorStop(0,'#10222f'); g.addColorStop(1,'#04090e');
      ctx.beginPath(); p.forEach((s,q)=> q?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]));
      ctx.closePath();
      ctx.fillStyle=g; ctx.fill();
      ctx.strokeStyle='rgba(34,230,255,.3)'; ctx.lineWidth=.6; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(p[0][0],p[0][1]); ctx.lineTo(p[1][0],p[1][1]);
      ctx.strokeStyle='rgba(34,230,255,.5)'; ctx.lineWidth=1.1; ctx.stroke();
      continue;
    }
    if(it.kind==='tower'){
      const rT = it.r;
      const base = to3(it.P[0], it.P[1], 0), top = to3(it.P[0], it.P[1], it.z);
      const sw = rT * S3;
      ctx.fillStyle='rgba(16,34,46,.92)';
      ctx.beginPath();
      ctx.moveTo(base[0]-sw, base[1]); ctx.lineTo(top[0]-sw, top[1]);
      ctx.ellipse(top[0], top[1], sw, sw*.38, 0, Math.PI, 0);
      ctx.lineTo(base[0]+sw, base[1]);
      ctx.ellipse(base[0], base[1], sw, sw*.38, 0, 0, Math.PI);
      ctx.closePath(); ctx.fill();
      ctx.strokeStyle='rgba(34,230,255,.45)'; ctx.lineWidth=.8; ctx.stroke();
      // Spiralrampen-Andeutung
      ctx.strokeStyle='rgba(34,230,255,.25)'; ctx.lineWidth=.5;
      for(let sp=1; sp<4; sp++){
        const zz = it.z*sp/4;
        const c1 = to3(it.P[0], it.P[1], zz);
        ctx.beginPath(); ctx.ellipse(c1[0], c1[1], sw, sw*.38, 0, 0, Math.PI);
        ctx.stroke();
      }
      continue;
    }
    if(it.kind==='archseg'){
      const s0 = to3(it.p0[0], it.p0[1], it.p0[2]);
      const s1 = to3(it.p1[0], it.p1[1], it.p1[2]);
      ctx.strokeStyle='rgba(210,230,240,.85)'; ctx.lineCap='round';
      for(const lw of [3, 1.2]){
        ctx.lineWidth = lw;
        ctx.beginPath(); ctx.moveTo(s0[0],s0[1]); ctx.lineTo(s1[0],s1[1]); ctx.stroke();
      }
      ctx.lineCap='butt';
      continue;
    }
    if(it.kind==='arch'){
      const th = D.meta.axisTheta, fc = D.meta.fieldC || [0,0];
      const ct2=Math.cos(th), st2=Math.sin(th);
      const W = it.R*1.05, H = it.R*.95, off = -it.R*.42;
      ctx.strokeStyle='rgba(210,230,240,.85)'; ctx.lineWidth=3; ctx.lineCap='round';
      for(const lw of [3, 1.2]){
        ctx.lineWidth = lw;
        ctx.beginPath();
        for(let k2=0;k2<=28;k2++){
          const u = -1 + 2*k2/28;
          const lx = u*W, ly = off, lz = H*(1-u*u);
          const wx = fc[0] + lx*ct2 - ly*st2, wy = fc[1] + lx*st2 + ly*ct2;
          const s = to3(wx, wy, lz);
          k2 ? ctx.lineTo(s[0], s[1]) : ctx.moveTo(s[0], s[1]);
        }
        ctx.stroke();
      }
      ctx.lineCap='butt';
      continue;
    }
    if(it.kind==='mast'){
      const f = to3(it.F[0], it.F[1], 0);
      const t = to3(it.T[0], it.T[1], it.zT);
      ctx.strokeStyle = it.col; ctx.lineCap='round';
      for(const off of [-1.4, 1.4]){                     // Doppelstrich = Fachwerkturm
        ctx.lineWidth = 1.9;
        ctx.beginPath(); ctx.moveTo(f[0]+off, f[1]); ctx.lineTo(t[0]+off*.6, t[1]); ctx.stroke();
      }
      ctx.lineWidth = 1;
      for(const q of [.3,.55,.8]){                       // Querstreben
        const mx2=f[0]+(t[0]-f[0])*q, my2=f[1]+(t[1]-f[1])*q;
        ctx.beginPath(); ctx.moveTo(mx2-2, my2); ctx.lineTo(mx2+2, my2); ctx.stroke();
      }
      ctx.lineWidth = .8; ctx.globalAlpha = .8;          // Abspannseile zur Dachkante
      for(const sp of it.seile){
        const s2 = to3(sp[0], sp[1], it.zR);
        ctx.beginPath(); ctx.moveTo(t[0], t[1]); ctx.lineTo(s2[0], s2[1]); ctx.stroke();
      }
      ctx.globalAlpha = 1; ctx.lineCap='butt';
      continue;
    }
    if(it.kind==='bock'){
      const a = to3(it.apex[0], it.apex[1], it.z);
      const f1 = to3(it.F1[0], it.F1[1], 0), f2 = to3(it.F2[0], it.F2[1], 0);
      const t1 = to3(it.T1[0], it.T1[1], it.zT), t2 = to3(it.T2[0], it.T2[1], it.zT);
      ctx.strokeStyle = it.col; ctx.lineCap='round';
      ctx.lineWidth = 2.8;
      ctx.beginPath(); ctx.moveTo(f1[0],f1[1]); ctx.lineTo(a[0],a[1]);
      ctx.lineTo(f2[0],f2[1]); ctx.stroke();
      ctx.lineWidth = 1.4;
      const m1=[(f1[0]+a[0])/2,(f1[1]+a[1])/2], m2=[(f2[0]+a[0])/2,(f2[1]+a[1])/2];
      ctx.beginPath(); ctx.moveTo(m1[0],m1[1]); ctx.lineTo(m2[0],m2[1]); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(t1[0],t1[1]); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(t2[0],t2[1]); ctx.stroke();
      ctx.lineCap='butt';
      continue;
    }
    if(it.kind==='pylon'){
      if(it.F){
        const f2 = to3(it.F[0], it.F[1], 0);
        const h2 = to3(it.H[0], it.H[1], it.z);
        ctx.strokeStyle = it.col; ctx.lineWidth = 2.6; ctx.lineCap='round';
        ctx.beginPath(); ctx.moveTo(f2[0],f2[1]); ctx.lineTo(h2[0],h2[1]); ctx.stroke();
        ctx.lineWidth = 1.1;
        ctx.beginPath(); ctx.moveTo(f2[0]+2,f2[1]); ctx.lineTo(h2[0]+1,h2[1]); ctx.stroke();
        ctx.lineCap='butt';
        continue;
      }
      const P = it.P, col = it.col;
      const foot = to3(P[0],P[1],0), top = to3(P[0],P[1],it.z);
      ctx.strokeStyle = col; ctx.lineWidth = 2.4;
      ctx.beginPath(); ctx.moveTo(foot[0],foot[1]); ctx.lineTo(top[0],top[1]); ctx.stroke();
      ctx.fillStyle = col;
      ctx.beginPath(); ctx.arc(top[0],top[1],2.6,0,Math.PI*2); ctx.fill();
      continue;
    }
    if(it.kind==='roof'){
      const t = roofMeta.depth || 1.35;                         // Dachtiefe pro Stadion
      const zRoofBase = roofMeta.level==='uniform'
        ? Math.max(...blocks.map(bb=>bb.z1)) : b.z1;
      // Dachinnenkante nie näher als 6 m an die Feldkurve (schützt einrangige Tribünen)
      const fc2 = D.meta.fieldC || [0,0], th2 = D.meta.axisTheta;
      const c2t=Math.cos(th2), s2t=Math.sin(th2);
      const ia = D.meta.track ? 82 : 59.5, ib = D.meta.track ? 60 : 41;
      const clampIn = (P, Q)=>{
        const dx=Q[0]-P[0], dy=Q[1]-P[1], L=Math.hypot(dx,dy)||1;
        const lx=(P[0]-fc2[0])*c2t+(P[1]-fc2[1])*s2t;
        const ly=-(P[0]-fc2[0])*s2t+(P[1]-fc2[1])*c2t;
        const al=Math.atan2(ly,lx);
        const tf=((Math.abs(Math.cos(al))/ia)**6+(Math.abs(Math.sin(al))/ib)**6)**(-1/6);
        const maxL=Math.max(6, Math.hypot(lx,ly)-tf-6);
        const f=Math.min(1, maxL/L);
        return [P[0]+dx*f, P[1]+dy*f];
      };
      const Ai0 = clampIn(A, [A[0]+(Dq[0]-A[0])*t, A[1]+(Dq[1]-A[1])*t]);
      const Bi0 = clampIn(B, [B[0]+(C[0]-B[0])*t,  B[1]+(C[1]-B[1])*t]);
      const ri = roofInfo.get(b.id) || {tA:.4, tB:.6};
      let fL = 1.09, fR = 1.09;
      if(roofMeta.type==='flat4'){                              // getrennte Tribünendächer
        if(ri.gapL) fL = .84;
        if(ri.gapR) fR = .84;
      }
      const stretch2 = (P,Q)=>{
        const mx2=(P[0]+Q[0])/2, my2=(P[1]+Q[1])/2;
        return [[mx2+(P[0]-mx2)*fL, my2+(P[1]-my2)*fL],
                [mx2+(Q[0]-mx2)*fR, my2+(Q[1]-my2)*fR]];
      };
      const [As,Bs] = stretch2(A,B);
      const [Ai,Bi] = stretch2(Ai0,Bi0);
      let zA = zRoofBase+3, zB = zRoofBase+3;
      if(roofMeta.type==='arc'){                                // Bogenbinder-Silhouette
        const h = 7*(roofMeta.bulge||1);
        zA += h*Math.sin(Math.PI*ri.tA);
        zB += h*Math.sin(Math.PI*ri.tB);
      }
      const zIn = roofMeta.level==='uniform' ? zRoofBase - 2
                  : b.z1 - (b.z1-b.z0)*.3;                      // leicht nach innen geneigt
      const p = [ to3(As[0],As[1],zA),  to3(Bs[0],Bs[1],zB),
                  to3(Bi[0],Bi[1],zIn), to3(Ai[0],Ai[1],zIn) ];
      ctx.beginPath();
      p.forEach((s,q)=> q?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]));
      ctx.closePath();
      const bb = (roofMeta.bright !== undefined) ? roofMeta.bright
                 : (roofMeta.tone==='hell' ? .8 : 0);
      const roofA = tilt3d < 42 ? (bb>.3 ? .5 : .25) : .62;
      ctx.fillStyle = `rgba(${Math.round(14+180*bb)},${Math.round(32+172*bb)},${Math.round(42+170*bb)},${roofA})`;
      ctx.fill();
      if(roofMeta.diamond){                        // Membran-Rautennetz (Allianz)
        ctx.strokeStyle='rgba(230,245,250,.22)'; ctx.lineWidth=.5;
        ctx.beginPath();
        ctx.moveTo(p[0][0],p[0][1]); ctx.lineTo(p[2][0],p[2][1]);
        ctx.moveTo(p[1][0],p[1][1]); ctx.lineTo(p[3][0],p[3][1]);
        ctx.stroke();
      }
      if(roofMeta.girders){                        // farbige Stahlträger (San Siro)
        ctx.strokeStyle = roofMeta.girders; ctx.lineWidth = 1.5;
        for(const f of [.2,.5,.8]){
          const q0=[p[0][0]+(p[1][0]-p[0][0])*f, p[0][1]+(p[1][1]-p[0][1])*f];
          const q1=[p[3][0]+(p[2][0]-p[3][0])*f, p[3][1]+(p[2][1]-p[3][1])*f];
          ctx.beginPath(); ctx.moveTo(q0[0],q0[1]); ctx.lineTo(q1[0],q1[1]); ctx.stroke();
        }
      }
      if(roofMeta.girders){                        // markante Dachträger (San Siro rot)
        ctx.strokeStyle = roofMeta.girders; ctx.lineWidth = 1.6;
        for(const f2 of [.2,.5,.8]){
          const q0=[p[0][0]+(p[1][0]-p[0][0])*f2, p[0][1]+(p[1][1]-p[0][1])*f2];
          const q1=[p[3][0]+(p[2][0]-p[3][0])*f2, p[3][1]+(p[2][1]-p[3][1])*f2];
          ctx.beginPath(); ctx.moveTo(q0[0],q0[1]); ctx.lineTo(q1[0],q1[1]); ctx.stroke();
        }
      }
      if(roofMeta.spokes){                         // radiale Dachträger
        ctx.strokeStyle = bb>.4 ? 'rgba(30,60,75,.5)' : 'rgba(34,230,255,.28)';
        ctx.lineWidth=.7;
        for(const f of [.33,.66]){
          const q0=[p[0][0]+(p[1][0]-p[0][0])*f, p[0][1]+(p[1][1]-p[0][1])*f];
          const q1=[p[3][0]+(p[2][0]-p[3][0])*f, p[3][1]+(p[2][1]-p[3][1])*f];
          ctx.beginPath(); ctx.moveTo(q0[0],q0[1]); ctx.lineTo(q1[0],q1[1]); ctx.stroke();
        }
      }
      ctx.strokeStyle='rgba(34,230,255,.32)'; ctx.lineWidth=.6; ctx.stroke();
      // Traufkante betonen
      ctx.beginPath(); ctx.moveTo(p[3][0],p[3][1]); ctx.lineTo(p[2][0],p[2][1]);
      ctx.strokeStyle='rgba(34,230,255,.5)'; ctx.lineWidth=1; ctx.stroke();
      if(roofMeta.type==='arc'){
        ctx.beginPath(); ctx.moveTo(p[0][0],p[0][1]); ctx.lineTo(p[1][0],p[1][1]);
        ctx.strokeStyle='rgba(34,230,255,.6)'; ctx.lineWidth=1.3; ctx.stroke();
      }
      continue;
    }
    const p = [ to3(A[0],A[1],b.z1), to3(B[0],B[1],b.z1),      // außen = hoch
                to3(C[0],C[1],b.z0), to3(Dq[0],Dq[1],b.z0) ];  // innen = tief
    if(dotMode){
      drawBlockDots(ctx, it.i, (u,v)=>{
        const w = quadPoint(b.quad,u,v);
        return to3(w[0], w[1], b.z0 + v*(b.z1-b.z0));
      });
      strokeBlockBorder(ctx, b, p, .4);
    } else {
      drawTexturedQuad(ctx, texCache[it.i], p);
      strokeBlockBorder(ctx, b, p, .7);
    }
  }

}

/* ── Renderdispatch ───────────────────────────────────────────── */
function renderAll(){
  if(view==='2d'){ renderBase(); renderBlocks(); renderOverlay(); }
  else render3D();
}

/* ── Undo / Redo ──────────────────────────────────────────────── */
function snapshotFull(){
  undoStack.push({
    base: baseData.map(a=>a.slice()),
    press: pressings.map(p=>({...p})),
  });
  if(undoStack.length>30) undoStack.shift();
  redoStack.length = 0; syncUndoButtons();
}
function applySnap(stackFrom, stackTo){
  const snap = stackFrom.pop(); if(!snap) return;
  stackTo.push({ base: baseData.map(a=>a.slice()), press: pressings.map(p=>({...p})) });
  baseData.forEach((a,i)=>a.set(snap.base[i]));
  pressings = snap.press.map(p=>({...p}));
  syncUndoButtons(); recompose(); syncPressList();
}
function syncUndoButtons(){
  document.getElementById('btnUndo').disabled = !undoStack.length;
  document.getElementById('btnRedo').disabled = !redoStack.length;
}

/* ── Aktionen: Füllen & Muster ────────────────────────────────── */
function applyFill(){
  if(!selection.size) return toast('Erst Blöcke wählen.');
  snapshotFull();
  for(const id of selection) baseData[id].fill(col1);
  recompose(); toast(`${selection.size} Blöcke gefüllt.`);
}
function applyPattern(){
  if(!selection.size) return toast('Erst Blöcke wählen.');
  const kind = document.getElementById('patternKind').value;
  const w = +document.getElementById('patternW').value;
  snapshotFull();
  for(const id of selection){
    const b = blocks[id], d = baseData[id];
    for(let r=0;r<b.rows;r++) for(let s=0;s<b.seats;s++){
      let c = col1;
      if(kind==='hstripe' && Math.floor(r/w)%2) c = col2;
      if(kind==='vstripe' && Math.floor(s/w)%2) c = col2;
      if(kind==='check'  && (Math.floor(r/w)+Math.floor(s/w))%2) c = col2;
      if(kind==='frame') c = (r<w||s<w||r>=b.rows-w||s>=b.seats-w) ? col2 : col1;
      d[r*b.seats+s]=c;
    }
  }
  recompose(); toast('Muster gepresst.');
}

/* ── Overlay bauen: Text & Bild (ein Codepfad) ────────────────── */
function makeTextOverlay(){
  const t = document.getElementById('textInput').value.trim();
  if(!t){ overlay=null; renderOverlay(); return; }
  const size = +document.getElementById('textSize').value;
  const bend = +document.getElementById('textBend').value;
  const font = document.getElementById('textFont').value;
  const bg = document.getElementById('textBg').checked;
  const pad = bg ? Math.round(size*.6) : 4;
  const meas = document.createElement('canvas').getContext('2d');
  meas.font = `600 ${size}px "${font}", sans-serif`;
  let c;
  if(Math.abs(bend) < 3){
    /* gerade */
    const textW = meas.measureText(t).width;
    c = document.createElement('canvas');
    c.width = Math.ceil(textW)+pad*2; c.height = Math.ceil(size*1.3)+(bg?pad:0);
    const ctx = c.getContext('2d');
    if(bg){ ctx.fillStyle = PALETTE[col2][0]; ctx.fillRect(0,0,c.width,c.height); }
    ctx.font = `600 ${size}px "${font}", sans-serif`;
    ctx.fillStyle = PALETTE[col1][0];
    ctx.textBaseline='middle'; ctx.fillText(t, pad, c.height/2);
  } else {
    /* Text auf Kreisbogen, Zeichen für Zeichen */
    const chars = [...t];
    const widths = chars.map(ch => meas.measureText(ch).width);
    const textW = Math.max(1, widths.reduce((a,b)=>a+b,0));
    const totalA = Math.abs(bend)/100 * Math.PI;          // bis 180°
    const R = textW / totalA;
    const hb = size*.7 + (bg ? pad*.6 : 2);               // halbe Bandhöhe
    const Rout = R + hb, Rin = Math.max(4, R - hb);
    const half = totalA/2, up = bend > 0;
    const w = Math.ceil(2*Rout*Math.min(1, Math.sin(half))) + 8;
    const h = Math.ceil(Rout - Rin*Math.cos(Math.min(half, Math.PI/2))) + 8;
    c = document.createElement('canvas'); c.width=w; c.height=h;
    const ctx = c.getContext('2d');
    const cx = w/2;
    const cy = up ? Rout + 4 : h - Rout - 4;
    const aStart = up ? -Math.PI/2 - half : Math.PI/2 + half;
    const dirA = up ? 1 : -1;                             // Leserichtung entlang des Bogens
    if(bg){
      ctx.beginPath();
      const a0 = up ? aStart : aStart - totalA;
      ctx.arc(cx, cy, Rout, a0, a0 + totalA);
      ctx.arc(cx, cy, Rin, a0 + totalA, a0, true);
      ctx.closePath();
      ctx.fillStyle = PALETTE[col2][0]; ctx.fill();
    }
    ctx.font = `600 ${size}px "${font}", sans-serif`;
    ctx.fillStyle = PALETTE[col1][0];
    ctx.textAlign='center'; ctx.textBaseline='middle';
    let cum = 0;
    for(let i=0;i<chars.length;i++){
      const a = aStart + dirA * (cum + widths[i]/2)/textW * totalA;
      cum += widths[i];
      ctx.save();
      ctx.translate(cx + R*Math.cos(a), cy + R*Math.sin(a));
      ctx.rotate(a + (up ? Math.PI/2 : -Math.PI/2));
      ctx.fillText(chars[i], 0, 0);
      ctx.restore();
    }
  }
  ensureOverlay('text', c);
  overlay.rot = +document.getElementById('textRot').value*Math.PI/180;
  renderOverlay();
}
/* Vorlage an der Tribüne ausrichten: Textrichtung = Außenkante des Blocks unter der Mitte */
function alignToStand(){
  if(!overlay) return;
  let b = blockAt(overlay.wx, overlay.wy);
  if(!b){ const u = blocksUnderOverlay(); if(u.size) b = blocks[[...u][0]]; }
  if(!b && selection.size) b = blocks[[...selection][0]];
  if(!b) return toast('Vorlage erst über eine Tribüne ziehen.');
  const [A,B] = b.quad;
  let a = Math.atan2(B[1]-A[1], B[0]-A[0]);
  if(a > Math.PI/2) a -= Math.PI;          // nie kopfstehend
  if(a < -Math.PI/2) a += Math.PI;
  overlay.rot = a;
  const deg = Math.round(a*180/Math.PI);
  const slider = overlay.kind==='text' ? 'textRot' : 'imgRot';
  document.getElementById(slider).value = deg;
  renderOverlay(); toast('An Tribüne ausgerichtet.');
}
function makeImageOverlay(img){
  const c = document.createElement('canvas');
  const maxDim = 480, f = Math.min(1, maxDim/Math.max(img.width,img.height));
  c.width = img.width*f; c.height = img.height*f;
  c.getContext('2d').drawImage(img,0,0,c.width,c.height);
  ensureOverlay('image', c);
  syncImageOverlay();
}
function ensureOverlay(kind, canvas){
  const keep = overlay && overlay.kind===kind;
  const wx = keep?overlay.wx : selCenter()[0], wy = keep?overlay.wy : selCenter()[1];
  overlay = { kind, canvas, wx, wy,
              scale: keep?overlay.scale : .55, rot: keep?overlay.rot : 0 };
  quantizeOverlay(); buildPreview();
  document.getElementById('btnPress').disabled = false;
}
/* Vorlage: Pixel cachen — bei Glätten ≥1 vorab tiefpass-gefiltert (Blur passend
   zur Sitzgröße), damit Foto-Details zu Mischtönen werden statt Zufallstupfern. */
function quantizeOverlay(){
  overlay.qw = overlay.canvas.width; overlay.qh = overlay.canvas.height;
  overlay._S = null;                        // Sampler wird lazy neu gebaut
}
/* Bildregler aus dem DOM */
function domImgParams(){
  const cut = +(document.getElementById('imgCut')?.value||0);
  const dither = +(document.getElementById('imgDither')?.value||0);
  return {
    cut,
    hi: cut*.55, lo: cut*.55, sat: cut*.7,
    boost: +(document.getElementById('imgBoost')?.value||0),
    smooth: dither>10 ? 1 : 2,                 // Mischen aktiv → feine Strukturen erhalten
    dither,
    fillBg: false,
  };
}
/* Sampler: Quellpixel + Schwellen + Blur (abhängig von Vorlagen-Maßstab) */
function makeSampler(canvas, kind, p, scale){
  const w = canvas.width, h = canvas.height;
  let srcC = canvas;
  const smooth = kind==='image' ? p.smooth : 0;
  if(smooth>=1){
    const pxPerSeat = 0.55/scale;
    const blur = Math.min(12, Math.max(0, pxPerSeat/2.4));
    if(blur > .6){
      const t = document.createElement('canvas'); t.width=w; t.height=h;
      const tc = t.getContext('2d');
      tc.filter = `blur(${blur.toFixed(1)}px)`;
      tc.drawImage(canvas,0,0);
      srcC = t;
    }
  }
  const raw = srcC.getContext('2d').getImageData(0,0,w,h).data;
  return { raw, qw:w, qh:h, kind,
           hi: kind==='image'?p.hi:0, lo: kind==='image'?p.lo:0,
           sat: kind==='image'?p.sat:0, boost: kind==='image'?p.boost:0 };
}
function sampleFrom(S, lx, ly){
  const px = lx|0, py = ly|0;
  if(px<0||py<0||px>=S.qw||py>=S.qh) return 'out';
  const o = (py*S.qw+px)*4, a = S.raw[o+3];
  if(a<96) return 'cut';
  let R=S.raw[o],G=S.raw[o+1],B=S.raw[o+2];
  const luma = (R*.299+G*.587+B*.114)/255;
  if(S.hi>0 && luma > 1-S.hi/100*.6) return 'cut';
  if(S.lo>0 && luma < S.lo/100*.6) return 'cut';
  if(S.sat>0 && (Math.max(R,G,B)-Math.min(R,G,B)) < S.sat*1.15) return 'cut';
  if(S.boost>0){
    const m=(R+G+B)/3, k=1+S.boost/100*1.4;
    R=Math.max(0,Math.min(255,m+(R-m)*k));
    G=Math.max(0,Math.min(255,m+(G-m)*k));
    B=Math.max(0,Math.min(255,m+(B-m)*k));
  }
  return [R,G,B];
}
function sampleRaw(lx, ly){
  if(!overlay._S) overlay._S = makeSampler(overlay.canvas, overlay.kind, domImgParams(), overlay.scale);
  return sampleFrom(overlay._S, lx, ly);
}
/* Mehrheitsfilter: isolierte Einzelsitze an die Umgebung angleichen */
function modeFilter(d, rows, seats, touched){
  const out = d.slice();
  for(let r=0;r<rows;r++) for(let s=0;s<seats;s++){
    const idx = r*seats+s;
    if(!touched[idx]) continue;
    const count = {};
    for(let dr=-1;dr<=1;dr++) for(let ds=-1;ds<=1;ds++){
      const rr=r+dr, ss=s+ds;
      if(rr<0||ss<0||rr>=rows||ss>=seats) continue;
      const c = d[rr*seats+ss];
      count[c]=(count[c]||0)+1;
    }
    let best=d[idx], bn=-1;
    for(const k in count) if(count[k]>bn){ bn=count[k]; best=+k; }
    out[idx]=best;
  }
  d.set(out);
}
/* Druckvorschau: die Vorlage in Sitzraster-Auflösung, ehrlich grob. */
const ROW_D = 0.8;                                 // m Reihentiefe
function buildPreview(){
  if(!overlay) return;
  const wmW = overlay.canvas.width * overlay.scale;
  const wmH = overlay.canvas.height * overlay.scale;
  const cols = Math.max(2, Math.round(wmW/0.55));
  const rows = Math.max(2, Math.round(wmH/ROW_D));
  const p = document.createElement('canvas'); p.width=cols; p.height=rows;
  const ctx = p.getContext('2d');
  const im = ctx.createImageData(cols, rows);
  const smooth = overlay.kind==='image' ? domImgParams().smooth : 1;
  const SS = smooth>=1 ? 3 : 1;
  const cells = new Uint8Array(cols*rows).fill(255);
  const fillBg = false;
  const isText = overlay.kind==='text';
  const votes = new Uint16Array(PALETTE.length);
  for(let y=0;y<rows;y++) for(let x=0;x<cols;x++){
    let aR=0,aG=0,aB=0,n=0;
    if(isText) votes.fill(0);
    for(let i=0;i<SS;i++) for(let j=0;j<SS;j++){
      const sx = (x+(i+.5)/SS)/cols*overlay.qw;
      const sy = (y+(j+.5)/SS)/rows*overlay.qh;
      const c = sampleRaw(sx, sy);
      if(Array.isArray(c)){
        n++;
        if(isText) votes[nearestColor(c[0],c[1],c[2])]++;
        else { aR+=c[0]; aG+=c[1]; aB+=c[2]; }
      }
    }
    if(n >= SS*SS*.35){
      if(isText){
        let best=0, bn=-1;
        for(let k2=0;k2<votes.length;k2++) if(votes[k2]>bn){ bn=votes[k2]; best=k2; }
        cells[y*cols+x] = best;
      } else {
        const t = ditherShift(x, y);
        cells[y*cols+x] = nearestColor(aR/n+t, aG/n+t, aB/n+t);
      }
    }
    else if(fillBg) cells[y*cols+x] = col2;
  }
  if(smooth>=2){
    const t = new Uint8Array(cols*rows);
    for(let i=0;i<t.length;i++) t[i] = cells[i]!==255 ? 1 : 0;
    for(let k=0;k<smooth-1;k++) modeFilter(cells, rows, cols, t);
  }
  for(let i=0;i<cols*rows;i++){
    const o=i*4;
    if(cells[i]===255){ im.data[o+3]=0; continue; }
    const [R,G,B]=PAL_RGB[cells[i]];
    im.data[o]=R; im.data[o+1]=G; im.data[o+2]=B; im.data[o+3]=235;
  }
  ctx.putImageData(im,0,0);
  overlay.preview = p;
}
function syncImageOverlay(){
  if(!overlay || overlay.kind!=='image') return;
  overlay.scale = +document.getElementById('imgScale').value/100 * .55;
  overlay.rot = +document.getElementById('imgRot').value*Math.PI/180;
  quantizeOverlay(); buildPreview(); renderOverlay();
}
function selCenter(){
  if(!selection.size) return [0,0];
  let x=0,y=0,n=0;
  for(const id of selection){ const m=quadPoint(blocks[id].quad,.5,.5); x+=m[0];y+=m[1];n++; }
  return [x/n,y/n];
}

/* ── DIE PRESS-OPERATION ──────────────────────────────────────── */
function blocksUnder(S, wx, wy, scale, rot){
  const ids = new Set();
  const cr = Math.cos(rot), sr = Math.sin(rot);
  for(const b of blocks){
    outer:
    for(let u=0;u<=1;u+=.25) for(let v=0;v<=1;v+=.25){
      const [px,py] = quadPoint(b.quad,u,v);
      const dx = px-wx, dy = py-wy;
      const lx = ( dx*cr + dy*sr)/scale + S.qw/2;
      const ly = ( dx*sr - dy*cr)/scale + S.qh/2;
      if(lx>=0&&ly>=0&&lx<S.qw&&ly<S.qh){ ids.add(b.id); break outer; }
    }
  }
  return ids;
}
function blocksUnderOverlay(){
  if(!overlay._S) overlay._S = makeSampler(overlay.canvas, overlay.kind, domImgParams(), overlay.scale);
  return blocksUnder(overlay._S, overlay.wx, overlay.wy, overlay.scale, overlay.rot);
}
/* Ein Pressing-Objekt aufs Sitzraster anwenden (für recompose) */
function applyPressing(o){
  const S = makeSampler(o.canvas, o.kind, o.params, o.scale);
  const targets = o.targets ? new Set(o.targets) : blocksUnder(S, o.wx, o.wy, o.scale, o.rot);
  const cr = Math.cos(o.rot), sr = Math.sin(o.rot);
  const isText = o.kind==='text';
  const smooth = o.kind==='image' ? o.params.smooth : 1;
  const SS = smooth>=1 ? 3 : 1;
  const dith = o.kind==='image' ? o.params.dither : 0;
  const fillBg = o.kind==='image' && o.params.fillBg;
  const votes = new Uint16Array(PALETTE.length);
  for(const id of targets){
    const b = blocks[id], d = seatData[id];
    const touched = new Uint8Array(b.rows*b.seats);
    for(let r=0;r<b.rows;r++) for(let s=0;s<b.seats;s++){
      let aR=0,aG=0,aB=0,n=0,nIn=0;
      if(isText) votes.fill(0);
      for(let i=0;i<SS;i++) for(let j=0;j<SS;j++){
        const [wx,wy] = quadPoint(b.quad, (s+(i+.5)/SS)/b.seats, (r+(j+.5)/SS)/b.rows);
        const dx = wx-o.wx, dy = wy-o.wy;
        const lx = ( dx*cr + dy*sr)/o.scale + S.qw/2;
        const ly = ( dx*sr - dy*cr)/o.scale + S.qh/2;
        const c = sampleFrom(S, lx, ly);
        if(c!=='out') nIn++;
        if(Array.isArray(c)){
          n++;
          if(isText) votes[nearestColor(c[0],c[1],c[2])]++;   // Mehrheit statt Mittelung
          else { aR+=c[0]; aG+=c[1]; aB+=c[2]; }
        }
      }
      if(nIn < SS*SS*.35) continue;
      if(n >= SS*SS*.35){
        if(isText){
          let best=0, bn=-1;
          for(let k2=0;k2<votes.length;k2++) if(votes[k2]>bn){ bn=votes[k2]; best=k2; }
          d[r*b.seats+s] = best;
        } else {
          const t = dith>0 ? (BAYER4[r&3][s&3]/16 - .469) * dith/100 * 72 : 0;
          d[r*b.seats+s] = nearestColor(aR/n+t, aG/n+t, aB/n+t);
        }
        touched[r*b.seats+s]=1;
      }
      else if(fillBg){ d[r*b.seats+s] = o.params.bgCol; touched[r*b.seats+s]=1; }
    }
    for(let k=0;k<Math.max(0,smooth-1);k++) modeFilter(d, b.rows, b.seats, touched);
  }
  return targets;
}
/* Grundschicht + alle Objekte → Sitzraster neu aufbauen */
function recompose(){
  for(let i=0;i<blocks.length;i++) seatData[i].set(baseData[i]);
  for(const o of pressings) applyPressing(o);
  blocks.forEach((_,i)=>updateTexture(i));
  renderAll();
}
function pressOverlay(){
  if(!overlay) return;
  snapshotFull();
  const o = {
    id: pressId++, kind: overlay.kind, canvas: overlay.canvas,
    params: overlay.kind==='image'
      ? Object.assign(domImgParams(), {bgCol: col2})
      : { text: document.getElementById('textInput').value.trim(),
          size: +document.getElementById('textSize').value,
          bend: +document.getElementById('textBend').value,
          font: document.getElementById('textFont').value,
          bg: document.getElementById('textBg').checked,
          fg: col1, bgc: col2 },
    wx: overlay.wx, wy: overlay.wy, scale: overlay.scale, rot: overlay.rot,
    targets: selection.size ? [...selection] : null,
    label: overlay.kind==='text'
      ? `„${document.getElementById('textInput').value.trim().slice(0,18)}“`
      : `Bild ${pressId-1}`,
  };
  pressings.push(o);
  overlay = null;
  document.getElementById('btnPress').disabled = (tool==='fill'||tool==='pattern') ? false : true;
  recompose(); syncPressList();
  toast(`Gepresst — über „Gepresst“ jederzeit änderbar.`);
}
/* Objektliste im Panel */
function syncPressList(){
  const el = document.getElementById('pressList');
  el.innerHTML = '';
  if(!pressings.length){ el.innerHTML = '<div style="font-size:11px;color:var(--faint)">Noch nichts gepresst.</div>'; return; }
  for(const o of [...pressings].reverse()){
    const row = document.createElement('div');
    row.style.cssText='display:flex;align-items:center;gap:6px;font-size:11px;padding:3px 0';
    row.innerHTML = `<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${o.kind==='text'?'𝐓':'🖼'} ${o.label}</span>`;
    const be = document.createElement('button'); be.className='btn'; be.textContent='✎'; be.style.padding='3px 8px';
    be.onclick = ()=> editPressing(o.id);
    const bd = document.createElement('button'); bd.className='btn'; bd.textContent='✕'; bd.style.padding='3px 8px';
    bd.onclick = ()=>{ snapshotFull(); pressings = pressings.filter(p=>p.id!==o.id); recompose(); syncPressList(); toast('Entfernt.'); };
    row.append(be, bd);
    el.appendChild(row);
  }
}
/* Objekt zurück auf den Presstisch */
function editPressing(id){
  const o = pressings.find(p=>p.id===id); if(!o) return;
  snapshotFull();
  pressings = pressings.filter(p=>p.id!==id);
  recompose(); syncPressList();
  selection.clear();
  if(o.targets) o.targets.forEach(t=>selection.add(t));
  syncSel();
  const btn = document.querySelector(`[data-tool=${o.kind}]`);
  btn.click();
  if(o.kind==='text'){
    const p = o.params;
    document.getElementById('textInput').value = p.text;
    document.getElementById('textSize').value = p.size;
    document.getElementById('textBend').value = p.bend;
    document.getElementById('textBg').checked = p.bg;
    document.getElementById('textFont').value = p.font || 'Oswald';
    document.getElementById('textRot').value = Math.round(o.rot*180/Math.PI);
    col1 = p.fg; col2 = p.bgc; syncPal();
    makeTextOverlay();
  } else {
    const p = o.params;
    document.getElementById('imgScale').value = Math.round(o.scale/.55*100);
    document.getElementById('imgRot').value = Math.round(o.rot*180/Math.PI);
    document.getElementById('imgCut').value = p.cut ?? Math.round(Math.max(p.hi||0, p.lo||0, (p.sat||0)/.7));
    document.getElementById('imgBoost').value = p.boost;
    document.getElementById('imgDither').value = p.dither;
    if(p.bgCol !== undefined){ col2 = p.bgCol; syncPal(); }
    ensureOverlay('image', o.canvas);
  }
  overlay.wx = o.wx; overlay.wy = o.wy; overlay.rot = o.rot;
  if(o.kind==='image') overlay.scale = o.scale;
  quantizeOverlay(); buildPreview(); renderOverlay(); syncPressButton();
  toast('Zum Bearbeiten geladen — PRESSEN übernimmt es wieder.');
}
/* ── AUSBAU (Mechanik C): Reihen an den äußersten Rang, dann neuer Rang ── */
const MAX_ROWS = 42;
function standCenter(){ return [D._cx, D._cy]; }
function outerTierOf(stand, seatType){
  const cand = blocks.filter(b=>b.stand===stand && b.type===seatType);
  if(!cand.length) return null;
  const [cx,cy] = standCenter();
  const rad = b => { const m = quadPoint(b.quad,.5,1); return Math.hypot(m[0]-cx,m[1]-cy); };
  const byTier = {};
  for(const b of cand){ (byTier[b.tier]=byTier[b.tier]||[]).push(b); }
  let best=null, bestR=-1;
  for(const t in byTier){
    const r = byTier[t].reduce((a,b)=>a+rad(b),0)/byTier[t].length;
    if(r>bestR){ bestR=r; best=byTier[t]; }
  }
  return best;
}
function growBlockRows(i, add){
  const b = blocks[i];
  const [A,B,C,Dq] = b.quad;
  const dL = [(A[0]-Dq[0])/b.rows, (A[1]-Dq[1])/b.rows];
  const dR = [(B[0]-C[0])/b.rows, (B[1]-C[1])/b.rows];
  b.quad[0] = [A[0]+dL[0]*add, A[1]+dL[1]*add];
  b.quad[1] = [B[0]+dR[0]*add, B[1]+dR[1]*add];
  b.z1 = b.z1 + ((b.z1-b.z0)/b.rows || .77) * add;
  const nb = new Uint8Array((b.rows+add)*b.seats);
  nb.set(baseData[i]);                              // alte Reihen bleiben, neue = 0 (Beton)
  baseData[i] = nb;
  b.rows += add;
  b.capacity += add * b.seats;
  const c = texCache[i]; c.width = b.seats; c.height = b.rows;
  seatData[i] = new Uint8Array(b.rows*b.seats);
}
function addNewTier(refBlocks, seatType, rows){
  const tierName = 'RANG' + (new Set(blocks.map(b=>b.tier)).size + 1);
  for(const rb of refBlocks){
    const [A,B] = rb.quad;
    const dL = [(rb.quad[0][0]-rb.quad[3][0])/rb.rows, (rb.quad[0][1]-rb.quad[3][1])/rb.rows];
    const dR = [(rb.quad[1][0]-rb.quad[2][0])/rb.rows, (rb.quad[1][1]-rb.quad[2][1])/rb.rows];
    const slope = (rb.z1-rb.z0)/rb.rows || .77;
    const nb = {
      id: blocks.length, tier: tierName, stand: rb.stand,
      rows, seats: rb.seats, capacity: rows * rb.seats, type: seatType,
      quad: [ [A[0]+dL[0]*rows, A[1]+dL[1]*rows],
              [B[0]+dR[0]*rows, B[1]+dR[1]*rows],
              [B[0], B[1]], [A[0], A[1]] ],
      z0: rb.z1 + 2, z1: rb.z1 + 2 + slope*rows,
    };
    const renderBlock = renderableBlock(nb, blocks.length);
    blocks.push(renderBlock);
    baseData.push(new Uint8Array(renderBlock.rows * renderBlock.seats));
    seatData.push(new Uint8Array(renderBlock.rows * renderBlock.seats));
    const c = document.createElement('canvas'); c.width=renderBlock.seats; c.height=renderBlock.rows;
    texCache.push(c);
  }
}
function expandStand(stand, seatType, amount){
  const cap = 120000;
  if(D.meta.capacity >= cap) { toast('Maximalkapazität 120.000 erreicht.'); return 0; }
  amount = Math.min(amount, cap - D.meta.capacity);
  snapshotFull();
  let remaining = amount, built = 0;
  let outer = outerTierOf(stand, seatType);
  if(outer){
    const perRow = outer.reduce((a,b)=>a+b.seats,0);
    const room = Math.min(...outer.map(b=>MAX_ROWS-b.rows));
    const want = Math.ceil(remaining/perRow);
    const add = Math.max(0, Math.min(room, want));
    if(add>0){
      for(const b of outer) growBlockRows(b.id, add);
      built += add*perRow; remaining -= add*perRow;
    }
  }
  if(remaining > 0){
    /* neuer Rang über dem äußersten Rang der Tribüne (egal welcher Sitzart) */
    const [cx,cy] = standCenter();
    const rad = b => { const m = quadPoint(b.quad,.5,1); return Math.hypot(m[0]-cx,m[1]-cy); };
    const standBlocks = blocks.filter(b=>b.stand===stand);
    const byTier = {};
    for(const b of standBlocks){ (byTier[b.tier]=byTier[b.tier]||[]).push(b); }
    let ref=null, bestR=-1;
    for(const t in byTier){
      const r = byTier[t].reduce((a,b)=>a+rad(b),0)/byTier[t].length;
      if(r>bestR){ bestR=r; ref=byTier[t]; }
    }
    const perRow = ref.reduce((a,b)=>a+b.seats,0);
    let rows = Math.min(MAX_ROWS, Math.max(4, Math.ceil(remaining/perRow)));
    // Tiefe deckeln: neuer Rang darf die Nachbartribünen um höchstens 35 % überragen
    const rMaxNb = Math.max(...blocks.filter(b=>b.stand!==stand).map(rad));
    const rRef = Math.max(...ref.map(rad));
    const stepPerRow = Math.max(.4, (rRef - Math.min(...ref.map(b=>{
      const m = quadPoint(b.quad,.5,0); return Math.hypot(m[0]-cx,m[1]-cy); }))) / ref[0].rows);
    const roomOut = Math.max(6, (rMaxNb*1.35 - rRef) / stepPerRow);
    rows = Math.min(rows, Math.round(roomOut));
    addNewTier(ref, seatType, rows);
    built += rows*perRow; remaining -= rows*perRow;
  }
  D.meta.capacity = blocks.reduce((a,b)=>a+b.capacity,0);
  const title = document.getElementById('stadiumTitle');
  if(title) title.innerHTML =
    `${D.meta.name} <span>${D.meta.club} · ${D.meta.capacity.toLocaleString('de-DE')} Plätze</span>`;
  recompose(); syncPressList();
  toast(`Ausbau ${stand}: ${built.toLocaleString('de-DE')} ${seatType}-Plätze gebaut.`);
  return built;
}
const expandButton = document.getElementById('btnExpand');
if(expandButton){
  expandButton.addEventListener('click', ()=>{
    expandStand(document.getElementById('expStand').value,
                document.getElementById('expType').value,
                +document.getElementById('expAmount').value);
  });
}

/* ── Export ───────────────────────────────────────────────────── */
async function exportDesign(){
  const out = {version:1, stadium:D.meta.name, palette:PALETTE.map(p=>p[0]),
    blocks: blocks.map((b,i)=>{
      const d = seatData[i].subarray(0, b.capacity), rle=[];
      if(d.length){
        let cur=d[0], n=1;
        for(let k=1;k<d.length;k++){ if(d[k]===cur&&n<65535)n++; else{rle.push([n,cur]);cur=d[k];n=1;} }
        rle.push([n,cur]);
      }
      return {id:b.id, rle};
    })};
  const button = document.getElementById('btnSave');
  button.disabled = true;
  try{
    const response = await fetch(EDITOR.saveUrl, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':EDITOR.csrfToken}, body:JSON.stringify(out)});
    const body = await response.json();
    if(!response.ok) throw new Error(body.error || 'Speichern fehlgeschlagen.');
    toast('Gestaltung gespeichert.');
  }catch(error){ toast(error.message || 'Speichern fehlgeschlagen.'); }
  finally{ button.disabled = false; }
}

/* ── Interaktion ──────────────────────────────────────────────── */
cvOverlay.addEventListener('mousemove', e => {
  const [wx,wy] = s2w(e.offsetX, e.offsetY);
  if(dragOverlay && overlay){ overlay.wx = wx-dragOff[0]; overlay.wy = wy-dragOff[1]; renderOverlay(); return; }
  const b = blockAt(wx,wy);
  const nid = b?b.id:null;
  if(nid!==hoverBlock){ hoverBlock=nid; renderOverlay(); }
  document.getElementById('sbHover').textContent = b
    ? `${b.stand} · ${b.tier}rang · Block ${b.id} · ${b.capacity.toLocaleString('de-DE')} Plätze (${{SITZ:'Sitz',STEH:'Steh',VIP:'VIP'}[b.type]})`
    : '–';
});
cvOverlay.addEventListener('mousedown', e => {
  if(view!=='2d') return;
  const [wx,wy] = s2w(e.offsetX,e.offsetY);
  if(overlay){
    const sc = overlay.scale;
    const dx=wx-overlay.wx, dy=wy-overlay.wy;
    const cr=Math.cos(overlay.rot), sr=Math.sin(overlay.rot);
    const lx=(dx*cr+dy*sr)/sc+overlay.canvas.width/2, ly=(dx*sr-dy*cr)/sc+overlay.canvas.height/2;
    if(lx>=0&&ly>=0&&lx<=overlay.canvas.width&&ly<=overlay.canvas.height){
      dragOverlay=true; dragOff=[wx-overlay.wx, wy-overlay.wy]; return;
    }
  }
  const b = blockAt(wx,wy);
  if(!b){ if(!e.ctrlKey){selection.clear(); syncSel();} return; }
  if(e.ctrlKey){ selection.has(b.id)?selection.delete(b.id):selection.add(b.id); }
  else { selection.clear(); selection.add(b.id); }
  syncSel();
});
window.addEventListener('mouseup', ()=> dragOverlay=false);

function syncSel(){
  const n = selection.size;
  let seats = 0; for(const id of selection) seats += blocks[id].capacity;
  document.getElementById('selStatus').innerHTML = n
    ? `<b>${n}</b> Blöcke · <b>${seats.toLocaleString('de-DE')}</b> Plätze`
    : 'Kein Block gewählt — klick ins Stadion.';
  syncPressButton(); renderOverlay();
}
function syncPressButton(){
  const btn = document.getElementById('btnPress');
  if(tool==='fill'||tool==='pattern') btn.disabled = !selection.size;
  else btn.disabled = !overlay;
}
document.getElementById('btnSelTier').onclick = ()=>{
  const last=[...selection].pop(); if(last==null) return;
  const t=blocks[last].tier, s=blocks[last].stand;
  blocks.forEach(b=>{ if(b.tier===t && b.stand===s) selection.add(b.id); }); syncSel();
};
document.getElementById('btnSelStand').onclick = ()=>{
  const last=[...selection].pop(); if(last==null) return;
  const s=blocks[last].stand;
  blocks.forEach(b=>{ if(b.stand===s) selection.add(b.id); }); syncSel();
};
document.getElementById('btnSelNone').onclick = ()=>{ selection.clear(); syncSel(); };
document.getElementById('btnErase').onclick = ()=>{
  if(!selection.size) return toast('Erst Blöcke wählen.');
  snapshotFull();
  for(const id of selection) baseData[id].fill(0);
  recompose(); toast('Grundschicht der Auswahl auf Beton — Objekte bleiben, „Gepresst“-Liste zum Entfernen.');
};

/* Palette */
const palEl = document.getElementById('palette');
function buildPaletteUI(){
  palEl.innerHTML='';
  PALETTE.forEach((p,i)=>{
    const s = document.createElement('div');
    s.className='swatch'; s.style.background=p[0]; s.title=p[1];
    s.onclick = ()=>{ col1=i; syncPal(); if(overlay&&overlay.kind==='text') makeTextOverlay(); };
    s.oncontextmenu = e=>{ e.preventDefault(); col2=i; syncPal(); if(overlay&&overlay.kind==='text') makeTextOverlay(); };
    palEl.appendChild(s);
  });
}
buildPaletteUI();
document.getElementById('btnAddColor').addEventListener('click', ()=>{
  addCustomColor(document.getElementById('colorPick').value);
});
function syncPal(){
  [...palEl.children].forEach((s,i)=>{
    s.classList.toggle('sel1', i===col1); s.classList.toggle('sel2', i===col2);
  });
  renderOverlay();
}
syncPal();

/* Werkzeuge */
document.querySelectorAll('[data-tool]').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    tool = btn.dataset.tool;
    document.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active', b===btn));
    document.getElementById('subPattern').classList.toggle('open', tool==='pattern');
    document.getElementById('subText').classList.toggle('open', tool==='text');
    document.getElementById('subImage').classList.toggle('open', tool==='image');
    if(tool!=='text' && tool!=='image'){ overlay=null; renderOverlay(); }
    if(tool==='text') makeTextOverlay();
    syncPressButton(); renderOverlay();
  });
});
for(const id of ['patternKind','patternW'])
  document.getElementById(id).addEventListener('input', renderOverlay);
document.getElementById('patternKind').addEventListener('change', renderOverlay);
document.getElementById('textInput').addEventListener('input', makeTextOverlay);
document.getElementById('textBend').addEventListener('input', makeTextOverlay);
document.getElementById('textBg').addEventListener('change', makeTextOverlay);
document.getElementById('btnAlignT').addEventListener('click', alignToStand);
document.getElementById('btnAlignI').addEventListener('click', alignToStand);
document.getElementById('textSize').addEventListener('input', makeTextOverlay);
document.getElementById('textRot').addEventListener('input', makeTextOverlay);
document.getElementById('imgScale').addEventListener('input', syncImageOverlay);
for(const id of ['imgCut','imgBoost','imgDither'])
  document.getElementById(id).addEventListener('input', ()=>{
    if(!overlay) return; quantizeOverlay(); buildPreview(); renderOverlay();
  });
document.getElementById('imgRot').addEventListener('input', syncImageOverlay);
document.getElementById('imgInput').addEventListener('change', e=>{
  const f = e.target.files[0]; if(!f) return;
  const img = new Image();
  img.onload = ()=>{ makeImageOverlay(img); syncPressButton(); };
  img.src = URL.createObjectURL(f);
});

/* Pressen */
document.getElementById('btnPress').onclick = ()=>{
  if(tool==='fill') applyFill();
  else if(tool==='pattern') applyPattern();
  else pressOverlay();
};
document.getElementById('btnUndo').onclick = ()=> applySnap(undoStack, redoStack);
document.getElementById('btnRedo').onclick = ()=> applySnap(redoStack, undoStack);
document.getElementById('btnSave').onclick = exportDesign;

/* Ansicht */
document.getElementById('btnDots').onclick = ()=>{
  dotMode = !dotMode;
  document.getElementById('btnDots').classList.toggle('active', dotMode);
  document.getElementById('btnDots').textContent = dotMode ? '⣿ PUNKTE' : '■ FLÄCHEN';
  renderAll();
};
let r3dPending = false;
function requestRender3D(){
  if(r3dPending) return;
  r3dPending = true;
  requestAnimationFrame(()=>{ r3dPending=false; if(view==='3d') render3D(); });
}
document.getElementById('btn2d').onclick = ()=> setView('2d');
document.getElementById('btn3d').onclick = ()=> setView('3d');
document.getElementById('yawSlider').addEventListener('input', e=>{ yaw3d=+e.target.value; requestRender3D(); });
document.getElementById('roofChk').addEventListener('change', e=>{ roofOn=e.target.checked; render3D(); });
document.getElementById('tiltSlider').addEventListener('input', e=>{ tilt3d=+e.target.value; requestRender3D(); });
document.getElementById('btnShot').addEventListener('click', ()=>{
  const c = document.createElement('canvas'); c.width=W; c.height=H;
  const g = c.getContext('2d');
  g.drawImage(cvBase,0,0); g.drawImage(cvBlocks,0,0);
  c.toBlob(b=>{
    const a = document.createElement('a');
    a.href = URL.createObjectURL(b);
    a.download = `${D.meta.name.replace(/\s+/g,'_')}_ansicht.png`; a.click();
    toast('Ansicht als PNG gespeichert.');
  }, 'image/png');
});
function setView(v){
  view = v;
  document.getElementById('btn2d').classList.toggle('active', v==='2d');
  document.getElementById('btn3d').classList.toggle('active', v==='3d');
  document.getElementById('rot3d').style.display = v==='3d' ? 'flex' : 'none';
  document.getElementById('toolsPanel').style.opacity = v==='3d' ? .35 : 1;
  document.getElementById('toolsPanel').style.pointerEvents = v==='3d' ? 'none' : 'auto';
  renderAll();
}

/* Toast */
let toastT;
function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(()=>t.classList.remove('show'), 2200);
}

/* Schriften vorladen, damit Messung/Pressung sofort stimmen */
for(const f of ['Oswald','Cinzel','Anton','Bebas Neue','Archivo Black','Germania One','Permanent Marker'])
  document.fonts.load(`600 32px "${f}"`).catch(()=>{});
document.getElementById('textFont').addEventListener('change', makeTextOverlay);

/* Geometrie und Gestaltung gehören immer zum angemeldeten Verein. */
window.addEventListener('resize', resize);
(async function boot(){
  try{
    const [geometryResponse, designResponse] = await Promise.all([
      fetch(EDITOR.geometryUrl, {credentials:'same-origin'}),
      fetch(EDITOR.designUrl, {credentials:'same-origin'}),
    ]);
    const geometry = await geometryResponse.json();
    if(!geometryResponse.ok) throw new Error(geometry.error || 'Geometrie konnte nicht geladen werden.');
    const design = designResponse.ok ? await designResponse.json() : {};
    initStadium(geometry, design);
    buildPaletteUI(); syncPal(); resize();
  }catch(error){
    const title = document.getElementById('stadiumTitle');
    if(title) title.textContent = error.message || 'Editor nicht verfügbar';
    toast(error.message || 'Editor nicht verfügbar');
  }
})();
