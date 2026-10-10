// Registration is ground-bound. Never fit the camera to changing stand bounds.
export function imageCameraFrame(config) {
  const {referenceSize, pitchCorners, pitchHalfSize, pitchY = 0} = config;
  if (!Array.isArray(referenceSize) || referenceSize.length !== 2 ||
      !Array.isArray(pitchCorners) || pitchCorners.length !== 4 ||
      !Array.isArray(pitchHalfSize) || pitchHalfSize.length !== 2 ||
      ![...referenceSize, ...pitchCorners.flat(), ...pitchHalfSize, pitchY]
        .every(value => typeof value === 'number' && Number.isFinite(value)) ||
      pitchCorners.some(point => !Array.isArray(point) || point.length !== 2) ||
      referenceSize.some(value => value <= 0) || pitchHalfSize.some(value => value <= 0)) {
    throw new Error('Ungültige Spielfeldregistrierung.');
  }
  const [width, height] = referenceSize;
  const [farLeft, farRight, nearRight, nearLeft] = pitchCorners;
  const farWidth = farRight[0] - farLeft[0];
  const nearWidth = nearRight[0] - nearLeft[0];
  const farY = (farLeft[1] + farRight[1]) / 2;
  const nearY = (nearLeft[1] + nearRight[1]) / 2;
  const [depth, length] = pitchHalfSize;
  const sinElevation = (nearY - farY) * 2 * length / (depth * (farWidth + nearWidth));
  const depthRatio = (nearWidth - farWidth) / (nearWidth + farWidth);
  if (sinElevation <= 0 || sinElevation >= 1 || depthRatio <= 0 ||
      depthRatio >= 1 || nearWidth <= 0 || farWidth <= 0) {
    throw new Error('Das Bild lässt sich nicht als feste Stadionperspektive registrieren.');
  }
  const elevation = Math.asin(sinElevation);
  const distance = depth * Math.cos(elevation) / depthRatio;
  const focal = farWidth * (distance + depth * Math.cos(elevation)) / (2 * length);
  const centerX = pitchCorners.reduce((sum, p) => sum + p[0], 0) / 4;
  const centerY = farY + farWidth * depth * sinElevation / (2 * length);
  // Reject a pair of arbitrarily shaped quadrilaterals rather than warping
  // stadium geometry. These supplied fields are symmetric to subpixel accuracy.
  const expected = [
    [centerX - farWidth / 2, farY], [centerX + farWidth / 2, farY],
    [centerX + nearWidth / 2, nearY], [centerX - nearWidth / 2, nearY],
  ];
  const residualPx = Math.max(...expected.map((point, i) =>
    Math.hypot(point[0] - pitchCorners[i][0], point[1] - pitchCorners[i][1])));
  if (residualPx > 2) throw new Error('Die Feld-Eckpunkte haben keine gemeinsame Kameraperspektive.');
  return {
    elevation, distance, azimuth: -Math.PI / 2,
    fov: 2 * Math.atan(height / (2 * focal)) * 180 / Math.PI,
    aspect: width / height, target: {x: 0, y: pitchY, z: 0},
    offsetX: .5 - centerX / width, offsetY: .5 - centerY / height,
    residualPx,
  };
}

export function applyImageCameraFrame(camera, frame, width, height) {
  camera.aspect = frame.aspect;
  camera.fov = frame.fov;
  // Shared letterboxed 2:1 viewport: both photo and canvas have these dimensions.
  camera.setViewOffset(width, height, width * frame.offsetX,
    height * frame.offsetY, width, height);
  camera.updateProjectionMatrix();
}
