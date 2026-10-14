// Read-only CPU preflight. No WebGLRenderer, DOM, network or source rewriting.
// Isolate each source object so one bad feature cannot hide subsequent errors.
import * as THREE from './static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings, editorPointToDortmund, resolveSurroundingsAxes,
  SURROUNDINGS_AXES_DEFAULT} from './static/stadium_editor/dortmund_surroundings.js';
import {validateSurroundingsGround} from './static/stadium_editor/surroundings_ground.js';
import {pathToFileURL} from 'node:url';

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
  const terrain = {};
  try {
    validateSurroundingsGround(data);
    for (const key of ['groundLevel', 'groundCutout'])
      if (Object.hasOwn(data, key)) terrain[key] = data[key];
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
      const isolated = {...terrain, [layer]: [values[index]]};
      if (layer === 'buildings') isolated.buildingHeights = [data.buildingHeights?.[index]];
      let environment;
      try {
        // This executes the EXACT production transform, polygon relation,
        // rendered road strips + octagonal joins, height checks and tree test.
        environment = buildDortmundSurroundings(THREE, isolated, frame, axes);
        if (environment.group.userData.terrain?.omitted[layer]?.length)
          add('info', `${layer}[${index}]`, 'surface_inside_cutout',
            'Fläche liegt vollständig in groundCutout und wird nur beim Rendern ausgeblendet; Quelle bleibt unverändert.');
      } catch (error) {
        add('error', `${layer}[${index}]`, 'renderer_rejected',
          error.message.replaceAll(`${layer}[0]`, `${layer}[${index}]`));
      } finally {
        environment?.dispose();
      }
    }
  }
  return report();
}

// Input via stdin only: package JSON is data, never executable code.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    let raw = '';
    for await (const chunk of process.stdin) raw += chunk;
    const input = JSON.parse(raw);
    console.log(JSON.stringify(inspectSurroundings(input.data, input.frame, input.axes)));
  } catch {
    console.error('Die lokale Rendererprüfung konnte nicht ausgeführt werden.');
    process.exitCode = 2;
  }
}
