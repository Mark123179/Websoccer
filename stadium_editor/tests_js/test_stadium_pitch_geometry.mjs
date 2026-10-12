import assert from 'node:assert/strict';
import test from 'node:test';
import {execFileSync} from 'node:child_process';

import {
  PITCH,
  buildPitchLayout,
  pitchWorldPoint,
} from '../static/stadium_editor/stage/pitch_geometry.js';

function close(actual, expected, message) {
  assert.ok(Math.abs(actual - expected) < 1e-9,
    `${message}: expected ${expected}, received ${actual}`);
}

test('2D pitch dimensions agree with the source registration contract', () => {
  const contract = JSON.parse(execFileSync('python', ['-c',
    'import json; from stadium_editor.pitch_validation import PITCH_LENGTH, PITCH_WIDTH; print(json.dumps(dict(length=PITCH_LENGTH,width=PITCH_WIDTH)))'],
    {cwd: new URL('../..', import.meta.url), encoding: 'utf8'}));
  assert.deepEqual(PITCH, contract);
  assert.deepEqual(PITCH, {length: 105, width: 68});
});

test('pitch surface and every marking share one quarter-turn transform', () => {
  for (const degrees of [0, 90, 180, 270]) {
    const rotation = degrees * Math.PI / 180;
    const layout = buildPitchLayout(rotation);
    assert.equal(layout.stripes.length, 10);
    assert.equal(layout.lines.length, 17);
    assert.deepEqual(layout.center, pitchWorldPoint([0, 0], rotation));

    const surfacePoints = layout.stripes.flatMap(stripe => stripe.quad);
    const xs = surfacePoints.map(point => point[0]);
    const zs = surfacePoints.map(point => point[1]);
    const rotated = degrees % 180 !== 0;
    close(Math.max(...xs) - Math.min(...xs),
      rotated ? PITCH.width : PITCH.length, `${degrees}° surface width`);
    close(Math.max(...zs) - Math.min(...zs),
      rotated ? PITCH.length : PITCH.width, `${degrees}° surface depth`);

    const halfway = layout.lines.find(line => line.name === 'halfway');
    assert.deepEqual(halfway.from, pitchWorldPoint([0, -34], rotation));
    assert.deepEqual(halfway.to, pitchWorldPoint([0, 34], rotation));
    const penalty = layout.lines.find(
      line => line.name === 'penalty-side-1',
    );
    assert.deepEqual(
      penalty.from,
      pitchWorldPoint([36, -20.16], rotation),
    );
    assert.deepEqual(
      penalty.to,
      pitchWorldPoint([36, 20.16], rotation),
    );
  }
});

test('pitch layout rejects invalid rotations and stripe counts', () => {
  assert.throws(() => buildPitchLayout(Number.NaN), /Ungültige/);
  assert.throws(() => buildPitchLayout(0, 0), /Ungültige/);
  assert.throws(() => buildPitchLayout(0, 101), /Ungültige/);
});