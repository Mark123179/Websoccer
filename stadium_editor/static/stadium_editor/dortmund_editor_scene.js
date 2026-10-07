import * as THREE from 'three';
import {buildConcept, warpShell, ROOF_NAMES, SHELL_NAMES} from './dortmund_concept.js?v=49';
import {previewSupportsMaterial, sourceOpaqueColor} from './dortmund_source_materials.js';
import {addReconstructedFacade, reconstructedFacadeVisible, sourceFacadePreviewColor} from './dortmund_reconstructed_facade.js?v=2';
import {buildDortmundSurroundings} from './dortmund_surroundings.js?v=51';
import {tickerCameraFrame, tickerHeightElevation, TICKER_ELEVATION, TICKER_AZIMUTH} from './dortmund_ticker_camera.js?v=2';

const ASSET_BASE = new URL('./dortmund_original/', import.meta.url);
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const shade = name => {
  const n = name.toLowerCase();
  if (n.includes('pitch') || n.includes('dtmnd')) return '#31734a';
  if (n.includes('seat')) return '#b3a04c';
  if (n.includes('pllr') || n.includes('iron') || n.includes('trus')) return '#c6ac42';
  if (n.includes('roof') || n.includes('irpl')) return '#a3a9a7';
  if (n.includes('glas')) return '#667d81';
  if (n.includes('sgbd') || n.includes('coat_band')) return '#d9bd49';
  if (n.includes('wall') || n.includes('cncr')) return '#777f7e';
  return '#8a9290';
};
const url = file => new URL(file, ASSET_BASE).href;
const sideOrder = ['NORD', 'SUED', 'OST', 'WEST'];

