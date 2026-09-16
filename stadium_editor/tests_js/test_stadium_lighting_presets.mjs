import assert from 'node:assert/strict';
import test from 'node:test';

import {
  LIGHTING_PRESETS,
  lightingPreset,
} from '../static/stadium_editor/stage/stadium_lighting_presets.js';

test('daylight is neutral, brighter than ambient night, and needs no emissive pitch', () => {
  const day = lightingPreset('day');
  const night = lightingPreset('night');
  assert.equal(day, LIGHTING_PRESETS.day);
  assert.ok(day.hemisphere.intensity > night.hemisphere.intensity * 1.5);
  assert.ok(day.key.intensity > night.key.intensity * 3);
  assert.equal(day.pitchEmissiveIntensity, 0);
  assert.ok(day.roofEmissiveIntensity > 0);
  const keyChannels = [
    day.key.color >> 16,
    (day.key.color >> 8) & 0xff,
    day.key.color & 0xff,
  ];
  assert.ok(
    Math.max(...keyChannels) - Math.min(...keyChannels) <= 16,
    'day key light must stay neutral rather than green or warm',
  );
});

test('night keeps readable ambient layers within a controlled exposure range', () => {
  const night = lightingPreset('night');
  assert.ok(night.hemisphere.intensity >= 0.75);
  assert.ok(night.ambient.intensity >= 0.3);
  assert.ok(night.key.intensity > 0);
  assert.ok(night.fill.intensity > 0);
  assert.ok(night.pitchEmissiveIntensity > 0);
  assert.ok(night.structureEmissiveIntensity > 0);
  assert.ok(night.roofEmissiveIntensity > 0);
  assert.ok(night.exposure >= 0.9 && night.exposure <= 1.15);
  assert.equal(lightingPreset('unknown'), LIGHTING_PRESETS.day);
});

test('lighting presets and their nested light contracts are immutable', () => {
  assert.ok(Object.isFrozen(LIGHTING_PRESETS));
  for (const preset of Object.values(LIGHTING_PRESETS)) {
    assert.ok(Object.isFrozen(preset));
    assert.ok(Object.isFrozen(preset.hemisphere));
    assert.ok(Object.isFrozen(preset.ambient));
    assert.ok(Object.isFrozen(preset.key));
    assert.ok(Object.isFrozen(preset.fill));
  }
});