// Offline bridge: use the actual renderer, not a second terrain interpolator.
import {readFileSync} from 'node:fs';
import {elevationSampler} from '../stadium_editor/static/stadium_editor/measured_ground.js';
import {editorPointToDortmund} from '../stadium_editor/static/stadium_editor/dortmund_surroundings.js';
import {bridgeHeightEvidence} from '../stadium_editor/static/stadium_editor/bridge_height_evidence.js';

const {presentation: p, points} = JSON.parse(readFileSync(0, 'utf8'));
const sample = elevationSampler(p.surroundings.groundElevation);
if (!p.surroundings.groundElevation) throw new Error('Missing measured display grid');
process.stdout.write(JSON.stringify({
  bridgeHeightEvidence: bridgeHeightEvidence(p.surroundings),
  offsets: points.map(([x,z]) => sample(x,z)),
  roads: p.surroundings.roads.map(road => road.p.map(point =>
    editorPointToDortmund(point, p.frame, p.calibration.surroundingsAxes))),
}));
