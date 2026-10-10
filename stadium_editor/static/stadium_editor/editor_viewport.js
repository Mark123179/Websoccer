/* Local view preferences only: never part of the saved stadium design. */
(function (root) {
  'use strict';
  const defaults = () => ({factor: 1, center: [0, 0]});
  const clamp = value => Math.max(.25, Math.min(8, value));
  function normalize(value) {
    if (!value || !Number.isFinite(value.factor) || value.factor <= 0 ||
        !Array.isArray(value.center) || value.center.length !== 2 ||
        !value.center.every(Number.isFinite)) return defaults();
    return {factor: clamp(value.factor), center: [...value.center]};
  }
  function load(storage, key) {
    try { return normalize(JSON.parse(storage.getItem(key))); }
    catch (_) { return defaults(); }
  }
  function save(storage, key, value) {
    try { storage.setItem(key, JSON.stringify(normalize(value))); return true; }
    catch (_) { return false; }
  }
  root.StadiumEditorViewport = {defaults, clamp, load, save};
})(typeof window === 'undefined' ? globalThis : window);
