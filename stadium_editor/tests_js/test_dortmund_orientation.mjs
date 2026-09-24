import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {SIDES} from '../static/stadium_editor/dortmund_concept.js';

const editor = readFileSync(new URL('../templates/stadium_editor/editor.html', import.meta.url), 'utf8');
const controller = readFileSync(new URL('../static/stadium_editor/editor.js', import.meta.url), 'utf8');

test('mapped OSM north faces model +Z, with legacy stand IDs kept for capacity', () => {
  // The local OSM extract uses metres east (+x) and north (+z). Its scene
  // alignment rotates it +0.16 radians: north still projects mostly onto +Z.
  const angle = .16;
  assert.ok(Math.cos(angle) > Math.sin(angle));
  assert.deepEqual(SIDES, {
    SUED: 'PLUS_X', NORD: 'MINUS_X', OST: 'PLUS_Z', WEST: 'MINUS_Z',
  });
  const displayed = [
    ['Nord', 'OST', 'ost'],
    ['Ost', 'SUED', 'sued'],
    ['Süd', 'WEST', 'west'],
    ['West', 'NORD', 'nord'],
  ];
  for (const [label, legacyId, field] of displayed) {
    assert.ok(editor.includes(`data-de-stand="${legacyId}">${label} <b>{{ stadium.${field}_standing`));
    assert.ok(editor.includes(`<option value="${legacyId}">${label}</option>`));
  }
  assert.match(controller,
    /dortmundStandLabels = \{OST: 'Nord', SUED: 'Ost', WEST: 'Süd', NORD: 'West'\}/);
});