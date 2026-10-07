import test from 'node:test';
import assert from 'node:assert/strict';
import {naturalProfileFromUpdate} from './natural_profile.js';

test('camera, roof, and unrelated editor updates leave the selected profile alone', () => {
  assert.equal(naturalProfileFromUpdate(), null);
  assert.equal(naturalProfileFromUpdate({cameraPreset: 'exterior', roofVisible: false}), null);
  assert.equal(naturalProfileFromUpdate({weights: {NORD: .3}}), null);
});

test('only an explicit day/floodlight boolean chooses a profile', () => {
  assert.equal(naturalProfileFromUpdate({day: true}), 'day');
  assert.equal(naturalProfileFromUpdate({day: false}), 'night');
  assert.equal(naturalProfileFromUpdate({floodlight: true}), 'night');
  assert.equal(naturalProfileFromUpdate({floodlight: false}), 'day');
  assert.equal(naturalProfileFromUpdate({floodlight: true, day: true}), 'night');
});
