export const LIGHTING_PRESETS = Object.freeze({
  day: Object.freeze({
    background: 0xb9c9d8,
    hemisphere: Object.freeze({
      sky: 0xeaf2ff, ground: 0x59646e, intensity: 1.45,
    }),
    ambient: Object.freeze({color: 0xb8c4d0, intensity: 0.22}),
    key: Object.freeze({
      color: 0xfffbef, intensity: 1.08, position: [-70, 125, 85],
    }),
    fill: Object.freeze({
      color: 0xc7dcf3, intensity: 0.28, position: [95, 60, -75],
    }),
    exposure: 1,
    building: 0x323941,
    structureEmissive: 0x53606c,
    structureEmissiveIntensity: 0.24,
    roofEmissive: 0x7b8792,
    roofEmissiveIntensity: 0.9,
    pitchEmissive: 0x000000,
    pitchEmissiveIntensity: 0,
  }),
  night: Object.freeze({
    background: 0x040912,
    hemisphere: Object.freeze({
      sky: 0x3d526f, ground: 0x151f2c, intensity: 0.9,
    }),
    ambient: Object.freeze({color: 0x344862, intensity: 0.4}),
    key: Object.freeze({
      color: 0x9ebce8, intensity: 0.34, position: [-55, 105, 100],
    }),
    fill: Object.freeze({
      color: 0x7895bd, intensity: 0.22, position: [90, 48, -65],
    }),
    exposure: 1.06,
    building: 0x1b222c,
    structureEmissive: 0x26384c,
    structureEmissiveIntensity: 0.2,
    roofEmissive: 0x344a63,
    roofEmissiveIntensity: 0.42,
    pitchEmissive: 0x0d4a25,
    pitchEmissiveIntensity: 0.58,
  }),
});

export function lightingPreset(mode) {
  return LIGHTING_PRESETS[mode === 'night' ? 'night' : 'day'];
}