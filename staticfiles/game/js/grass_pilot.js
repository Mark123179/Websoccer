import {mountStudyModel, disposeStudySourceCache} from '../../stadium_editor/study_models.js?v=7';
import {createStudyLighting} from '../../stadium_editor/study_lighting.js?v=3';
import {applyStudyCamera} from '../../stadium_editor/study_camera.js?v=3';
import {createGrassPilotMaterial} from '../../stadium_editor/grass_pilot_material.js?v=1';

const config = JSON.parse(document.getElementById('grass-pilot-config').textContent);
const host = document.getElementById('grass-stage');
const variant = document.getElementById('grass-variant');
const night = document.getElementById('grass-night');
const roof = document.getElementById('grass-roof');
const floodlight = document.getElementById('grass-floodlight');
const status = document.getElementById('grass-status');
const errorBox = document.getElementById('grass-error');
let handle, lighting, grass, observer, disposed = false, shaderFailed = false;
const controls = [variant, night, roof, floodlight];
controls.forEach(control => { control.disabled = true; });

function report(error) {
  errorBox.textContent = error.message || 'Die Vorschau konnte nicht geladen werden.';
  errorBox.hidden = false;
}
function render() {
  if (!handle || disposed) return;
  handle.setRoof(roof.checked);
  lighting.setState(night.checked, false, floodlight.checked);
  handle.stage.render();
}
function resize() {
  if (!handle || disposed) return;
  const width = Math.max(1, host.clientWidth), height = Math.max(1, host.clientHeight);
  handle.stage.renderer.setSize(width, height, false);
  applyStudyCamera(handle.stage.camera, 'perspective', width, height);
  render();
}
function sync() {
  if (!handle) return;
  try {
    grass?.select(variant.value);
    render();
    if (shaderFailed) throw new Error('Rasen-Shader nicht verfügbar. Der Bestand wurde wiederhergestellt.');
    status.textContent = `${variant.selectedOptions[0].textContent} · ${night.checked ? 'Nacht' : 'Tag'} · nur Vorschau`;
  } catch (error) {
    grass?.select('bestand'); variant.value = 'bestand';
    for (const option of variant.options) if (option.value !== 'bestand') option.disabled = true;
    handle.stage.render();
    status.textContent = 'Bestand · Rasenvergleich nicht verfügbar';
    report(error);
  }
}
async function start() {
  try {
    const response = await fetch(config.lightsUrl);
    if (!response.ok) throw new Error('Die belegten Dortmunder Lichtquellen fehlen.');
    const fixtures = await response.json();
    if (!fixtures.verifiedFixtures?.length) throw new Error('Keine geprüften Stadionleuchten vorhanden.');
    handle = await mountStudyModel({host, club: 'dortmund', concept: 'perspective'});
    lighting = createStudyLighting(handle, fixtures);
    host.querySelector('.gp-stage-placeholder')?.remove();
    const renderer = handle.stage.renderer;
    renderer.debug.onShaderError = () => { shaderFailed = true; };
    renderer.domElement.setAttribute('aria-label', 'Dortmund in fester 2D-Spielperspektive');
    renderer.domElement.addEventListener('webglcontextlost', () =>
      report(new Error('Grafikkontext verloren. Bitte die Testseite neu laden.')));
    observer = new ResizeObserver(resize);
    observer.observe(host);
    [night, roof, floodlight].forEach(control => { control.disabled = false; });
    resize();
    try {
      grass = await createGrassPilotMaterial(handle.stage, config.assets);
      variant.disabled = false;
      sync();
    } catch (error) {
      status.textContent = 'Bestand · Rasenlagen nicht verfügbar';
      report(error);
    }
  } catch (error) {
    status.textContent = 'Stadionvorschau nicht verfügbar';
    report(error);
  }
}
controls.forEach(control => control.addEventListener('change', sync));
window.addEventListener('pagehide', () => {
  disposed = true; observer?.disconnect(); grass?.dispose();
  lighting?.dispose?.(); handle?.dispose(); disposeStudySourceCache();
}, {once: true});
start();
