// Read-only bridge from the newly rendered approved frame to the map audit.
// Never re-apply the old cutaway camera or reuse old roof masks.
import fs from 'node:fs';

const output='generated-artifacts/stadium-main-stand-back-probe';
const current=JSON.parse(fs.readFileSync(`${output}/verification.json`,'utf8'));
const daylight=current.states.filter(state=>!state.variant || state.variant==='day');
const approved=JSON.parse(fs.readFileSync(
  'generated-artifacts/stadium-middle-probe/verification.json','utf8')).states[0];
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
  const prefix=`${output}/${state.club}_${state.roof?'roof':'no_roof'}`;
  for(const suffix of ['.png','_silhouette.png']){
    if(!fs.existsSync(prefix+suffix))throw new Error(`Missing fresh render: ${prefix+suffix}`);
  }
}
if(combinations.size!==4)throw new Error('Duplicated club/roof state.');
fs.writeFileSync(`${output}/camera_exact.json`,JSON.stringify({
  format:current.fitted.format,position:current.fitted.position,
  projection:approved.projection,worldInverse:approved.pose,
  corners:approved.corners,modelTurnDegrees:180,
},null,2));
console.log('Fresh east/northeast renders and exact approved 75% camera verified.');
