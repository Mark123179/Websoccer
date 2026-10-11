const sceneURL = new URL('../../stadium_editor/dortmund_editor_scene.js', import.meta.url);
sceneURL.searchParams.set('v', `ticker-${new URL(import.meta.url).searchParams.get('v') || '18'}`);
const adapterURL = new URL('../../stadium_editor/stadium_stage_adapter.js', import.meta.url);
adapterURL.searchParams.set('v', 'ticker-4');
const liveSceneURL = new URL('../../stadium_editor/live_mode.js', import.meta.url);
liveSceneURL.searchParams.set('v', 'ticker-4');

const canvasHost = document.getElementById('ticker-stadium-preview');
const statusHost = document.getElementById('ticker-stadium-status');

if (canvasHost && statusHost) {
  let sceneHandle = null;
  let attempt = 0;
  let stopped = false;
  const heightControl = document.getElementById('ticker-camera-height');
  const heightValue = document.getElementById('ticker-camera-height-value');
  const heightReset = document.getElementById('ticker-camera-reset');
  const roofControl = document.getElementById('ticker-roof-visible');
  const roofValue = document.getElementById('ticker-roof-state');
  const dayControl = document.getElementById('ticker-day-visible');
  const dayValue = document.getElementById('ticker-day-state');
  const defaultHeight = Number(heightControl?.defaultValue || 50);
  let cameraFrame = 0;
  let canonicalMode = false;
  let spatialDortmund = false;
  let spatialUnity = false;
  const controlsEnabled = enabled => {
    if (heightControl) heightControl.disabled = !enabled || canonicalMode || spatialDortmund || spatialUnity;
    if (heightReset) heightReset.disabled = !enabled || canonicalMode || spatialDortmund || spatialUnity;
    if (roofControl) roofControl.disabled = !enabled;
    if (dayControl) dayControl.disabled = !enabled;
  };
  const updateRoof = () => {
    const visible = roofControl?.checked ?? true;
    if (canonicalMode) sceneHandle?.update?.({roofVisible: visible});
    else sceneHandle?.setTickerRoofVisible(visible);
    if (roofValue) roofValue.textContent = visible ? 'Mit Dach' : 'Ohne Dach';
  };
  roofControl?.addEventListener('change', updateRoof);
  const updateDay = () => {
    const day = dayControl?.checked ?? true;
    if (canonicalMode) sceneHandle?.update?.({day});
    else if (spatialDortmund || spatialUnity) sceneHandle?.update?.({day, floodlight: !day});
    if (dayValue) dayValue.textContent = day ? 'Tageslicht' : 'Nacht';
  };
  dayControl?.addEventListener('change', updateDay);
  const updateCamera = () => {
    const degrees = Number(heightControl?.value || defaultHeight);
    if (heightValue) heightValue.textContent = `Neigung: ${degrees}°`;
    heightControl?.setAttribute('aria-valuetext', `${degrees} Grad`);
    cancelAnimationFrame(cameraFrame);
    cameraFrame = requestAnimationFrame(() => {
      if (!stopped && !canonicalMode) sceneHandle?.setTickerCameraHeight(degrees);
    });
  };
  heightControl?.addEventListener('input', updateCamera);
   const resetCamera = () => {
    if (heightControl) heightControl.value = String(defaultHeight);
    updateCamera();
   };
   heightReset?.addEventListener('click', resetCamera);

  statusHost.className = 'ticker-stadium-status';
  statusHost.setAttribute('role', 'status');
  statusHost.setAttribute('aria-live', 'polite');

  const setState = (state, message) => {
    canvasHost.dataset.state = state;
    statusHost.replaceChildren();
    const label = document.createElement('span');
    label.textContent = message;
    statusHost.append(label);
    statusHost.hidden = false;
  };

  const readJSON = (value, fallback) => {
    if (!value) return fallback;
    try { return JSON.parse(value); } catch (_) {
      throw new Error('Stadionumfeld-Daten sind ungültig.');
    }
  };

  const dispose = () => {
    stopped = true;
    cancelAnimationFrame(cameraFrame);
    heightControl?.removeEventListener('input', updateCamera);
     heightReset?.removeEventListener('click', resetCamera);
    roofControl?.removeEventListener('change', updateRoof);
    dayControl?.removeEventListener('change', updateDay);
    controlsEnabled(false);
    sceneHandle?.dispose();
    sceneHandle = null;
  };

  const mount = async () => {
    const thisAttempt = ++attempt;
    sceneHandle?.dispose();
    sceneHandle = null;
    controlsEnabled(false);
    statusHost.querySelector('[data-retry]')?.remove();
    setState('loading', 'Stadionansicht wird geladen …');
    try {
      const config = readJSON(document.getElementById('ticker-stadium-environment')?.textContent, {});
      spatialDortmund = config.renderer === 'dortmund-spatial';
      spatialUnity = config.renderer === 'unity-spatial';
      if(spatialUnity){
        if(!config.sceneUrl) throw new Error('Original-Stadion-Scene-Adresse fehlt.');
        const response=await fetch(config.sceneUrl,{credentials:'same-origin'});
        if(!response.ok) throw new Error('Original-Stadion-Scene konnte nicht geladen werden.');
        const runtime=(await response.json()).presentation;
        if(runtime?.clubId!==config.clubId||runtime?.renderer!=='unity-spatial')
          throw new Error('Stadion-Scene gehört nicht zum gewählten Verein.');
        const {mountUnityStadium}=await import(new URL('../../stadium_editor/unity_stadium_scene.js',import.meta.url));
        const mounted=await mountUnityStadium({element:canvasHost,presentation:runtime,tickerPreview:true});
        if(stopped||thisAttempt!==attempt){mounted.dispose();return;}
        sceneHandle=mounted;controlsEnabled(true);
        updateRoof();updateDay();
        setState('ready',`${config.stadium} · Originalmodell und eigener Ortsplan · Gemeinsame Feldkamera`);
        return;
      }
      if (spatialDortmund && !config.sceneUrl)
        throw new Error('Die gemeinsame BVB-Scene-Adresse fehlt.');
      if (config.renderer === 'canonical' && !config.sceneUrl) {
        throw new Error('Die kanonische Stadion-Scene-Adresse fehlt; es wird kein Ersatzmodell geladen.');
      }
      canonicalMode = config.renderer === 'canonical' && Boolean(config.sceneUrl);
      controlsEnabled(false);
      if (canonicalMode) {
        canvasHost.dataset.renderer = 'canonical';
        const [{mountStadiumStage}, {loadLiveScene, StadiumLiveRenderer}] = await Promise.all([
          import(adapterURL.href), import(liveSceneURL.href),
        ]);
        const scene = await loadLiveScene(config.sceneUrl);
        let environmentWarning = '';
        if (scene.surroundings?.unavailable || scene.surroundings?.warning) {
          const warning = scene.surroundings.warning || scene.surroundings.unavailable;
          environmentWarning = typeof warning === 'string' ? warning : JSON.stringify(warning);
          const noObjects = !(scene.surroundings.buildings?.length ||
            scene.surroundings.roads?.length || scene.surroundings.green?.length ||
            scene.surroundings.vegetation?.length);
          if (noObjects) {
            scene.surroundings = {
              ...scene.surroundings, style: 'elversberg-blueprint', frame: 'pitch',
              buildings: [], roads: [], green: [], vegetation: [],
            };
          }
        }
        if (scene.surroundings &&
            (scene.surroundings.style !== 'elversberg-blueprint' ||
             scene.surroundings.frame !== 'pitch')) {
          scene.surroundings = {
            style: 'elversberg-blueprint', frame: 'pitch',
            buildings: [], roads: [], green: [], vegetation: [],
          };
          environmentWarning = 'Umfelddaten nicht passend gerahmt · Umfeld ausgelassen';
        } else if (!scene.surroundings) {
          scene.surroundings = {
            style: 'elversberg-blueprint', frame: 'pitch',
            buildings: [], roads: [], green: [], vegetation: [],
          };
          environmentWarning ||= 'Umfeldquelle fehlt · Stadion bleibt verfügbar';
        }
        const mounted = await mountStadiumStage({
          element: canvasHost, scene, mode: 'live', camera: 'match',
          day: dayControl?.checked ?? true,
          roofVisible: roofControl?.checked ?? true,
          surroundings: true,
          fallback: canvas => new StadiumLiveRenderer(canvas, scene),
        });
        if (stopped || thisAttempt !== attempt) {
          mounted?.dispose?.();
          return;
        }
        sceneHandle = mounted;
        sceneHandle?.setActive?.(false);
        controlsEnabled(true);
        if (roofControl && !roofControl.checked) updateRoof();
        updateDay();
        const title = config.stadium || 'Elversberg';
        setState('ready', `${title} · ${environmentWarning || 'Gemeinsames Blueprint-Umfeld'} · Feste 75%-Feldkamera`);
        return;
      }
      delete canvasHost.dataset.renderer;
      setState('loading', 'Originales Dortmunder Stadion wird geladen …');
      if (config.unavailable) throw new Error('Die Dortmunder Umfeldquelle ist derzeit nicht verfügbar. Der Ticker läuft weiter.');
      const {mountDortmundScene} = await import(sceneURL.href);
      let presentation = config;
      if (spatialDortmund) {
        const response = await fetch(config.sceneUrl, {credentials:'same-origin'});
        if (!response.ok) throw new Error('Die gemeinsame BVB-Scene konnte nicht geladen werden.');
        const scene = await response.json();
        if (scene.club?.id !== config.clubId ||
            scene.presentation?.renderer !== 'dortmund-spatial')
          throw new Error('Die BVB-Scene gehört nicht zum gewählten Verein.');
        presentation = scene.presentation;
      }
      const surroundings = presentation.surroundings ??
        readJSON(canvasHost.dataset.surroundings, {});
      const frame = presentation.frame ?? readJSON(canvasHost.dataset.frame, {});
      const mounted = await mountDortmundScene({
        element: canvasHost,
        surroundings,
        frame,
        includeSurroundings: !config.imageBackground,
        interactive: false,
        autoRotate: false,
        compact: false,
        transparentBackground: Boolean(config.imageBackground),
        tickerPreview: true,
        spatialTicker: spatialDortmund,
        runtimeLighting: spatialDortmund,
        naturalPackage: config.naturalPackage,
        imageBackground: config.imageBackground,
        onStatus: message => {
          if (!stopped && thisAttempt === attempt) setState('ready', `SIGNAL IDUNA PARK · ${message}`);
        },
      });
      if (stopped || thisAttempt !== attempt) {
        mounted?.dispose();
        return;
      }
      sceneHandle = mounted;
      if (spatialDortmund) {
        await sceneHandle.update({designColors: presentation.designColors,
          day: dayControl?.checked ?? true, floodlight: dayControl ? !dayControl.checked : false});
      }
      // This view is a still preview: first frame and ResizeObserver redraws only.
      sceneHandle?.setActive(false);
      controlsEnabled(true);
      if (Number(heightControl?.value || defaultHeight) !== defaultHeight) updateCamera();
      if (roofControl && !roofControl.checked) updateRoof();
      setState('ready', spatialDortmund
        ? 'SIGNAL IDUNA PARK · Gemeinsamer räumlicher Ortsplan · Feste 75%-Feldkamera'
        : 'SIGNAL IDUNA PARK · 3D-Stadion · Bildbasiertes Umfeld · Feste Kamera');
    } catch (error) {
      if (stopped || thisAttempt !== attempt) return;
      canvasHost.replaceChildren();
      controlsEnabled(false);
      setState('error', error?.message || 'Das Stadion konnte nicht geladen werden.');
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.dataset.retry = '';
      retry.className = 'ticker-stadium-retry';
      retry.textContent = 'Erneut laden';
      retry.addEventListener('click', mount, {once: true});
      statusHost.append(retry);
    }
  };

  window.addEventListener('pagehide', dispose, {once: true});
  mount();
}
