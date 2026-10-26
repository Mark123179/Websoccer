import {mountUnityStadium} from './unity_stadium_scene.js?v=82';

const root = document.getElementById('allianzPilot');
const host = document.getElementById('pilotStage');
const status = document.getElementById('pilotStatus');
const dayInput = document.getElementById('pilotDay');
const floodlightInput = document.getElementById('pilotFloodlight');
const roofInput = document.getElementById('pilotRoof');
const cameraInput = document.getElementById('pilotCamera');

function reportError(error) {
  status.textContent = `Ansicht nicht verfügbar: ${error?.message || 'Unbekannter Fehler'}`;
  status.dataset.state = 'error';
}

async function startPilot() {
  let mounted = null;
  try {
    const response = await fetch(root.dataset.sceneUrl, {credentials: 'same-origin'});
    if (!response.ok) throw new Error(`Szenendaten konnten nicht geladen werden (HTTP ${response.status}).`);
    const scene = await response.json();
    if (scene?.presentation?.renderer !== 'unity-spatial' ||
        scene.presentation.clubFmiId !== 915) {
      throw new Error('Die gelieferte Szene ist kein freigegebenes Bayern-Originalmodell.');
    }
    mounted = await mountUnityStadium({
      element: host,
      presentation: scene.presentation,
      initialState: {
        day: dayInput.checked,
        floodlight: floodlightInput.checked,
        roofVisible: roofInput.checked,
      },
    });
    await mounted.update({
      day: dayInput.checked,
      floodlight: floodlightInput.checked,
      roofVisible: roofInput.checked,
      camera: cameraInput.value,
    });
    status.textContent = 'Originalmodell geladen · Geometrie unverändert';
    status.dataset.state = 'ready';

    dayInput.addEventListener('change', () => mounted?.update({day: dayInput.checked})
      .catch(reportError));
    floodlightInput.addEventListener('change', () =>
      mounted?.update({floodlight: floodlightInput.checked}).catch(reportError));
    roofInput.addEventListener('change', () =>
      mounted?.update({roofVisible: roofInput.checked}).catch(reportError));
    cameraInput.addEventListener('change', () =>
      mounted?.update({camera: cameraInput.value}).catch(reportError));
    window.addEventListener('pagehide', () => mounted?.dispose(), {once: true});
  } catch (error) {
    mounted?.dispose();
    reportError(error);
  }
}

startPilot();