export async function mountDortmundScene({
  element, onStatus = () => {}, surroundings, frame: editorFrame,
  includeSurroundings = true, interactive = true, autoRotate = false, compact = false,
  transparentBackground = false, compactZoom = 1, verticalFraming = 0, tickerPreview = false,
}) {
  if (!window.WebGLRenderingContext) throw new Error('WebGL ist auf diesem Gerät nicht verfügbar.');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      antialias: true, powerPreference: 'high-performance', alpha: transparentBackground,
    });
  } catch (_) {
    throw new Error('WebGL konnte nicht gestartet werden.');
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  renderer.localClippingEnabled = tickerPreview;
   renderer.domElement.setAttribute('aria-label', tickerPreview
     ? 'Feste Stadionansicht des Signal Iduna Parks mit geöffnetem Vordergrund und waagerechtem Spielfeld'
     : interactive
    ? 'Drehbarer Unity-Mesh-Auszug des Signal Iduna Parks mit vereinfachten Materialien und konzeptioneller Erweiterung'
    : 'Automatisch rotierende 3D-Ansicht des Signal Iduna Parks');
  element.replaceChildren(renderer.domElement);
  const scene = new THREE.Scene();
  const nightEnvironment = '#030b0d';
  scene.background = transparentBackground ? null : new THREE.Color(nightEnvironment);
  scene.fog = transparentBackground ? null : new THREE.Fog(nightEnvironment, 850, 1800);
  if (transparentBackground) renderer.setClearColor(0x000000, 0);
  const world = new THREE.Group();
  scene.add(world);
  scene.add(new THREE.HemisphereLight(0xe7f1f2, 0x344045, 1.35));
  const sun = new THREE.DirectionalLight(0xfff3d4, 1.5);
  sun.position.set(-135, 210, 100);
  scene.add(sun);
  const camera = tickerPreview
    ? new THREE.OrthographicCamera(-150, 150, 90, -90, 1, 2400)
    : new THREE.PerspectiveCamera(42, 1, 1, 2400);
  const target = new THREE.Vector3(0, 25, 0);
   let azimuth = tickerPreview ? TICKER_AZIMUTH : .88;
   let elevation = tickerPreview ? TICKER_ELEVATION : .56, distance = 490;
  let frame = 0, disposed = false, concept = null, colorBands = null, facade = null, environment = null, roofOn = true;
  let lastWeights = '', lastColors = '';
  const geometries = [], textures = [], materials = new Map(), facadeMaterials = new Map();
  const facadeSourceParts = [], roof = [], shell = [];
  let resizeObserver;
  let animationActive = true, lastAnimationTime = null;
  const fitCompactCamera = () => {
    const bounds = new THREE.Box3().setFromObject(world);
    if (bounds.isEmpty()) return;
    target.copy(bounds.getCenter(new THREE.Vector3()));
    const corners = [];
    for (const x of [bounds.min.x, bounds.max.x])
      for (const y of [bounds.min.y, bounds.max.y])
        for (const z of [bounds.min.z, bounds.max.z])
          corners.push(new THREE.Vector3(x, y, z).sub(target));
    const tanY = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const tanX = tanY * camera.aspect;
    let required = 150;
    // Fit the entire rotation, not just the initial angle of the small tile.
    for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 16) {
      const direction = new THREE.Vector3(
        Math.sin(angle) * Math.cos(elevation), Math.sin(elevation),
        Math.cos(angle) * Math.cos(elevation));
      const right = new THREE.Vector3(Math.cos(angle), 0, -Math.sin(angle));
      const up = new THREE.Vector3(
        -Math.sin(angle) * Math.sin(elevation), Math.cos(elevation),
        -Math.cos(angle) * Math.sin(elevation));
      for (const corner of corners) {
        const depth = corner.dot(direction);
        required = Math.max(required,
          Math.abs(corner.dot(right)) / tanX + depth,
          Math.abs(corner.dot(up)) / tanY + depth);
      }
    }
    distance = required * 1.10 / compactZoom;
  };
  const positionCamera = () => {
    camera.position.set(target.x + distance * Math.sin(azimuth) * Math.cos(elevation),
      target.y + distance * Math.sin(elevation),
      target.z + distance * Math.cos(azimuth) * Math.cos(elevation));
    camera.lookAt(target);
  };
  const resize = () => {
    const width = element.clientWidth, height = element.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    if (tickerPreview) {
      // Pitch's goal-to-goal Z axis is horizontal from this fixed side view.
       const framing = tickerCameraFrame(camera.aspect, elevation);
       camera.left = framing.left;
       camera.right = framing.right;
       camera.top = framing.top;
       camera.bottom = framing.bottom;
       target.set(0, framing.targetY, 0);
    }
    // Shift projection, not the canvas or model: shared viewers stay unchanged.
    if (verticalFraming) camera.setViewOffset(width, height, 0,
      height * clamp(verticalFraming, -0.25, 0.25), width, height);
    else camera.clearViewOffset();
    camera.updateProjectionMatrix();
    if (compact) fitCompactCamera();
    if (!animationActive) render();
  };
  const render = () => { positionCamera(); renderer.render(scene, camera); };
  const controls = renderer.domElement;
  let dragging = false, lastX = 0, lastY = 0;
  const down = e => { dragging = true; lastX = e.clientX; lastY = e.clientY; controls.setPointerCapture(e.pointerId); };
  const up = () => { dragging = false; };
  const move = e => {
    if (!dragging) return;
    azimuth += (e.clientX - lastX) * .006;
    elevation = clamp(elevation + (e.clientY - lastY) * .004, .15, 1.35);
    lastX = e.clientX; lastY = e.clientY;
  };
  const wheel = e => { e.preventDefault(); distance = clamp(distance * Math.exp(e.deltaY * .0008), 190, 1300); };
  if (interactive) {
    controls.addEventListener('pointerdown', down);
    controls.addEventListener('pointerup', up);
    controls.addEventListener('pointercancel', up);
    controls.addEventListener('pointermove', move);
    controls.addEventListener('wheel', wheel, {passive: false});
  }
  const dispose = () => {
    disposed = true;
    cancelAnimationFrame(frame);
    resizeObserver?.disconnect();
    controls.removeEventListener('pointerdown', down);
    controls.removeEventListener('pointerup', up);
    controls.removeEventListener('pointercancel', up);
    controls.removeEventListener('pointermove', move);
    controls.removeEventListener('wheel', wheel);
    if (concept) concept.dispose();
    facade?.dispose();
    environment?.dispose();
    if (colorBands) {
      colorBands.traverse(object => { object.geometry?.dispose(); object.material?.dispose(); });
    }
    geometries.forEach(item => item.dispose());
    materials.forEach(item => item.dispose());
    facadeMaterials.forEach(item => item.dispose());
    textures.forEach(item => item.dispose());
    renderer.dispose();
    if (controls.parentNode === element) element.removeChild(controls);
  };
  try {
    if (includeSurroundings) {
      environment = buildDortmundSurroundings(THREE, surroundings, editorFrame);
      scene.add(environment.group);
    }
    const [manifestResponse, binaryResponse] = await Promise.all([
      fetch(url('manifest.json')), fetch(url('geometry.bin')),
    ]);
    if (!manifestResponse.ok || !binaryResponse.ok) throw new Error('Originalmeshes konnten nicht geladen werden.');
    const manifest = await manifestResponse.json(), binary = await binaryResponse.arrayBuffer();
    if (manifest.format !== 'unity-mesh-binary-v1') throw new Error('Unbekanntes Format der Originalmeshes.');
    const loader = new THREE.TextureLoader(), imageMaps = {};
    await Promise.all(manifest.textures.map(name => new Promise((resolve, reject) => {
      loader.load(url(`${name}.webp`), texture => {
        texture.colorSpace = THREE.SRGBColorSpace;
        textures.push(texture); imageMaps[name] = texture; resolve();
      }, undefined, () => reject(new Error(`Originaltextur ${name} fehlt.`)));
    })));
    for (const entry of manifest.meshes) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(
        new Float32Array(new Float32Array(binary, entry.positionOffset, entry.vertexCount * 3)), 3));
      geometry.setAttribute('uv', new THREE.BufferAttribute(
        new Float32Array(binary, entry.uvOffset, entry.vertexCount * 2), 2));
      const indices = [], groupMaterials = [], sourcePartSlots = [];
      for (const part of entry.parts) {
        if (!previewSupportsMaterial(part)) continue;
        const start = indices.length;
        indices.push(...new Uint32Array(binary, part.indexOffset, part.indexCount));
        geometry.addGroup(start, part.indexCount, groupMaterials.length);
        const key = part.texture || part.material;
        if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({
          color: part.texture ? '#ffffff' : sourceOpaqueColor(part) || shade(part.material),
          roughness: .83, metalness: .08, side: THREE.DoubleSide,
          ...(part.texture ? {map: imageMaps[part.texture]} : {}),
        }));
        const original = materials.get(key);
        const previewColor = sourceFacadePreviewColor(entry.name, sourceOpaqueColor(part), true);
        if (previewColor && previewColor !== sourceOpaqueColor(part)) {
          if (!facadeMaterials.has(key)) {
            const preview = original.clone();
            preview.color.set(previewColor);
            preview.roughness = .9;
            preview.metalness = 0;
            facadeMaterials.set(key, preview);
          }
          sourcePartSlots.push({index: groupMaterials.length, original, preview: facadeMaterials.get(key)});
          groupMaterials.push(facadeMaterials.get(key));
        } else {
          groupMaterials.push(original);
        }
      }
      if (!indices.length) { geometry.dispose(); continue; }
      geometry.setIndex(indices);
      geometry.computeVertexNormals();
      geometries.push(geometry);
      const mesh = new THREE.Mesh(geometry, groupMaterials);
      mesh.name = `ORIGINAL_${entry.name}`;
      world.add(mesh);
      sourcePartSlots.forEach(slot => facadeSourceParts.push({mesh, ...slot}));
      if (ROOF_NAMES.has(entry.name)) {
        roof.push(mesh);
        // Cutaway copies do not change the original roof materials.
        const cutaway = groupMaterials.map(original => {
          const copy = original.clone();
          copy.transparent = true; copy.opacity = .026; copy.depthWrite = false;
          return copy;
        });
        mesh.userData.cutaway = cutaway;
        mesh.userData.original = groupMaterials;
      }
      if (SHELL_NAMES.has(entry.name)) shell.push({
        geometry, source: new Float32Array(geometry.attributes.position.array),
      });
    }
    facade = addReconstructedFacade(THREE, world);
    if (tickerPreview) {
      // GPU clipping cuts even source triangles spanning the entire front roof.
      // Keep source indices/UVs intact. Exempt the measured pitch meshes so
      // their full playing surface survives the deeper roof/truss cut.
      const frontCut = new THREE.Plane(new THREE.Vector3(1, 0, 0), 32);
      world.traverse(object => {
        if (!object.isMesh) return;
        const list = Array.isArray(object.material) ? object.material : [object.material];
        list.forEach(material => {
          if (object.name.startsWith('ORIGINAL_st081_pitch_')) {
            material.clippingPlanes = [];
            material.color.set(object.name === 'ORIGINAL_st081_pitch_0' ? '#438c32' : '#f3f5e8');
            if (object.name === 'ORIGINAL_st081_pitch_1') {
              material.emissive.set('#b9c3a9');
              material.emissiveIntensity = .35;
            }
            material.needsUpdate = true;
            return;
          }
          material.clippingPlanes = [frontCut];
          material.needsUpdate = true;
        });
      });
    }
    if (disposed) return null;
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(element); resize();
    onStatus('Unity-Mesh-Auszug + rekonstruierte, nicht quellbelegte Bestandsfassade');
    const animate = timestamp => {
      if (disposed || !animationActive) return;
      if (autoRotate && lastAnimationTime !== null)
        azimuth += Math.min((timestamp - lastAnimationTime) / 1000, .1) * .12;
      lastAnimationTime = timestamp;
      render();
      frame = requestAnimationFrame(animate);
    };
    animate(performance.now());
    return {
      kind: 'three', stage: {renderer, render}, dispose,
      setTickerCameraHeight(degrees) {
        if (disposed || !tickerPreview) return;
        elevation = tickerHeightElevation(degrees);
        resize();
      },
      setActive(active) {
        if (disposed || Boolean(active) === animationActive) return;
        animationActive = Boolean(active);
        lastAnimationTime = null;
        if (animationActive) frame = requestAnimationFrame(animate);
        else cancelAnimationFrame(frame);
      },
       update({weights, designColors, roofVisible, fullConcept, cameraPreset, orbit, day, floodlight} = {}) {
        if (disposed) return Promise.resolve();
         facade.group.visible = reconstructedFacadeVisible(facade.group.visible, fullConcept);
         // A scene-mode switch must restore the untouched source preview in Rundum.
         facadeSourceParts.forEach(({mesh, index, original, preview}) => {
           mesh.material[index] = facade.group.visible ? preview : original;
         });
        if (weights && JSON.stringify(weights) !== lastWeights) {
          lastWeights = JSON.stringify(weights);
          const next = Object.fromEntries(sideOrder.map(side => [side, clamp(Number(weights[side]) || 0, 0, 1)]));
          if (concept) { world.remove(concept.group); concept.dispose(); concept = null; }
          for (const {geometry, source} of shell) warpShell(geometry, source, next);
          if (Object.values(next).some(Boolean)) {
            concept = buildConcept(THREE, next);
            world.add(concept.group);
          }
          roof.forEach(mesh => {
            mesh.material = concept ? mesh.userData.cutaway : mesh.userData.original;
          });
           onStatus(fullConcept ? 'Unity-Mesh-Auszug + Rundum-Konzept · Entwurf, keine Bestandsfassade'
             : concept ? 'Unity-Mesh-Auszug + rekonstruierte Bestandsfassade + graue Konzeptbauteile'
             : 'Unity-Mesh-Auszug + rekonstruierte, nicht quellbelegte Bestandsfassade');
        }
        if (designColors && JSON.stringify(designColors) !== lastColors) {
          lastColors = JSON.stringify(designColors);
          if (colorBands) {
            world.remove(colorBands);
            colorBands.traverse(object => { object.geometry?.dispose(); object.material?.dispose(); });
          }
          colorBands = new THREE.Group();
          colorBands.name = 'EDITOR_DESIGN_COLOR_BANDS';
          for (const [stand, hex] of Object.entries(designColors)) {
            if (!sideOrder.includes(stand) || !/^#[0-9a-f]{6}$/i.test(hex)) continue;
            const xSide = stand === 'SUED' || stand === 'NORD';
            const sign = stand === 'SUED' || stand === 'OST' ? 1 : -1;
            const across = xSide ? 104 : 83;
            const radial = xSide ? 89 : 113;
            const vertices = xSide
              ? [sign * radial, 37, -across, sign * radial, 37, across,
                sign * (radial + 1.3), 37, across, sign * (radial + 1.3), 37, -across]
              : [-across, 37, sign * radial, across, 37, sign * radial,
                across, 37, sign * (radial + 1.3), -across, 37, sign * (radial + 1.3)];
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
            geometry.setIndex([0, 1, 2, 0, 2, 3]);
            geometry.computeVertexNormals();
            const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
              color: hex, side: THREE.DoubleSide, depthTest: false,
            }));
            mesh.renderOrder = 2;
            mesh.name = `EDITOR_DESIGN_${stand}`;
            colorBands.add(mesh);
          }
          world.add(colorBands);
        }
        if (typeof roofVisible === 'boolean') roofOn = roofVisible;
        roof.forEach(mesh => { mesh.visible = roofOn; });
        concept?.group.traverse(object => {
          if (object.name?.includes('_ROOF_JUNCTION') || object.name?.includes('_EAVE'))
            object.visible = roofOn;
        });
        if (cameraPreset === 'seat' || cameraPreset === 'interior') {
          azimuth = -1.2; elevation = .63; distance = 210;
        } else if (cameraPreset === 'exterior') {
          azimuth = .88; elevation = .56; distance = 490;
        } else if (cameraPreset === 'roof-corner') {
          azimuth = .34; elevation = 1.03; distance = 430;
        } else if (cameraPreset === 'opposite') {
          azimuth = -2.28; elevation = .53; distance = 490;
        } else if (cameraPreset === 'distance') {
          azimuth = .6; elevation = .57; distance = 810;
        }
        if (orbit) {
          azimuth = Number(orbit.azimuth) * Math.PI / 180 + .88;
          elevation = clamp(Number(orbit.elevation) * Math.PI / 180, .15, 1.35);
        }
         // Daylight remains a subtle tint; the map environment must retain its dark neon contrast.
          if (typeof day === 'boolean' && !transparentBackground) {
           const environmentColor = day ? '#081719' : nightEnvironment;
           scene.background.set(environmentColor);
           scene.fog.color.set(environmentColor);
         }
        if (typeof floodlight === 'boolean') sun.intensity = floodlight ? 2 : 1.5;
        render();
        return Promise.resolve();
      },
    };
  } catch (error) {
    dispose();
    throw error;
  }
}