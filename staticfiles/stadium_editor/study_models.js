import * as THREE from 'three';
import {createStadiumStage} from './stage/stadium_stage.js?v=study-3';
import {previewSupportsMaterial, sourceOpaqueColor} from './dortmund_source_materials.js?v=2';
import {TICKER_ROOF_NAMES} from './dortmund_ticker_roof.js?v=1';
import {studyPreset, dortmundAdapter} from './study_camera.js?v=3';
import {addStudyGoals} from './study_pitch_details.js?v=1';
import {mountStadiumStage} from './stadium_stage_adapter.js?v=3';

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
export async function mountStudyModel({host, club, source, concept}) {
  if (club === 'elversberg') {
    const scene = source?.scene || source?.liveScene || source;
    if (!scene?.schema || scene?.frame?.name !== 'pitch' ||
        scene?.surroundings?.style !== 'elversberg-blueprint') {
      throw new Error('Die kanonische Elversberg-Live-Scene oder ihr Blueprint-Umfeld fehlt.');
    }
    const api = await mountStadiumStage({
      element: host, scene, mode: 'live', camera: 'match', day: true,
      preset: studyPreset(concept), roofVisible: true,
      surroundings: true, coordinateRotation: 0,
    });
    if (api.kind !== 'three' || !api.stage) {
      api.dispose?.();
      throw api.reason || new Error('Die gemeinsame Elversberg-Szene konnte nicht gestartet werden.');
    }
    const pitchGroup = api.stage.sceneRoot.children.find(group => group.isGroup &&
      group.children.some(mesh => api.stage.pitchMaterials.has(mesh.material)));
    pitchGroup?.traverse(mesh => { if (mesh.isMesh) mesh.userData.studyPitch = true; });
    addStudyGoals(api.stage.sceneRoot);
    const model = new THREE.Group();
    const canvas = api.stage.renderer.domElement;
    return {
      stage: api.stage, api, canvas, model, roofMeshes: [],
      allMeshes: [],
      setRoof(visible) { return api.update({roofVisible: Boolean(visible)}); },
      dispose() { api.dispose(); },
    };
  }
  const canvas = document.createElement('canvas');
  host.append(canvas);
  const width = host.clientWidth, height = host.clientHeight;
  const stage = createStadiumStage({canvas, width, height, scene: emptyScene(),
    drawPitch: true, preset: studyPreset(concept), view: 'match',
    surroundings: false, facade: false, floodlight: false, coordinateRotation: 0});
  const pitchGroup = stage.sceneRoot.children.find(group => group.isGroup &&
    group.children.some(mesh => stage.pitchMaterials.has(mesh.material)));
  pitchGroup?.traverse(mesh => { if(mesh.isMesh)mesh.userData.studyPitch=true; });
  let stripe=0;
  for(const material of stage.pitchMaterials) material.color.set(stripe++%2?'#2d7b3b':'#337f42');
  addStudyGoals(stage.sceneRoot);
  stage.renderer.localClippingEnabled = true;
  const model = dortmundAdapter();
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
          materials.at(-1).userData.sourceMaterial = part.material;
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
