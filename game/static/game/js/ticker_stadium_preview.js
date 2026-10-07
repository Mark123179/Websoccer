const sceneURL = new URL('../../stadium_editor/dortmund_editor_scene.js', import.meta.url);
sceneURL.searchParams.set('v', `ticker-${new URL(import.meta.url).searchParams.get('v') || '7'}`);

const canvasHost = document.getElementById('ticker-stadium-preview');
const statusHost = document.getElementById('ticker-stadium-status');

if (canvasHost && statusHost) {
  let sceneHandle = null;
  let attempt = 0;
  let stopped = false;

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
    sceneHandle?.dispose();
    sceneHandle = null;
  };

  const mount = async () => {
    const thisAttempt = ++attempt;
    sceneHandle?.dispose();
    sceneHandle = null;
    statusHost.querySelector('[data-retry]')?.remove();
    setState('loading', 'Originales Dortmunder Stadion wird geladen …');
    try {
      const config = readJSON(document.getElementById('ticker-stadium-environment')?.textContent, {});
      if (config.unavailable) throw new Error('Die Dortmunder Umfeldquelle ist derzeit nicht verfügbar. Der Ticker läuft weiter.');
      const {mountDortmundScene} = await import(sceneURL.href);
      const surroundings = config.surroundings ??
        readJSON(canvasHost.dataset.surroundings, {});
      const frame = config.frame ?? readJSON(canvasHost.dataset.frame, {});
      const mounted = await mountDortmundScene({
        element: canvasHost,
        surroundings,
        frame,
        includeSurroundings: true,
        interactive: false,
        autoRotate: false,
        compact: false,
        transparentBackground: false,
        tickerPreview: true,
        onStatus: message => {
          if (!stopped && thisAttempt === attempt) setState('ready', `SIGNAL IDUNA PARK · ${message}`);
        },
      });
      if (stopped || thisAttempt !== attempt) {
        mounted?.dispose();
        return;
      }
      sceneHandle = mounted;
      // This view is a still preview: first frame and ResizeObserver redraws only.
      sceneHandle?.setActive(false);
      setState('ready', 'SIGNAL IDUNA PARK · Unity-Modell · Offene Kamerastudie');
    } catch (error) {
      if (stopped || thisAttempt !== attempt) return;
      canvasHost.replaceChildren();
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
