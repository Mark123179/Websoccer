import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

// The draft module's state machine has no DOM/WebGL dependency.
const source = readFileSync(new URL('../static/stadium_editor/grass_editor.js', import.meta.url), 'utf8');
const stateSource = source.slice(source.indexOf('export const validGrass'), source.indexOf('/** Albedo'));
const {createGrassDraft} = await import('data:text/javascript,' + encodeURIComponent(
  'const GRASS_PRESETS = Object.fromEntries(["A1","A2","A3","A4","B1","B2","B3","C1","C2","D1","D2","D3"].map(k=>[k,true]));\n'
  + stateSource));

test('selection and reset never commit the saved choice', () => {
  const draft = createGrassDraft('A1');
  draft.select('D3');
  assert.equal(draft.selected, 'D3');
  assert.equal(draft.saved, 'A1');
  assert.equal(draft.dirty, true);
  draft.reset();
  assert.equal(draft.selected, 'A1');
  assert.equal(draft.dirty, false);
  assert.throws(()=>draft.select('invalid'));
});

test('a successful pending save commits its snapshot, not a newer unsaved selection', () => {
  const draft = createGrassDraft();
  draft.select('C1');
  const submitted = draft.selected;
  draft.select('A4');
  draft.commit(submitted);
  assert.equal(draft.saved, 'C1');
  assert.equal(draft.selected, 'A4');
  assert.equal(draft.dirty, true);
});

test('missing historical value preserves existing pitch until user chooses otherwise', () => {
  const draft = createGrassDraft();
  assert.equal(draft.selected, 'bestand');
  assert.equal(draft.dirty, false);
  draft.select('B2');
  draft.commit('B2');
  assert.equal(draft.dirty, false);
});
