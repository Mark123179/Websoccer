import {RGBELoader} from './stage/vendor/addons/loaders/RGBELoader.js';

// Pure-sky HDRI contains no foreign buildings/terrain. Source materials stay intact.
export async function configureNaturalLighting(THREE, scene, renderer, assetBase) {
  const texture = await new RGBELoader().loadAsync(
    new URL('overcast_soil_puresky_1k.hdr', assetBase).href,
  );
  texture.mapping = THREE.EquirectangularReflectionMapping;
  const generator = new THREE.PMREMGenerator(renderer);
  let environment;
  try { environment = generator.fromEquirectangular(texture); }
  catch (error) { texture.dispose(); throw error; }
  finally { generator.dispose(); }
  scene.background = texture;
  scene.environment = environment.texture;
  scene.environmentIntensity = .45;
  scene.fog = new THREE.Fog('#bcc8cb', 550, 1250);
  renderer.toneMappingExposure = 1.0;
  let disposed = false;
  return {dispose() {
    if (disposed) return;
    disposed = true;
    scene.environment = null;
    scene.background = null;
    environment.dispose(); texture.dispose();
  }};
}
