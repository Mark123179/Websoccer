// Explicit, opt-in partitions of retained OSM footprints. No height inference.
const fail = (detail='') => { throw new Error(
  `buildingParts benötigt eindeutige Teilgrundrisse und belegte NHN-Höhen. ${detail}`); };
const cross = (a,b,c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const area = p => Math.abs(p.reduce((s,a,i) => s+cross(p[0],a,p[(i+1)%p.length]),0))/2;
const number = (n,limit) => Number.isFinite(n) && Math.abs(n)<=limit;
const text = s => typeof s==='string' && s.trim().length>0;

function triangles(THREE, raw, limit=10000) {
  if (!Array.isArray(raw) || raw.length<3 || raw.length>257 ||
      raw.some(p=>!Array.isArray(p)||p.length!==2||!p.every(n=>number(n,limit)))) fail();
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

function validateRoofs(THREE, part, reference, groundLevel) {
  if(Object.hasOwn(part,'roofStatus')){
    if(part.roofStatus==='rejected_retained_envelope'){
      if(Object.hasOwn(part,'roofSurfaces')||!text(part.roofRejection))fail('Dach-Ausschluss.');
    }else if(part.roofStatus!=='official_surfaces'||!Object.hasOwn(part,'roofSurfaces'))
      fail('Dach-Status.');
  }
  if (!Object.hasOwn(part,'roofSurfaces')) return undefined;
  if (!Array.isArray(part.roofSurfaces)||!part.roofSurfaces.length||
      part.roofSurfaces.length>128||!number(part.roofMinNHN,1000)||
      part.roofMinNHN<=part.baseNHN||part.roofMinNHN>part.roofNHN) fail('RoofSurface-Niveau.');
  const parent=part.polygons.flatMap(p=>triangles(THREE,p)), children=[], surfaces=[], walls=[];
  const keys=new Set(), sourceZ=[];
  const edges=part.polygons.flatMap(raw=>{
    const p=raw[0].every((n,i)=>n===raw.at(-1)[i])?raw.slice(0,-1):raw;
    return p.map((a,i)=>[a,p[(i+1)%p.length]]);
  });
  const edgeKey=([a,b])=>[JSON.stringify(a),JSON.stringify(b)].sort().join('|');
  const counts=new Map();
  edges.forEach(e=>counts.set(edgeKey(e),(counts.get(edgeKey(e))||0)+1));
  const boundary=edges.filter(e=>counts.get(edgeKey(e))===1);
  const planar=ring=>{
    const o=ring[0]; let best;
    for(let i=1;i<ring.length-1;i++){
      const a=ring[i].map((v,k)=>v-o[k]),b=ring[i+1].map((v,k)=>v-o[k]);
      const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
      if(!best||Math.abs(n[2])>Math.abs(best[2]))best=n;
    }
    if(!best||Math.abs(best[2])<1e-8)fail('Vertikale Dachfläche.');
    const height=p=>o[2]-(best[0]*(p[0]-o[0])+best[1]*(p[1]-o[1]))/best[2];
    if(ring.some(p=>Math.abs(height(p)-p[2])>.01))fail('Nicht ebene Dachfläche.');
    return height;
  };
  for(const roof of part.roofSurfaces){
    if(!roof||roof.lodId!==part.lodId||roof.file!==part.file||
        !text(roof.surfaceId)||!text(roof.polygonId)||
        !Array.isArray(roof.sourceRingsUTM)||!roof.sourceRingsUTM.length||
        roof.sourceRingsUTM.length>64||!Array.isArray(roof.polygons)||roof.polygons.length>512)
      fail('RoofSurface-Quelle.');
    const key=JSON.stringify([roof.surfaceId,roof.polygonId]);
    if(keys.has(key))fail('Doppelte Dachquelle.');keys.add(key);
    let sourcePlane;const sourceRings=[];
    for(const ring of roof.sourceRingsUTM){
      if(!Array.isArray(ring)||ring.length<4||ring.length>257||
          sourceZ.length+ring.length>16384||
          ring.some(p=>!Array.isArray(p)||p.length!==3||!p.every(n=>number(n,1e7)))||
          !ring[0].every((v,i)=>v===ring.at(-1)[i]))fail('Dach-Quellring.');
      sourcePlane??=planar(ring);
      const tris=triangles(THREE,ring.map(p=>p.slice(0,2)),1e7);
      const size=tris.reduce((s,t)=>s+area(t),0);
      if(sourceRings.length){
        if(Math.abs(overlap(tris,sourceRings[0])-size)>1e-5)fail('Dach-Quellloch außerhalb.');
        for(let i=1;i<sourceRings.length;i++)
          if(overlap(tris,sourceRings[i])>1e-5)fail('Überlappende Dach-Quelllöcher.');
      }
      sourceRings.push(tris);
      if(ring.some(p=>Math.abs(sourcePlane(p)-p[2])>.01||
          p[2]<part.roofMinNHN-.01||p[2]>part.roofNHN+.01))fail('Dach-Quellhöhe.');
      sourceZ.push(...ring.map(p=>p[2]));
    }
    for(const ring of roof.polygons){
      if(!Array.isArray(ring)||ring.length<4||ring.some(p=>!Array.isArray(p)||p.length!==3||
          !p.every(n=>number(n,10000))||p[2]<part.roofMinNHN-.01||p[2]>part.roofNHN+.01)||
          !ring[0].every((v,i)=>v===ring.at(-1)[i]))fail('Dachring.');
      planar(ring);
      const xy=ring.map(p=>p.slice(0,2)), tris=triangles(THREE,xy);
      if(children.length>=512)fail('Zu viele Dachflächen.');
      children.push(tris);
      surfaces.push(ring.slice(0,-1).map(([x,y,z])=>[x,y,z-reference-groundLevel]));
      // Only boundary intersections form schematic walls, never internal ridges.
      for(let i=0;i<ring.length-1;i++){
        const a=ring[i],b=ring[i+1],dx=b[0]-a[0],dy=b[1]-a[1],length2=dx*dx+dy*dy;
        if(length2<1e-16)continue;
        for(const [u,v] of boundary){
          if(Math.abs(cross(a,b,u))/Math.sqrt(length2)>1e-6||
              Math.abs(cross(a,b,v))/Math.sqrt(length2)>1e-6)continue;
          const t=p=>((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length2;
          const lo=Math.max(0,Math.min(t(u),t(v))),hi=Math.min(1,Math.max(t(u),t(v)));
          if(hi-lo>1e-9)walls.push([lo,hi].map(t=>[
            a[0]+t*dx,a[1]+t*dy,a[2]+t*(b[2]-a[2])-reference-groundLevel]));
        }
      }
    }
  }
  if(!sourceZ.length||Math.abs(Math.max(...sourceZ)-part.roofNHN)>.01||
      Math.abs(Math.min(...sourceZ)-part.roofMinNHN)>.01)fail('Dach-Extrema.');
  let sum=0;
  children.forEach((a,i)=>{
    const size=a.reduce((s,t)=>s+area(t),0);sum+=size;
    if(Math.abs(overlap(a,parent)-size)>1e-5)fail('Dach außerhalb Teilkörper.');
    for(let j=0;j<i;j++)if(overlap(a,children[j])>1e-5)fail('Überlappende Dächer.');
  });
  if(Math.abs(sum-parent.reduce((s,t)=>s+area(t),0))>1e-5)fail('Unvollständiges Dach.');
  return {surfaces,walls};
}

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
      const roofGeometry=validateRoofs(THREE,part,c.referenceNHN,data.groundLevel);
      for(const [pi,poly] of part.polygons.entries()){
        if(children.length>=512) fail();
        children.push(triangles(THREE,poly));
        entries.push({poly,height:part.height,
          base:part.baseNHN-c.referenceNHN-data.groundLevel,
          top:part.roofNHN-c.referenceNHN-data.groundLevel,lodId:part.lodId,
          surveyedRoof:roofGeometry!==undefined,roofGeometry:pi===0?roofGeometry:undefined});
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
