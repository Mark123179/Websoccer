/* Reversible seat-design state shared by the editor, renderers and Node tests. */
(function(root) {
  'use strict';

  function inferMode(saved, sceneMode) {
    if (saved && (saved.seat_mode === 'original' || saved.seat_mode === 'custom'))
      return saved.seat_mode;
    if (saved && Array.isArray(saved.blocks) && saved.blocks.length) return 'custom';
    if (sceneMode === 'original' || sceneMode === 'custom') return sceneMode;
    return 'original';
  }

  function switchMode(state, mode) {
    if (mode !== 'original' && mode !== 'custom') return state;
    return {...state, mode};
  }

  function captureMaterial(material) {
    const maps = {};
    for (const key of ['map', 'alphaMap', 'aoMap', 'emissiveMap', 'bumpMap',
      'normalMap', 'roughnessMap', 'metalnessMap', 'displacementMap', 'lightMap'])
      maps[key] = material[key] ?? null;
    return { maps, color: material.color?.clone?.() ?? material.color };
  }

  function setMaterialMode(material, source, mode) {
    if (mode === 'custom') {
      for (const key of Object.keys(source.maps)) material[key] = null;
      material.vertexColors = true;
      material.color?.set?.('#ffffff');
    } else {
      for (const [key, value] of Object.entries(source.maps)) material[key] = value;
      material.vertexColors = false;
      if (source.color?.isColor && material.color?.copy) material.color.copy(source.color);
      else if (source.color !== undefined) material.color = source.color;
    }
    material.needsUpdate = true;
  }

  const api = {inferMode, switchMode, captureMaterial, setMaterialMode};
  root.StadiumSeatDesignModes = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
