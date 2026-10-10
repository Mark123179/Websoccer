// Isolated read-only preview. No editor save/expansion endpoints are called.
const root = document.querySelector("[data-creator-stadium-viewer]");
let mounted = null, disposed = false;
const status = root.querySelector("[data-viewer-status]");
try {
    const element = root.querySelector("[data-stadium-stage]");
    const {mountDortmundScene} = await import(root.dataset.originalModule);
    mounted = await mountDortmundScene({
        element, includeSurroundings: false, interactive: true,
        compact: true, transparentBackground: true,
    });
    if (disposed) mounted?.dispose();
    else status.hidden = true;
} catch (error) {
    status.textContent = error.message?.startsWith("WebGL")
        ? error.message : "Das Stadionmodell konnte nicht geladen werden.";
}
const activity = () => mounted?.setActive?.(!document.hidden);
document.addEventListener("visibilitychange", activity);
window.addEventListener("pagehide", event => {
    if (event.persisted) mounted?.setActive?.(false);
    else { disposed = true; mounted?.dispose(); }
});
window.addEventListener("pageshow", activity);
