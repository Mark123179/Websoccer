// Match the editor's source-derived, explicitly approximate NoDraw preview.
interface SourcePart { material: string; sourceOpaqueColor?: string }
export function sourceOpaqueColor(part: SourcePart) {
  if (!/^NoDraw(?:_|\.|$)/i.test(part.material)) return null;
  return /^#[0-9a-f]{6}$/i.test(part.sourceOpaqueColor || '')
    ? part.sourceOpaqueColor : null;
}

export function previewSupportsMaterial(part: SourcePart) {
  return !/^NoDraw(?:_|\.|$)/i.test(part.material) || sourceOpaqueColor(part) !== null;
}