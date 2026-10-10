// Read-only bridge from the newly rendered approved frame to the map audit.
// Never re-apply the old cutaway camera or reuse old roof masks.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {verifyProbeImage} from './probe_image_evidence.mjs';

export function verifyGeoExport(output, approvedPath){
const current=JSON.parse(fs.readFileSync(`${output}/verification.json`,'utf8'));
const daylight=current.states.filter(state=>!state.variant || state.variant==='day');
const approved=JSON.parse(fs.readFileSync(approvedPath,'utf8')).states[0];
if(JSON.stringify(current.fitted.format)!==JSON.stringify([1880,940]))
  throw new Error('Unexpected export format.');
if(daylight.length!==4)throw new Error('Expected both clubs and both roof states in daylight.');
const combinations=new Set();
for(const state of daylight){
  combinations.add(`${state.club}:${state.roof}`);
  if(!['dortmund','elversberg'].includes(state.club) ||
     state.orientation?.modelTurnDegrees!==180 ||
     JSON.stringify(state.corners)!==JSON.stringify(approved.corners) ||
     JSON.stringify(state.projection)!==JSON.stringify(approved.projection) ||
     JSON.stringify(state.pose)!==JSON.stringify(approved.pose))
    throw new Error('New orientation or approved camera parity missing.');
  if(!state.roof && state.visibleRoofMeshes!==0)throw new Error('Roof-off failed.');
   for(const role of ['render','silhouette'])verifyProbeImage(output,state,current.fitted,role);
}
if(combinations.size!==4)throw new Error('Duplicated club/roof state.');
return {
  format:current.fitted.format,position:current.fitted.position,
  projection:approved.projection,worldInverse:approved.pose,
  corners:approved.corners,modelTurnDegrees:180,
};
}

if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
  const output='generated-artifacts/stadium-main-stand-back-probe';
  const camera=verifyGeoExport(output,'generated-artifacts/stadium-middle-probe/verification.json');
  fs.writeFileSync(`${output}/camera_exact.json`,JSON.stringify(camera,null,2));
  console.log('Render/silhouette content, east/northeast orientation and exact approved 75% camera verified.');
}
