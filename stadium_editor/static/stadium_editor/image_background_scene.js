import {imageCameraFrame} from './image_background_camera.js?v=1';

export function createImageBackground(element, config) {
  const frame = imageCameraFrame(config);
  if (Math.abs(config.aspect - frame.aspect) > .001) {
    throw new Error('Bildformat und Kameraregistrierung stimmen nicht überein.');
  }
  const container = document.createElement('div');
  container.className = 'ticker-image-viewport';
  const photo = document.createElement('img');
  photo.className = 'ticker-image-background';
  photo.alt = '';
  photo.draggable = false;
  photo.decoding = 'async';
  container.append(photo);
  element.prepend(container);
  let disposed = false, generation = 0;
  const cache = new Map();
  async function prepare(profile) {
    const source = config.images?.[profile];
    if (!source?.url || !Array.isArray(source.size)) {
      throw new Error(`Stadion-Hintergrund fehlt: ${profile}.`);
    }
    if (!cache.has(profile)) {
      const task = (async () => {
        const loaded = new Image();
        loaded.src = source.url;
        try { await loaded.decode(); }
        catch (_) { throw new Error(`Stadion-Hintergrund konnte nicht geladen werden: ${profile}.`); }
        if (loaded.naturalWidth !== source.size[0] || loaded.naturalHeight !== source.size[1] ||
            Math.abs(loaded.naturalWidth / loaded.naturalHeight - frame.aspect) > .001) {
          throw new Error(`Stadion-Bildformat stimmt nicht: ${profile}.`);
        }
        return loaded;
      })();
      cache.set(profile, task);
      task.catch(() => { if (cache.get(profile) === task) cache.delete(profile); });
    }
    return cache.get(profile);
  }
  return {
    container, frame,
    async setProfile(profile, commitLighting) {
      const token = ++generation;
      const loaded = await prepare(profile);
      if (disposed || generation !== token) return false;
      // One synchronous commit: no frame with a new photo and old illumination.
      commitLighting(profile);
      photo.src = loaded.src;
      element.dataset.imageProfile = profile;
      return true;
    },
    dispose() {
      disposed = true; generation++;
      photo.removeAttribute('src'); container.remove(); cache.clear();
    },
  };
}

export function configureImageLighting(THREE, scene, renderer, roofBounds, pitchHalfSize) {
  // No sky, HDRI, geographic model or floor: only the live stadium is lit.
  scene.background = null;
  scene.fog = null;
  renderer.setClearColor(0x000000, 0);
  const group = new THREE.Group();
  const ambient = new THREE.HemisphereLight(0xe7edf5, 0x555b42, .65);
  const sun = new THREE.DirectionalLight(0xfff2d5, 2);
  sun.position.set(-180, 260, -120);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, {left: -160, right: 160, top: 160, bottom: -160, near: 1, far: 800});
  sun.shadow.bias = -.00015;
  sun.shadow.normalBias = .035;
  sun.shadow.camera.updateProjectionMatrix();
  const floodFill = new THREE.HemisphereLight(0xb6c9ee, 0x272f3e, 0);
  group.add(ambient, sun, sun.target, floodFill);
  const spots = [];
  const cx = (roofBounds.min.x + roofBounds.max.x) / 2;
  const cz = (roofBounds.min.z + roofBounds.max.z) / 2;
  const [pitchDepth, pitchLength] = pitchHalfSize;
  // Under-canopy, inward-facing light: do not flood the outside roof skin.
  // Six fixtures are a lighting approximation, not a source-model lamp inventory.
  for (const sign of [-1, 1]) {
    for (const z of [-pitchLength * .8, 0, pitchLength * .8]) {
      const spot = new THREE.SpotLight(0xfff4df, 0, 180, .9, .65, 1);
      spot.position.set(cx + sign * (pitchDepth + 8), roofBounds.min.y + 1.5, cz + z);
      spot.target.position.set(cx - sign * pitchDepth / 3, 0, cz - z * .3);
      spot.castShadow = false;
      group.add(spot, spot.target);
      spots.push(spot);
    }
  }
  scene.add(group);
  let disposed = false;
  return {
    setProfile(profile) {
      if (disposed) return;
      if (profile !== 'day' && profile !== 'night') throw new Error('Ungültiges Lichtprofil.');
      ambient.intensity = profile === 'day' ? .65 : .16;
      sun.intensity = profile === 'day' ? 2 : 0;
      sun.castShadow = profile === 'day';
      floodFill.intensity = profile === 'night' ? .22 : 0;
      spots.forEach(spot => { spot.intensity = profile === 'night' ? 90 : 0; });
      renderer.toneMappingExposure = profile === 'day' ? .98 : .84;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      sun.shadow.dispose();
      scene.remove(group);
    },
  };
}
