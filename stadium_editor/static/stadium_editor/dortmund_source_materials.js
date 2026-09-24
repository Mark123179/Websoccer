// The reduced browser export has no implementation of Unity's NoDraw shader.
// Rendering those meshes as ordinary opaque grey invents visible walls.
// Omission in this preview does not establish what the full Unity scene drew.
export function previewSupportsMaterial(name) {
  return !/^NoDraw(?:_|\.|$)/i.test(name);
}