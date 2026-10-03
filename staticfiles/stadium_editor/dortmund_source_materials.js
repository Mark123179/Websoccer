// The full Unity shader is not reproduced. NoDraw's source renderer is enabled;
// its saved PBR state is opaque, with an untextured base-color factor.
// Fail closed if the exporter has not supplied that verified source color.
export function sourceOpaqueColor(part) {
  if (!/^NoDraw(?:_|\.|$)/i.test(part.material)) return null;
  return /^#[0-9a-f]{6}$/i.test(part.sourceOpaqueColor || '')
    ? part.sourceOpaqueColor : null;
}

export function previewSupportsMaterial(part) {
  return !/^NoDraw(?:_|\.|$)/i.test(part.material) || sourceOpaqueColor(part) !== null;
}