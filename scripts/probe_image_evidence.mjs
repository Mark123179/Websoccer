// Export-time byte evidence, not a signature against a hostile manifest author.
import fs from 'node:fs';
import {createHash} from 'node:crypto';

const sha256=bytes=>createHash('sha256').update(bytes).digest('hex');

export function imageContext(state, fitted){
  return {club:state.club,roof:state.roof,variant:state.variant??'day',
    orientation:state.orientation,projection:state.projection,pose:state.pose,
    corners:state.corners,format:fitted.format,position:fitted.position};
}

function binding(contextJson, bytes){
  return createHash('sha256').update(contextJson).update('\0').update(bytes).digest('hex');
}

export function writeProbeImage(directory, state, fitted, role, bytes){
  const variant=state.variant??'day';
  const stem=`${state.club}_${state.roof?'roof':'no_roof'}${variant==='day'?'':`_${variant}`}`;
  const file=`${stem}${role==='silhouette'?'_silhouette':''}.png`;
  const contextJson=JSON.stringify({...imageContext(state,fitted),role});
  const evidence={version:1,file,contextJson,sha256:sha256(bytes),
    bindingSha256:binding(contextJson,bytes)};
  fs.writeFileSync(`${directory}/${file}`,bytes);
  return evidence;
}

export function verifyProbeImage(directory, state, fitted, role){
  const evidence=state.imageEvidence?.[role];
  if(!evidence || evidence.version!==1)throw new Error(`Missing image evidence: ${state.club}/${role}; re-export required.`);
  const expected=JSON.stringify({...imageContext(state,fitted),role});
  if(evidence.contextJson!==expected)throw new Error(`Image context mismatch: ${state.club}/${role}`);
  const variant=state.variant??'day';
  const stem=`${state.club}_${state.roof?'roof':'no_roof'}${variant==='day'?'':`_${variant}`}`;
  if(evidence.file!==`${stem}${role==='silhouette'?'_silhouette':''}.png`)
    throw new Error(`Image filename mismatch: ${state.club}/${role}`);
  const bytes=fs.readFileSync(`${directory}/${evidence.file}`);
  if(sha256(bytes)!==evidence.sha256 || binding(evidence.contextJson,bytes)!==evidence.bindingSha256)
    throw new Error(`Image content mismatch: ${evidence.file}; stale or swapped export.`);
  if(bytes.length<24 || !bytes.subarray(0,8).equals(Buffer.from('89504e470d0a1a0a','hex')) ||
     bytes.toString('ascii',12,16)!=='IHDR' ||
     bytes.readUInt32BE(16)!==fitted.format[0] || bytes.readUInt32BE(20)!==fitted.format[1])
    throw new Error(`Image format/dimensions mismatch: ${evidence.file}`);
  return bytes;
}
