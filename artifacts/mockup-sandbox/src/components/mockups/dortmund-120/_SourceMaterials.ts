// Match the editor: the reduced browser export cannot reproduce Unity's
// NoDraw shader. Do not replace its unknown output with an opaque grey wall.
export function previewSupportsMaterial(name: string) {
  return !/^NoDraw(?:_|\.|$)/i.test(name);
}