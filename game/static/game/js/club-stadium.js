// Read-only miniature: no editor data, surroundings or input controls.
(() => {
    const script = document.currentScript;
    const host = document.querySelector('[data-club-stadium-stage]');
    if (!host) return;
    const status = host.parentElement.querySelector('[data-club-stadium-status]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let scene = null, loading = false, visible = false, disposed = false;

    const updateActivity = () => scene?.setActive(
        visible && !document.hidden && !reducedMotion.matches
    );
    const load = async () => {
        if (loading || scene || disposed) return;
        loading = true;
        try {
            const {mountDortmundScene} = await import(script.dataset.sceneUrl);
            const mounted = await mountDortmundScene({
                element: host,
                includeSurroundings: false,
                interactive: false,
                autoRotate: true,
                compact: true,
                compactZoom: 1.2,
                transparentBackground: true,
            });
            if (disposed) {
                mounted?.dispose();
                return;
            }
            scene = mounted;
            status.hidden = true;
            updateActivity();
        } catch (error) {
            if (disposed) return;
            status.hidden = false;
            status.textContent = error.message?.startsWith('WebGL')
                ? error.message : 'Das 3D-Stadion konnte nicht geladen werden.';
        }
    };
    const observer = new IntersectionObserver(entries => {
        visible = entries.some(entry => entry.isIntersecting);
        if (visible) load();
        updateActivity();
    });
    const dispose = () => {
        disposed = true;
        observer.disconnect();
        document.removeEventListener('visibilitychange', updateActivity);
        reducedMotion.removeEventListener('change', updateActivity);
        scene?.dispose();
        scene = null;
    };
    observer.observe(host);
    document.addEventListener('visibilitychange', updateActivity);
    reducedMotion.addEventListener('change', updateActivity);
    // Keep a back/forward-cached page usable; dispose only when it is discarded.
    window.addEventListener('pagehide', event => {
        if (event.persisted) scene?.setActive(false);
        else dispose();
    });
    window.addEventListener('pageshow', updateActivity);
})();