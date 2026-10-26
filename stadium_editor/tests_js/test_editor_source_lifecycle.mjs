import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source = readFileSync('stadium_editor/static/stadium_editor/editor.js', 'utf8');
function extract(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n}', start) + 2;
  return source.slice(start, end);
}
function fixture() {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) {
      const classes = new Set();
      nodes.set(id, {
        checked: false, hidden: false, textContent: '', value: 'orbit', style: {},
        classList: {
          add: name => classes.add(name),
          remove: name => classes.delete(name),
          contains: name => classes.has(name),
          toggle(name, on) { if (on) classes.add(name); else classes.delete(name); },
        },
      });
    }
    return nodes.get(id);
  };
  const updates = [], errors = [], legacy = [];
  const context = vm.createContext({
    EDITOR: {unityScene: true, sourceSeats: true},
    view: '2d', D: {}, stageThree: null, stageScene: null, stageAdapter: null,
    stageUpdateTimer: 0, roofOn: true, isDortmundScene: false, seatDesignMode: 'custom',
    seatDesignDraft: () => ({mode: 'custom', blocks: [{id: 1, rle: [3]}]}),
    showSeatStatus() {}, toast: message => errors.push(message),
    renderBase() {}, renderBlocks() {}, renderOverlay() {},
    render3D: () => legacy.push('canvas'),
    updateDortmundStage() {}, clearTimeout() {}, setTimeout() {},
    document: {
      getElementById: node,
      querySelectorAll: () => ['cvBase', 'cvBlocks', 'cvOverlay'].map(node),
    },
    ensureThreeStage() { context.showSourceSceneStatus('Original-Stadionmodell wird geladen …'); },
  });
  for (const name of ['renderAll', 'showSourceSceneStatus', 'showDortmundSceneError',
    'scheduleStageDesignUpdate', 'useLegacyThreePreview', 'activateThreeStage', 'setView']) {
    vm.runInContext(extract(name), context);
  }
  const renderer = {update: async state => { updates.push(state); }};
  return {context, node, updates, errors, legacy, renderer};
}

test('source loading and repeated redraws never show the old blueprint', () => {
  const {context, node, legacy} = fixture();
  context.setView('3d');
  context.renderAll();
  assert.equal(legacy.length, 0);
  assert.equal(node('sourceSceneStatus').hidden, false);
  assert.match(node('sourceSceneStatus').textContent, /wird geladen/);
  assert.equal(node('stage').classList.contains('stage-source-pending'), true);
  context.setView('2d');
  assert.equal(node('sourceSceneStatus').hidden, true);
  assert.equal(node('stage').classList.contains('stage-source-pending'), false);
});

test('roof off/on reaches the Bayern renderer together with the saved seat draft', async () => {
  const {context, node, updates, renderer} = fixture();
  context.stageThree = renderer;
  context.setView('3d');
  context.roofOn = false;
  node('stageDay').checked = true;
  node('stageFloodlight').checked = true;
  context.renderAll();
  context.roofOn = true;
  context.renderAll();
  await Promise.resolve();
  const last = updates.slice(-2);
  assert.deepEqual(last.map(update => update.roofVisible), [false, true]);
  for (const update of last) {
    assert.equal(update.day, true);
    assert.equal(update.floodlight, true);
    assert.equal(update.seatDesign.mode, 'custom');
    assert.equal(update.seatDesign.blocks[0].id, 1);
    assert.equal(update.camera, 'orbit');
  }
});

test('source-ready clears the loading overlay; failures never activate the legacy preview', () => {
  const {context, node, legacy, renderer} = fixture();
  context.setView('3d');
  context.stageThree = renderer;
  context.activateThreeStage();
  assert.equal(node('sourceSceneStatus').hidden, true);
  assert.equal(node('stage').classList.contains('stage-three-ready'), true);
  context.useLegacyThreePreview();
  assert.equal(legacy.length, 0);
  assert.equal(node('sourceSceneStatus').hidden, false);
  assert.match(node('sourceSceneStatus').textContent, /nicht verfügbar/);
  context.setView('2d');
  assert.equal(node('sourceSceneStatus').hidden, true);
});

test('all direct canvas callbacks are guarded for registered source models', () => {
  assert.match(extract('render3D'), /if\(EDITOR\.unityScene\) return;/);
  assert.match(extract('ensureThreeStage'), /showSourceSceneStatus\('Original-Stadionmodell wird geladen/);
});

test('unregistered stadiums retain their schematic preview', () => {
  const {context, legacy} = fixture();
  context.EDITOR.unityScene = false;
  context.EDITOR.sourceSeats = false;
  context.view = '3d';
  context.renderAll();
  assert.equal(legacy.length, 1);
});
