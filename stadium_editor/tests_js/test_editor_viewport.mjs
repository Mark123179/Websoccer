import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import '../static/stadium_editor/editor_viewport.js';

const preferences = globalThis.StadiumEditorViewport;
const memory = () => {
  const values = new Map();
  return {getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value)};
};
test('local zoom survives reload and remains stadium-specific', () => {
  const storage = memory();
  const value = {factor: 2.5, center: [12, -9]};
  assert.equal(preferences.save(storage, 'club-114', value), true);
  assert.deepEqual(preferences.load(storage, 'club-114'), value);
  assert.deepEqual(preferences.load(storage, 'club-115'), preferences.defaults());
});
test('blocked storage and invalid preferences cannot break the editor', () => {
  const blocked = {getItem() {throw Error('blocked');},
    setItem() {throw Error('blocked');}};
  assert.deepEqual(preferences.load(blocked, 'view'), preferences.defaults());
  assert.equal(preferences.save(blocked, 'view', preferences.defaults()), false);
  for (const value of ['broken', 'null', '{"factor":-1,"center":[0,0]}',
    '{"factor":2,"center":[null,0]}']) {
    assert.deepEqual(preferences.load({getItem: () => value}, 'view'),
      preferences.defaults());
  }
  assert.equal(preferences.clamp(100), 8);
  assert.equal(preferences.clamp(.01), .25);
});
test('wheel zoom keeps its world anchor, survives resize and never edits design', () => {
  const editor = fs.readFileSync(new URL(
    '../static/stadium_editor/editor.js', import.meta.url), 'utf8');
  const functions = editor.slice(editor.indexOf('function fitView(){'),
    editor.indexOf('function editorBackground(){'));
  const context = vm.createContext({
    viewportPreferences: preferences, viewportStorage: memory(), viewportKey: '114',
    viewport2D: preferences.defaults(), D: {unchanged: true}, view: '2d',
    W: 800, H: 600, SC: 1, CX: 400, CY: 300,
    document: {getElementById: () => ({textContent: '', title: ''})},
    renderAll() {},
  });
  vm.runInContext(`function fitBaseView(){SC=2;CX=W/2;CY=H/2;}\n${functions}
    fitView();
    const anchor=[230,190], before=s2w(...anchor);
    zoom2D(1.25,anchor);
    const after=s2w(...anchor);
    if(Math.hypot(before[0]-after[0],before[1]-after[1])>1e-9)
      throw Error('Zoom anchor moved');
    W=1200;H=800;fitView();
  `, context);
  assert.equal(context.viewport2D.factor, 1.25);
  assert.equal(context.SC, 2.5);
  assert.deepEqual(context.D, {unchanged: true});
  assert.deepEqual(preferences.load(context.viewportStorage, '114'), context.viewport2D);
});
