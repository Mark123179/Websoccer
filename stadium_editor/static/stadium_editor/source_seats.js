/* Shared source/2D registration. No generated motifs and no economic writes. */
(function(root) {
  'use strict';
  const cache = new Map();
  const tierOf = name => ({1:'UNTER',2:'MITTEL',3:'OBER'})[
    /^C_(?:back|front|left|right)([123])_/.exec(name)?.[1]];
  const cell = (x,z) => `${Math.floor(x/1.5)},${Math.floor(z/1.5)}`;
  function nativePoint(point, frame, axes={NORD:'+z',WEST:'-x'}) {
    const [cx,cy]=frame.fieldC || [0,0], a=frame.axisTheta || 0;
    const dx=point[0]-cx, dy=point[1]-cy;
    const u=dx*Math.cos(a)+dy*Math.sin(a), v=-dx*Math.sin(a)+dy*Math.cos(a);
    const result=[0,0];
    for(const [axis,value] of [[axes.NORD,u],[axes.WEST,v]])
      result[axis[1]==='x'?0:1]=(axis[0]==='-'?-1:1)*value;
    return result;
  }
  function quadPoint(q,u,v) {
    return [0,1].map(k=>(1-v)*(q[3][k]+u*(q[2][k]-q[3][k]))+
      v*(q[0][k]+u*(q[1][k]-q[0][k])));
  }
  function quadUV(q,x,z) {
    let u=.5,v=.5;
    for(let i=0;i<8;i++) {
      const p=quadPoint(q,u,v), du=[0,1].map(k=>(1-v)*(q[2][k]-q[3][k])+v*(q[1][k]-q[0][k]));
      const dv=[0,1].map(k=>(1-u)*(q[0][k]-q[3][k])+u*(q[1][k]-q[2][k]));
      const d=du[0]*dv[1]-du[1]*dv[0];
      if(Math.abs(d)<1e-9) return null;
      const ex=x-p[0],ez=z-p[1];
      u+=(ex*dv[1]-ez*dv[0])/d;v+=(du[0]*ez-du[1]*ex)/d;
    }
    return [u,v];
  }
  function decode(block) {
    const values=new Uint8Array(block.rows*block.seats);let at=0;
    for(const [n,c] of block.rle || []) {values.fill(c,at,Math.min(values.length,at+n));at+=n;}
    return values;
  }
  function registration(blocks, frame, axes) {
    const grids=new Map();
    const prepared=blocks.map(block=>({...block,
      nativeQuad:block.quad.map(p=>nativePoint(p,frame,axes)), values:block.values || decode(block)}));
    for(const b of prepared) {
      const xs=b.nativeQuad.map(p=>p[0]),zs=b.nativeQuad.map(p=>p[1]);
      for(let x=Math.floor(Math.min(...xs)/8);x<=Math.floor(Math.max(...xs)/8);x++)
        for(let z=Math.floor(Math.min(...zs)/8);z<=Math.floor(Math.max(...zs)/8);z++) {
          const key=`${b.tier}:${x},${z}`;
          if(!grids.has(key))grids.set(key,[]);grids.get(key).push(b);
        }
    }
    return {blocks:prepared, ring:ringFromBlocks(prepared), lookup(x,z,tier) {
      for(const b of grids.get(`${tier}:${Math.floor(x/8)},${Math.floor(z/8)}`) || []) {
        const uv=quadUV(b.nativeQuad,x,z);
        if(!uv || uv.some(v=>v<-.00001 || v>1.00001))continue;
        const row=Math.min(b.rows-1,Math.max(0,Math.floor(uv[1]*b.rows)));
        const seat=Math.min(b.seats-1,Math.max(0,Math.floor(uv[0]*b.seats)));
        return {block:b,index:row*b.seats+seat};
      }
      return null;
    }};
  }
  const angleBin=(x,z)=>((Math.floor((Math.atan2(z,x)+Math.PI)*180/Math.PI)%360)+360)%360;
  function makeRing(samples) {
    const ring={};
    for(const tier of ['UNTER','MITTEL','OBER']){
      const rows=Array.from({length:360},()=>[]);
      for(const [x,z,t] of samples)if(t===tier)rows[angleBin(x,z)].push(Math.hypot(x,z));
      ring[tier]=rows.map((values,i)=>{
        // A one-degree cell has enough source vertices for robust end radii.
        // Include neighbouring cells at blueprint corners without inventing stands.
        for(let d=1;values.length<6 && d<=3;d++)
          values=[...values,...rows[(i+d)%360],...rows[(i-d+360)%360]];
        if(!values.length)return null;
        values.sort((a,b)=>a-b);
        return [values[Math.floor((values.length-1)*.01)],
          values[Math.ceil((values.length-1)*.99)]];
      });
    }
    return ring;
  }
  function ringFromBlocks(blocks) {
    const samples=[];
    for(const b of blocks)
      for(let u=0;u<=24;u++)for(const v of [0,1]){
        const p=quadPoint(b.nativeQuad,u/24,v);
        samples.push([...p,b.tier]);
      }
    return makeRing(samples);
  }
  function warp(point,tier,from,to){
    const [x,z]=point,bin=angleBin(x,z),a=from[tier]?.[bin],b=to[tier]?.[bin];
    if(!a || !b || a[1]-a[0]<2 || b[1]-b[0]<2)return null;
    const r=Math.hypot(x,z),target=b[0]+(r-a[0])*(b[1]-b[0])/(a[1]-a[0]);
    return [x*target/r,z*target/r];
  }
  function sourceIndex(manifest, buffer) {
    const grids=new Map(), triangles=[], samples=[];
    for(const entry of manifest.meshes) {
      if(!entry.name.startsWith(manifest.calibration.crowdPrefix))continue;
      const tier=tierOf(entry.name);
      if(!tier)throw Error(`Ungeklärter Quellrang: ${entry.name}`);
      const p=new Float32Array(buffer,entry.positionOffset,entry.vertexCount*3);
      const uv=new Float32Array(buffer,entry.uvOffset,entry.vertexCount*2);
      for(let j=0;j<entry.vertexCount;j+=2)samples.push([p[j*3],p[j*3+2],tier]);
      for(const part of entry.parts) {
        const indices=new Uint32Array(buffer,part.indexOffset,part.indexCount);
        for(let i=0;i<indices.length;i+=3) {
          const ids=[indices[i],indices[i+1],indices[i+2]];
          const q=ids.map(j=>[p[j*3],p[j*3+2]]);
          const det=(q[1][0]-q[0][0])*(q[2][1]-q[0][1])-(q[2][0]-q[0][0])*(q[1][1]-q[0][1]);
          if(Math.abs(det)<.0001)continue; // Vertical backs cannot supply a plan colour.
          const t={q,det,uv:ids.map(j=>[uv[j*2],uv[j*2+1]]),part,tier};
          const idx=triangles.push(t)-1;
          const xs=q.map(p=>p[0]),zs=q.map(p=>p[1]);
          for(let x=Math.floor(Math.min(...xs)/1.5);x<=Math.floor(Math.max(...xs)/1.5);x++)
            for(let z=Math.floor(Math.min(...zs)/1.5);z<=Math.floor(Math.max(...zs)/1.5);z++){
              const key=`${tier}:${x},${z}`;
              if(!grids.has(key))grids.set(key,[]);grids.get(key).push(idx);
            }
        }
      }
    }
    return {triangles,ring:makeRing(samples), sample(x,z,tier) {
      const candidates=grids.get(`${tier}:${cell(x,z)}`) || [];
      let best=null,dist=Infinity;
      for(const i of candidates) {
        const t=triangles[i], [a,b,c]=t.q;
        const v=((x-a[0])*(c[1]-a[1])-(c[0]-a[0])*(z-a[1]))/t.det;
        const w=((b[0]-a[0])*(z-a[1])-(x-a[0])*(b[1]-a[1]))/t.det;
        let weights=[Math.max(0,1-v-w),Math.max(0,v),Math.max(0,w)];
        const sum=weights.reduce((a,b)=>a+b,0);weights=weights.map(v=>v/sum);
        const sx=weights.reduce((s,v,j)=>s+v*t.q[j][0],0),sz=weights.reduce((s,v,j)=>s+v*t.q[j][1],0);
        const d=(x-sx)**2+(z-sz)**2;
        if(d<dist && d<=2.25) {
          dist=d;best={part:t.part,uv:[0,1].map(k=>weights.reduce((s,v,j)=>s+v*t.uv[j][k],0)),distance:Math.sqrt(d)};
          if(d<1e-10)break;
        }
      }
      return best;
    }};
  }
  async function load(presentation) {
    if(!cache.has(presentation.modelUrl))cache.set(presentation.modelUrl,(async()=>{
      const response=await fetch(presentation.modelUrl);
      if(!response.ok)throw Error('Originalmodell nicht verfügbar.');
      const manifest=await response.json();
      if(manifest.clubFmiId!==915 || manifest.sourceSha256!==presentation.sourceSha256)
        throw Error('Originalzuordnung gehört nicht zur freigegebenen Modellquelle.');
      const base=new URL('.',new URL(presentation.modelUrl,location.href));
      const binary=await fetch(new URL('geometry.bin',base));
      if(!binary.ok)throw Error('Originalgeometrie nicht verfügbar.');
      const buffer=await binary.arrayBuffer();
      const index=sourceIndex(manifest,buffer), images=new Map();
      const names=[...new Set(index.triangles.map(t=>t.part.texture).filter(Boolean))];
      await Promise.all(names.map(async name=>{
        const image=new Image();image.src=new URL(name,base).href;await image.decode();
        const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
        const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);
        images.set(name,{width:image.width,height:image.height,data:ctx.getImageData(0,0,image.width,image.height).data});
      }));
      return {manifest,buffer,index,images};
    })().catch(error=>{cache.delete(presentation.modelUrl);throw error;}));
    return cache.get(presentation.modelUrl);
  }
  function originalColors(source, blocks, frame) {
    let mapped=0,total=0,maxDistance=0;
    const registered=registration(blocks,frame,source.manifest.calibration.surroundingsAxes);
    const rgb=registered.blocks.map(b=>{
      const out=new Uint8ClampedArray(b.rows*b.seats*3);
      for(let r=0;r<b.rows;r++)for(let s=0;s<b.seats;s++){
        total++;const at=(r*b.seats+s)*3;
        const editorPoint=quadPoint(b.nativeQuad,(s+.5)/b.seats,(r+.5)/b.rows);
        const mappedPoint=warp(editorPoint,b.tier,registered.ring,source.index.ring);
        const hit=mappedPoint && source.index.sample(...mappedPoint,b.tier);
        let color=[96,106,116];
        if(hit){
          mapped++;maxDistance=Math.max(maxDistance,hit.distance);
          const image=source.images.get(hit.part.texture);
          if(image){
            const u=Math.max(0,Math.min(image.width-1,Math.floor(hit.uv[0]*image.width)));
            const v=Math.max(0,Math.min(image.height-1,Math.floor(hit.uv[1]*image.height)));
            color=[...image.data.slice((v*image.width+u)*4,(v*image.width+u)*4+3)];
          }else color=hit.part.color.map(c=>Math.round(c*255));
        }
        out.set(color,at);
      }
      return out;
    });
    return {rgb,mapped,total,maxDistance};
  }
  root.StadiumSourceSeats={tierOf,nativePoint,quadPoint,quadUV,decode,registration,sourceIndex,load,originalColors,warp};
})(globalThis);
