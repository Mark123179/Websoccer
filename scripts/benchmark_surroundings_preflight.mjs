// Run each mode in a separate process for meaningful peak-RSS comparisons:
// node --max-old-space-size=512 scripts/benchmark_surroundings_preflight.mjs [--large|--huge] [--max-cutout] [--legacy]
import assert from 'node:assert/strict';
import * as THREE from '../stadium_editor/static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings} from '../stadium_editor/static/stadium_editor/dortmund_surroundings.js';
import {inspectSurroundings} from '../stadium_editor/surroundings_preflight.mjs';
import {surroundingsCatalog, appendLateConflicts, LARGE_CATALOG}
  from '../stadium_editor/tests_js/fixtures/surroundings_catalog.mjs';

const large = process.argv.includes('--large'), huge = process.argv.includes('--huge');
const legacy = process.argv.includes('--legacy');
const start = performance.now();
const options = huge ? {...LARGE_CATALOG,trees:1000000,surfaces:25000,roads:5000,buildings:5000}
  : large ? {...LARGE_CATALOG} : {};
if (process.argv.includes('--max-cutout')) options.cutoutVertices = 256;
const data = appendLateConflicts(surroundingsCatalog(options));
const layers = ['green','water','roads','buildings','trees'];
const expectedPaths = layers.map(layer => `${layer}[${data[layer].length - 1}]`);
const beginCheck = performance.now();
let findings;
if (legacy) {
  // Original full-renderer-per-object execution strategy, kept only as an oracle.
  findings = [];
  for (const layer of layers) {
    for (let index = 0; index < data[layer].length; index++) {
      let environment;
      try {
        environment = buildDortmundSurroundings(THREE, {
          groundLevel:data.groundLevel, groundCutout:data.groundCutout,
          [layer]:[data[layer][index]],
          ...(layer === 'buildings' ? {buildingHeights:[data.buildingHeights[index]]} : {}),
        });
        if (environment.group.userData.terrain?.omitted[layer]?.length)
          findings.push(`${layer}[${index}]`);
      } catch {
        findings.push(`${layer}[${index}]`);
      } finally { environment?.dispose(); }
    }
  }
} else findings = inspectSurroundings(data).findings.map(f => f.path);
assert.deepEqual(findings, expectedPaths);
console.log(JSON.stringify({
  mode:legacy ? 'renderer-per-object' : 'shared-cpu-checks',
  counts:Object.fromEntries(layers.map(layer => [layer,data[layer].length])),
  cutoutVertices:data.groundCutout.length,
  elapsedMs:Math.round(performance.now() - start),
  checkMs:Math.round(performance.now() - beginCheck),
  peakRssMiB:Math.round(process.resourceUsage().maxRSS / 1024 * 10) / 10,
  findings,
}));
