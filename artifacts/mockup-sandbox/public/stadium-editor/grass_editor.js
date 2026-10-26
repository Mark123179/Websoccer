import * as THREE from 'three';
import {createGrassPilotMaterial, GRASS_PRESETS} from './grass_pilot_material.js?v=2';

export const validGrass = value => typeof value === 'string'
  && (value === 'bestand' || Object.hasOwn(GRASS_PRESETS, value));

/** Draft state is local to the editor. Only the existing save POST persists it. */
export function createGrassDraft(initial = 'bestand') {
  let saved = validGrass(initial) ? initial : 'bestand', selected = saved;
  return {
    get selected() { return selected; },
    get saved() { return saved; },
    get dirty() { return selected !== saved; },
    select(value) {
      if (!validGrass(value)) throw new Error('Unbekannte Rasenvariante.');
      selected = value;
    },
    reset() { selected = saved; },
    commit(value) {
      if (!validGrass(value)) throw new Error('Unbekannte Rasenvariante.');
      saved = value; // A newer selection while the POST was pending stays a draft.
    },
  };
}

/** Albedo for Canvas2D comes from the exact approved shader, not an approximation. */
export async function createEditorGrass(assets) {
  const renderer = new THREE.WebGLRenderer({antialias: false, preserveDrawingBuffer: true});
  renderer.setSize(1050, 680);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-52.5, 52.5, 34, -34, .1, 200);
  camera.position.set(0, 100, 0);
  camera.up.set(0, 0, -1);
  camera.lookAt(0, 0, 0);
  const geometry = new THREE.PlaneGeometry(105, 68).rotateX(-Math.PI / 2);
  const original = new THREE.MeshBasicMaterial();
  const mesh = new THREE.Mesh(geometry, original);
  scene.add(mesh);
  let flat;
  try {
    flat = await createGrassPilotMaterial({
      renderer, sceneRoot: scene, pitchMaterials: new Set([original]), grassUnlit: true,
    }, assets);
  } catch (error) {
    geometry.dispose(); original.dispose(); renderer.dispose();
    throw error;
  }
  let selected = 'bestand', mounted = null, mountedRoot = null, pending = null, disposed = false;
  const canvas = renderer.domElement;
  function select(value) {
    if (!validGrass(value)) throw new Error('Unbekannte Rasenvariante.');
    selected = value;
    flat.select(value);
    if (value !== 'bestand') renderer.render(scene, camera);
    mounted?.select(value);
  }
  async function apply(api) {
    if (disposed || !api) return;
    const stage = api.stage || api;
    const root = stage.sceneRoot || stage.model || stage.scene;
    if (!root) throw new Error('Das 3D-Spielfeld ist nicht zugänglich.');
    if (root !== mountedRoot) {
      if (pending?.root === root) return pending.promise;
      mounted?.dispose(); mounted = null; mountedRoot = root;
      const targets = [];
      let projection;
      if (!stage.pitchMaterials) {
        root.traverse(object => {
          // Only the verified grass base, never pitch markings, goals or goal nets.
          if (!object.isMesh || !/^(?:ORIGINAL_|SOURCE_).*_pitch_0(?:[._]|$)/i.test(object.name)) return;
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((_, slot) => targets.push({
            mesh: object, ...(Array.isArray(object.material) ? {slot} : {}),
          }));
        });
        if (!targets.length) throw new Error('Keine getrennte Original-Rasenfläche gefunden.');
        const bounds = targets[0].mesh.geometry;
        bounds.computeBoundingBox();
        const box = bounds.boundingBox, center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        projection = size.z > size.x
          ? `vec2((52.5+(${center.z.toFixed(6)})-position.z)/105.0,`
            + `(position.x-(${center.x.toFixed(6)})+34.0)/68.0)`
          : `vec2((52.5+(${center.x.toFixed(6)})-position.x)/105.0,`
            + `(position.z-(${center.z.toFixed(6)})+34.0)/68.0)`;
      }
      const promise = createGrassPilotMaterial({
        ...stage, sceneRoot: root,
        ...(stage.pitchMaterials ? {} : {pitchTargets: targets, grassProjection: projection}),
      }, assets).then(controller => {
        if (disposed || root !== mountedRoot) { controller.dispose(); return; }
        mounted = controller; mounted.select(selected); stage.render?.();
      });
      pending = {root, promise};
      try { await promise; }
      catch (error) { if (mountedRoot === root) mountedRoot = null; throw error; }
      finally { if (pending?.promise === promise) pending = null; }
    } else {
      if (pending?.root === root) await pending.promise;
      mounted?.select(selected);
      stage.render?.();
    }
  }
  return {
    select, apply,
    get canvas() { return selected === 'bestand' ? null : canvas; },
    dispose() {
      disposed = true; mounted?.dispose(); flat.dispose();
      geometry.dispose(); original.dispose(); renderer.dispose();
    },
  };
}
