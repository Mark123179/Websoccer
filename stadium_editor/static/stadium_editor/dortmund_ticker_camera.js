// Camera-only framing for the admin ticker. Source stadium geometry is untouched.
export const TICKER_MIN_HEIGHT = 35;
export const TICKER_MAX_HEIGHT = 75;
export const TICKER_DEFAULT_HEIGHT = 60;
export const TICKER_ELEVATION = TICKER_DEFAULT_HEIGHT * Math.PI / 180;
export const TICKER_AZIMUTH = -Math.PI / 2;

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
  const viewHeight = Math.max(132, 246 / aspect);
  const halfHeight = viewHeight / 2;
  // Measured grass edge in the original mesh: keep a small lower margin.
  // The actual touchline (X=-34.08) stays further inside the viewport.
  const targetUp = halfHeight - 37.900013 * Math.sin(elevation) - 2.5;
  return {
    left: -viewHeight * aspect / 2,
    right: viewHeight * aspect / 2,
    top: halfHeight,
    bottom: -halfHeight,
    targetY: targetUp / Math.cos(elevation),
  };
}
