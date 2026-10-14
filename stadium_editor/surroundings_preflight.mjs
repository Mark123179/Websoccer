// Read-only CPU preflight. No WebGLRenderer, DOM, network or source rewriting.
// Isolate each source object so one bad feature cannot hide subsequent errors.
import * as THREE from './static/stadium_editor/stage/vendor/three.module.js';
import {createSurroundingsChecks, editorPointToDortmund, resolveSurroundingsAxes,
  SURROUNDINGS_AXES_DEFAULT} from './static/stadium_editor/dortmund_surroundings.js';
import {pathToFileURL} from 'node:url';

export const MAX_INPUT_BYTES = 128 * 1024 * 1024;

export async function readPreflightInput(stream, maxBytes = MAX_INPUT_BYTES) {
  let raw = '', bytes = 0;
  stream.setEncoding('utf8');
  for await (const chunk of stream) {
    bytes += Buffer.byteLength(chunk, 'utf8');
    if (bytes > maxBytes) throw new Error('Prüfpaket zu groß.');
    raw += chunk;
  }
  return raw;
}

export function inspectSurroundings(data = {}, frame = {}, axes = SURROUNDINGS_AXES_DEFAULT) {
  const findings = [];
  const report = () => ({
    ok: !findings.some(f => f.severity === 'error'),
    terrainDeclared: Object.hasOwn(data, 'groundLevel') || Object.hasOwn(data, 'groundCutout'),
    findings,
  });
  const add = (severity, path, code, message) => findings.push({severity, path, code, message});
  if (!data || typeof data !== 'object' || Array.isArray(data))
    return {ok: false, terrainDeclared: false, findings: [
      {severity: 'error', path: 'data', code: 'invalid_data', message: 'Umfelddaten müssen ein Objekt sein.'},
    ]};
  try {
    resolveSurroundingsAxes(axes);
    editorPointToDortmund([0, 0], frame, axes);
  } catch (error) {
    add('error', 'frame/axes', 'invalid_frame', error.message);
    return report();
  }
  let checks;
  try {
    checks = createSurroundingsChecks(THREE, data, frame, axes);
  } catch (error) {
    add('error', 'groundLevel/groundCutout', 'invalid_terrain', error.message);
    return report();
  }
  for (const layer of ['green', 'water', 'roads', 'buildings', 'trees']) {
    const values = data[layer] || [];
    if (!Array.isArray(values)) {
      add('error', layer, 'invalid_layer', 'Die Umfeldliste muss ein Array sein.');
      continue;
    }
    for (let index = 0; index < values.length; index++) {
      try {
        // Same production checks and triangulator, without CPU/GPU geometry.
        // Only the current feature is retained; no catalog-size mesh buffers.
        let omitted = false;
        if (layer === 'green' || layer === 'water')
          omitted = checks.surface(values[index], layer, index).omitted;
        else if (layer === 'buildings')
          checks.building(values[index], data.buildingHeights?.[index] ?? 9, index);
        else if (layer === 'trees') checks.tree(values[index]);
        else {
          const road = checks.road(values[index]);
          for (const footprint of checks.roadFootprints(road, index)) {
            // Consume every strip and join; never sample or cap source objects.
          }
        }
        if (omitted)
          add('info', `${layer}[${index}]`, 'surface_inside_cutout',
            'Fläche liegt vollständig in groundCutout und wird nur beim Rendern ausgeblendet; Quelle bleibt unverändert.');
      } catch (error) {
        add('error', `${layer}[${index}]`, 'renderer_rejected',
          error.message);
      }
    }
  }
  return report();
}

// Input via stdin only: package JSON is data, never executable code.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const input = JSON.parse(await readPreflightInput(process.stdin));
    console.log(JSON.stringify(inspectSurroundings(input.data, input.frame, input.axes)));
  } catch {
    console.error('Die lokale Rendererprüfung konnte nicht ausgeführt werden.');
    process.exitCode = 2;
  }
}
