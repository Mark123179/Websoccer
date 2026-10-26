/** Approved 75% study projection, shared by the export and rendered UV check. */
export const GRASS_STUDY_CAMERA = Object.freeze({
  focal: 1337.4782524186542, cx: 940, cy: 681.3221103379157,
  position: Object.freeze([0, 98, 110]), tilt: 44, format: Object.freeze([1880, 940]),
});

export function applyGrassStudyCamera(stage) {
  const c = GRASS_STUDY_CAMERA, [width, height] = c.format;
  stage.renderer.setPixelRatio(1);
  stage.renderer.setSize(width, height, false);
  stage.camera.position.fromArray(c.position);
  stage.camera.up.set(0, 1, 0);
  const tilt = c.tilt * Math.PI / 180;
  stage.camera.lookAt(0, 98 - Math.sin(tilt), 110 - Math.cos(tilt));
  stage.camera.updateMatrixWorld(true);
  stage.camera.projectionMatrix.makePerspective(-c.cx / c.focal,
    (width - c.cx) / c.focal, c.cy / c.focal, -(height - c.cy) / c.focal, 1, 6000);
  stage.camera.projectionMatrixInverse.copy(stage.camera.projectionMatrix).invert();
}
