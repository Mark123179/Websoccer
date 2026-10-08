import * as THREE from 'three';
import {createStadiumStage} from './stage/stadium_stage.js?v=study-2';
import {previewSupportsMaterial, sourceOpaqueColor} from './dortmund_source_materials.js';
import {TICKER_ROOF_NAMES} from './dortmund_ticker_roof.js?v=1';
import {studyPreset, dortmundAdapter} from './study_camera.js?v=1';
import {addStudyGoals} from './study_pitch_details.js?v=1';

const modelBase = new URL('./dortmund_original/', import.meta.url);
let modelTask;
async function originalData() {
  if (!modelTask) {
    modelTask = (async () => {
      const responses = await Promise.all(['manifest.json', 'geometry.bin'].map(file =>
        fetch(new URL(file, modelBase))));
      if (responses.some(response => !response.ok)) throw new Error('Originalmodell fehlt.');
      const [manifest, binary] = await Promise.all([responses[0].json(), responses[1].arrayBuffer()]);
      const loader = new THREE.TextureLoader(), maps = {};
      await Promise.all(manifest.textures.map(async name => {
        const texture = await loader.loadAsync(new URL(`${name}.webp`, modelBase).href);
        texture.colorSpace = THREE.SRGBColorSpace; maps[name] = texture;
      }));
      return {manifest, binary, maps};
    })();
    modelTask.catch(() => { modelTask = null; });
  }
  return modelTask;
}

function emptyScene() {
  return {blocks: [], palette: ['#172129'], mainStand: 'SUED', roof: {}, steckbrief: {}, outline: []};
}
function elversbergSource(source) {
  const copy = structuredClone(source);
  // A right-handed 180-degree rotation puts the actual south/main stand on
  // the camera side; playing coordinates are shared, not club-dependent.
  const point = p => [-p[0], -p[1], ...p.slice(2)];
  copy.blocks.forEach(block => { block.quad = block.quad.map(point); });
  copy.outline = copy.outline.map(point);
  const roofs = copy.roof.segments.map(segment => ({...segment, quad: segment.quad.map(point)}));
  copy.roof = {};
  copy.steckbrief = {};
  copy.surroundings = {};
  return {copy, roofs};
}

export async function mountStudyModel({host, club, source, concept}) {
  const canvas = document.createElement('canvas');
  host.append(canvas);
  const width = host.clientWidth, height = host.clientHeight;
  const elversberg = club === 'elversberg' ? elversbergSource(source) : null;
  const stage = createStadiumStage({canvas, width, height, scene: elversberg?.copy || emptyScene(),
    drawPitch: true, preset: studyPreset(concept), view: 'match',
    surroundings: false, facade: false, floodlight: false, coordinateRotation: 0});
  const pitchGroup = stage.sceneRoot.children.find(group => group.isGroup &&
    group.children.some(mesh => stage.pitchMaterials.has(mesh.material)));
  pitchGroup?.traverse(mesh => { if(mesh.isMesh)mesh.userData.studyPitch=true; });
  let stripe=0;
  for(const material of stage.pitchMaterials) material.color.set(stripe++%2?'#2d7b3b':'#337f42');
  addStudyGoals(stage.sceneRoot);
  stage.renderer.localClippingEnabled = true;
  const roofGroup = new THREE.Group(), model = dortmundAdapter();
  const allMeshes = [], roofMeshes = [];
  if (club === 'dortmund') {
    try {
      const {manifest, binary, maps} = await originalData();
      for (const entry of manifest.meshes) {
        if (entry.name.startsWith('st081_pitch_')) continue; // canonical shared 105×68 field
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(
          new Float32Array(new Float32Array(binary, entry.positionOffset, entry.vertexCount * 3)), 3));
        geometry.setAttribute('uv', new THREE.BufferAttribute(
          new Float32Array(binary, entry.uvOffset, entry.vertexCount * 2), 2));
        const indices = [], materials = [];
        for (const part of entry.parts) {
          if (!previewSupportsMaterial(part)) continue;
          const start = indices.length;
          indices.push(...new Uint32Array(binary, part.indexOffset, part.indexCount));
          geometry.addGroup(start, part.indexCount, materials.length);
          const name = part.material.toLowerCase();
          const color = sourceOpaqueColor(part) || (part.texture ? '#ffffff' :
            name.includes('pllr') ? '#c4ad32' : name.includes('seat') ? '#a99327' : '#72797d');
          materials.push(new THREE.MeshStandardMaterial({
            color, map: maps[part.texture] || null, roughness: .87, metalness: .06,
            side: THREE.DoubleSide, clippingPlanes: [new THREE.Plane(new THREE.Vector3(0,0,-1), 35)],
          }));
        }
        if (!indices.length) { geometry.dispose(); continue; }
        geometry.setIndex(indices); geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(geometry, materials);
        mesh.name = entry.name; mesh.userData.sourcePathId = entry.pathId;
        model.add(mesh); allMeshes.push(mesh);
        if (TICKER_ROOF_NAMES.has(entry.name)) roofMeshes.push(mesh);
      }
      stage.sceneRoot.add(model);
    } catch (error) { stage.dispose(); canvas.remove(); throw error; }
  } else {
    for (const segment of elversberg.roofs) {
      if (segment.quad.reduce((sum, p) => sum + p[1], 0) / 4 > 35) continue;
      const points = segment.quad.map((p, i) => [-p[0], segment.heights?.[i] ?? segment.z, p[1]]);
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(points.flat(), 3));
      geometry.setIndex([0,1,2,0,2,3]); geometry.computeVertexNormals();
      const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
        color: '#818b91', side: THREE.DoubleSide, roughness: .9,
      }));
      roofGroup.add(mesh); roofMeshes.push(mesh);
    }
    stage.sceneRoot.add(roofGroup);
  }
  // Disable the standard renderer's preview lighting and emissive fill.
  // The study owns its explicit, auditable daylight and declared fixture lights.
  stage.sceneRoot.traverse(object => {
    if (object.isLight) object.intensity = 0;
    if (object.isMesh) {
      // The standard editor keeps seats and pitch marks self-lit. The isolated
      // night study must not bypass the declared lights with bright materials.
      if (object.material?.isMeshBasicMaterial) {
        const old=object.material;
        object.material=new THREE.MeshLambertMaterial({color:old.color,side:old.side});
        old.dispose();
      }
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        if (material.emissive) material.emissiveIntensity = 0;
      }
    }
  });
  return {stage, canvas, model, roofMeshes, allMeshes,
    setRoof(visible) { roofMeshes.forEach(mesh => { mesh.visible = visible; }); },
    dispose() { stage.dispose(); canvas.remove(); },
  };
}

export function disposeStudySourceCache() {
  modelTask?.then(data => Object.values(data.maps).forEach(texture => texture.dispose())).catch(() => {});
  modelTask = null;
}
