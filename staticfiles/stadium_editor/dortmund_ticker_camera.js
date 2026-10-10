// Camera-only framing for the admin ticker. Source stadium geometry is untouched.
export const TICKER_MIN_HEIGHT = 35;
export const TICKER_MAX_HEIGHT = 75;
export const TICKER_DEFAULT_HEIGHT = 50;
export const TICKER_ELEVATION = TICKER_DEFAULT_HEIGHT * Math.PI / 180;
export const TICKER_AZIMUTH = -Math.PI / 2;
export const TICKER_VIEW_OFFSET = -.18;

export function tickerHeightElevation(degrees) {
  if (!Number.isFinite(degrees)) throw new RangeError('Die Kamerahöhe muss endlich sein.');
  return Math.max(TICKER_MIN_HEIGHT, Math.min(TICKER_MAX_HEIGHT, degrees)) * Math.PI / 180;
}

export function tickerCameraFrame(aspect, elevation = TICKER_ELEVATION) {
  if (!Number.isFinite(aspect) || aspect <= 0) {
    throw new RangeError('Die Kameraproportion muss positiv sein.');
  }
  if (!Number.isFinite(elevation) || elevation < tickerHeightElevation(TICKER_MIN_HEIGHT)
      || elevation > tickerHeightElevation(TICKER_MAX_HEIGHT)) {
    throw new RangeError('Die Kameraneigung liegt außerhalb des Vorschau-Bereichs.');
  }
  // Keep aim and distance fixed while adjusting height: unlike the old
  // orthographic view, the near touchline now grows relative to the far one.
  // Widen the vertical lens on narrow screens rather than cropping pitch sides.
  const tanHalfFov = Math.tan(27 * Math.PI / 360) * Math.max(1, 1.85 / aspect);
  return {
    fov: 2 * Math.atan(tanHalfFov) * 180 / Math.PI,
    distance: 285,
    target: {x: 0, y: 0, z: 0},
    offsetY: TICKER_VIEW_OFFSET,
  };
}
