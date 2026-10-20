// Explicit, opt-in partitions of retained OSM footprints. No height inference.
const fail = (detail='') => { throw new Error(
  `buildingParts benötigt eindeutige Teilgrundrisse und belegte NHN-Höhen. ${detail}`); };
const cross = (a,b,c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const area = p => Math.abs(p.reduce((s,a,i) => s+cross(p[0],a,p[(i+1)%p.length]),0))/2;
const number = (n,limit) => Number.isFinite(n) && Math.abs(n)<=limit;
const text = s => typeof s==='string' && s.trim().length>0;

function triangles(THREE, raw) {
  if (!Array.isArray(raw) || raw.length<3 || raw.length>257 ||
      raw.some(p=>!Array.isArray(p)||p.length!==2||!p.every(n=>number(n,10000)))) fail();
  const p=raw.map(p=>[...p]);
  if(p[0].every((n,i)=>n===p.at(-1)[i])) p.pop();
  if(p.length<3 || new Set(p.map(p=>JSON.stringify(p))).size!==p.length || area(p)<1e-10) fail();
  const on=(a,b,p)=>cross(a,b,p)===0 &&
    p[0]>=Math.min(a[0],b[0]) && p[0]<=Math.max(a[0],b[0]) &&
    p[1]>=Math.min(a[1],b[1]) && p[1]<=Math.max(a[1],b[1]);
  for(let i=0;i<p.length;i++) for(let j=i+1;j<p.length;j++){
    if(j===i+1 || (i===0&&j===p.length-1)) continue;
    const a=p[i],b=p[(i+1)%p.length],c=p[j],d=p[(j+1)%p.length];
    if((cross(a,b,c)*cross(a,b,d)<0 && cross(c,d,a)*cross(c,d,b)<0) ||
        on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b)) fail();
  }
  const faces=THREE.ShapeUtils.triangulateShape(p.map(p=>new THREE.Vector2(...p)),[]);
  const tris=faces.map(f=>f.map(i=>p[i]));
  if(!tris.length || Math.abs(tris.reduce((s,t)=>s+area(t),0)-area(p))>1e-6) fail();
  return tris;
}

function intersection(a,b) {
  let poly=a;
  const sign=cross(...b)>0?1:-1;
  for(let i=0;i<3&&poly.length;i++){
    const u=b[i],v=b[(i+1)%3],out=[];
    for(let j=0;j<poly.length;j++){
      const p=poly[j],q=poly[(j+1)%poly.length];
      const sp=sign*cross(u,v,p),sq=sign*cross(u,v,q);
      if(sp>=0) out.push(p);
      if((sp<0&&sq>0)||(sp>0&&sq<0)){
        const t=sp/(sp-sq); out.push(p.map((n,k)=>n+t*(q[k]-n)));
      }
    }
    poly=out;
  }
  return poly.length>=3?area(poly):0;
}
const overlap = (a,b) => a.reduce((s,t)=>s+b.reduce((v,u)=>v+intersection(t,u),0),0);

export function validateBuildingParts(THREE,data) {
  const result=new Map();
  if(!Object.hasOwn(data,'buildingParts')) return result;
  const c=data.buildingParts;
  if(!c || c.version!==1 || c.verticalDatum!=='DHHN2016 / NHN (EPSG:7837)' ||
      !number(c.referenceNHN,1000) || !text(c.source) ||
      !data.groundElevation || !number(data.groundLevel,30) ||
      c.referenceNHN!==data.heightEvidence?.terrainReferenceNHN ||
      !Array.isArray(c.groups) || !c.groups.length || c.groups.length>32) fail();
  const ids=new Set();
  for(const g of c.groups){
    const i=g?.buildingIndex;
    if(!Number.isInteger(i)||i<0||i>=(data.buildings||[]).length||result.has(i)||
        !text(g.osm)||g.osm!==data.buildingIds?.[i]||
        !data.heightEvidence?.buildings?.some(row=>row.index===i&&row.osm===g.osm&&
          row.status==='unmeasured_retained_envelope')||
        !number(data.buildingHeights?.[i],100)||data.buildingHeights[i]<=0||
        g.residualStatus!=='unmeasured_retained_envelope'||
        !Array.isArray(g.parts)||g.parts.length<2||g.parts.length>64||
        !Array.isArray(g.residualPolygons)||g.residualPolygons.length>512) fail();
    const parent=triangles(THREE,data.buildings[i]), children=[], entries=[];
    for(const part of g.parts){
      if(!part || !text(part.lodId)||ids.has(part.lodId)||!text(part.file)||
          !number(part.baseNHN,1000)||!number(part.roofNHN,1000)||
          !number(part.height,100)||part.height<1||
          Math.abs(part.roofNHN-part.baseNHN-part.height)>.01||
          part.sourceAttributes?.DatenquelleDachhoehe!=='1000'||
          part.sourceAttributes?.DatenquelleBodenhoehe!=='1100'||
          part.srsName!=='urn:adv:crs:ETRS89_UTM32*DE_DHHN2016_NH'||
          !Array.isArray(part.polygons)||!part.polygons.length||part.polygons.length>512) fail();
      ids.add(part.lodId);
      for(const poly of part.polygons){
        if(children.length>=512) fail();
        children.push(triangles(THREE,poly));
        entries.push({poly,height:part.height,
          base:part.baseNHN-c.referenceNHN-data.groundLevel,
          top:part.roofNHN-c.referenceNHN-data.groundLevel,lodId:part.lodId});
      }
    }
    for(const poly of g.residualPolygons){
      if(children.length>=512) fail();
      children.push(triangles(THREE,poly));
      entries.push({poly,height:data.buildingHeights[i]});
    }
    if(children.length>512 || children.reduce((s,t)=>s+t.length,0)>2048) fail();
    const parentArea=parent.reduce((s,t)=>s+area(t),0);
    let sum=0;
    for(let j=0;j<children.length;j++){
      const a=children[j],size=a.reduce((s,t)=>s+area(t),0);
      if(Math.abs(overlap(a,parent)-size)>1e-5) fail(`Teilfläche außerhalb von ${g.osm}.`);
      for(let k=0;k<j;k++) if(overlap(a,children[k])>1e-5) fail(`Überlappende Teilflächen in ${g.osm}.`);
      sum+=size;
    }
    if(Math.abs(sum-parentArea)>1e-5) fail(`Unvollständige Partition von ${g.osm}.`);
    result.set(i,entries);
  }
  return result;
}
