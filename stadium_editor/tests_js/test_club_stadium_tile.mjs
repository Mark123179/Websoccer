import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {setImmediate} from 'node:timers/promises';

const source = readFileSync(new URL('../../game/static/game/js/club-stadium.js', import.meta.url), 'utf8');
const rendererSource = readFileSync(new URL('../static/stadium_editor/dortmund_editor_scene.js', import.meta.url), 'utf8');

function harness(mount) {
  const events = {}, documentEvents = {}, motionEvents = {};
  const status = {hidden: false, textContent: 'Stadion wird geladen …'};
  const host = {parentElement: {querySelector: () => status}};
  const motion = {
    matches: false,
    addEventListener: (name, fn) => { motionEvents[name] = fn; },
    removeEventListener: name => { delete motionEvents[name]; },
  };
  const document = {
    currentScript: {dataset: {sceneUrl: '/scene.js'}},
    hidden: false,
    querySelector: () => host,
    addEventListener: (name, fn) => { documentEvents[name] = fn; },
    removeEventListener: name => { delete documentEvents[name]; },
  };
  let intersection, disconnected = false, loads = 0;
  vm.runInNewContext(source.replace('await import(script.dataset.sceneUrl)', 'await loadRenderer(script.dataset.sceneUrl)'), {
    document,
    window: {
      matchMedia: () => motion,
      addEventListener: (name, fn) => { events[name] = fn; },
    },
    IntersectionObserver: class {
      constructor(fn) { intersection = fn; }
      observe(element) { assert.equal(element, host); }
      disconnect() { disconnected = true; }
    },
    loadRenderer: async url => {
      assert.equal(url, '/scene.js'); loads++;
      return {mountDortmundScene: mount};
    },
  });
  return {
    events, documentEvents, motionEvents, document, motion, status,
    visible: value => intersection([{isIntersecting: value}]),
    get disconnected() { return disconnected; },
    get loads() { return loads; },
  };
}

test('loads only on visibility, auto-rotates without scenery or manual controls', async () => {
  const calls = [], activity = [];
  const h = harness(async options => {
    calls.push(options);
    return {setActive: value => activity.push(value), dispose() {}};
  });
  assert.equal(h.loads, 0);
  h.visible(true); await setImmediate();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].autoRotate, true);
  assert.equal(calls[0].interactive, false);
  assert.equal(calls[0].includeSurroundings, false);
  assert.equal(calls[0].compact, true);
  assert.equal(calls[0].compactZoom, 1.2);
  assert.equal(calls[0].transparentBackground, true);
  assert.equal(h.status.hidden, true);
  assert.equal(activity.at(-1), true);
  h.visible(false); assert.equal(activity.at(-1), false);
  h.visible(true); await setImmediate(); assert.equal(h.loads, 1);
  h.document.hidden = true; h.documentEvents.visibilitychange();
  assert.equal(activity.at(-1), false);
  h.document.hidden = false; h.documentEvents.visibilitychange();
  assert.equal(activity.at(-1), true);
  h.motion.matches = true; h.motionEvents.change();
  assert.equal(activity.at(-1), false);
});

test('cleans resources on departure and pauses rather than destroying a cached page', async () => {
  let disposed = 0; const activity = [];
  const h = harness(async () => ({
    setActive: value => activity.push(value), dispose: () => disposed++,
  }));
  h.visible(true); await setImmediate();
  h.events.pagehide({persisted: true});
  assert.equal(disposed, 0); assert.equal(activity.at(-1), false);
  h.events.pageshow(); assert.equal(activity.at(-1), true);
  h.events.pagehide({persisted: false});
  assert.equal(disposed, 1); assert.equal(h.disconnected, true);
  assert.equal(Object.keys(h.documentEvents).length, 0);
  assert.equal(Object.keys(h.motionEvents).length, 0);
});

test('a scene completing after departure is disposed, not attached as an active viewer', async () => {
  let resolve, disposed = 0;
  const h = harness(() => new Promise(done => { resolve = done; }));
  h.visible(true); await setImmediate();
  h.events.pagehide({persisted: false});
  resolve({dispose: () => disposed++, setActive() { assert.fail('must not animate'); }});
  await setImmediate(); assert.equal(disposed, 1);
});

test('WebGL failure remains visible instead of silently leaving an empty tile', async () => {
  const h = harness(async () => { throw new Error('WebGL konnte nicht gestartet werden.'); });
  h.visible(true); await setImmediate();
  assert.equal(h.status.hidden, false);
  assert.equal(h.status.textContent, 'WebGL konnte nicht gestartet werden.');
});

test('renderer defaults preserve editor controls and surroundings; tile rotation is time based', () => {
  assert.match(rendererSource, /includeSurroundings = true, interactive = true, autoRotate = false, compact = false/);
  assert.match(rendererSource, /if \(includeSurroundings\) \{\s*environment = buildDortmundSurroundings/);
  assert.match(rendererSource, /if \(interactive\) \{\s*controls.addEventListener/);
  assert.match(rendererSource, /if \(autoRotate && lastAnimationTime !== null\)/);
  assert.match(rendererSource, /\(timestamp - lastAnimationTime\) \/ 1000/);
  assert.match(rendererSource, /if \(disposed \|\| !animationActive\) return/);
  assert.match(rendererSource, /transparentBackground = false/);
  assert.match(rendererSource, /alpha: transparentBackground/);
  assert.match(rendererSource, /if \(transparentBackground\) renderer.setClearColor\(0x000000, 0\)/);
});