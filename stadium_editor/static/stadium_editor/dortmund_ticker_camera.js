// Camera-only framing for the admin ticker. Source stadium geometry is untouched.
export const TICKER_ELEVATION = .86;
export const TICKER_AZIMUTH = -Math.PI / 2;

export function tickerCameraFrame(aspect) {
  if (!Number.isFinite(aspect) || aspect <= 0) {
    throw new RangeError('Die Kameraproportion muss positiv sein.');
  }
  const viewHeight = Math.max(132, 246 / aspect);
  const halfHeight = viewHeight / 2;
  // Measured grass edge in the original mesh: keep a small lower margin.
  // The actual touchline (X=-34.08) stays further inside the viewport.
  const targetUp = halfHeight - 37.900013 * Math.sin(TICKER_ELEVATION) - 2.5;
  return {
    left: -viewHeight * aspect / 2,
    right: viewHeight * aspect / 2,
    top: halfHeight,
    bottom: -halfHeight,
    targetY: targetUp / Math.cos(TICKER_ELEVATION),
  };
}
