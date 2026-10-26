import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createTransitionController,
  interpolate,
  isConfirmedAllianzFacadeMaterial,
  projectFacadeUv,
  smoothstep,
  sourceMaterialFinish,
  splitFacadeTriangles,
  supportsAllianzPresentation,
} from './allianz_presentation.js';

const source = '52c0d0916cc4e780bd9d3d4cc60363b134195125ce95cd7a34a87b2c4a48c0b3';
const presentation = {clubFmiId: 915, sourceSha256: source};
const manifest = {clubFmiId: 915, sourceSha256: source, assetVersion: '7bc8ec0fcf20c166'};
const coverEntry = {
  name: 'cover_1.003',
  pathId: '-2079065756245898804',
  bounds: [[-114.229, 36.8816757, -129.998], [114.230, 52.1960754, 129.998]],
};

function makeClock() {
  let time = 0, nextId = 0;
  const callbacks = new Map();
  return {
    callbacks,
    now: () => time,
    requestFrame(callback) { const id = ++nextId; callbacks.set(id, callback); return id; },
    cancelFrame(id) { callbacks.delete(id); },
    advance(ms) {
      time += ms;
      const pending = [...callbacks.entries()];
      callbacks.clear();
      for (const [, callback] of pending) callback(time);
    },
  };
}

test('transition easing is bounded, smooth and reaches the endpoint', () => {
  assert.equal(smoothstep(-1), 0);
  assert.equal(smoothstep(0.5), 0.5);
  assert.equal(smoothstep(2), 1);
  assert.equal(interpolate(0.2, 0.8, 0.5), 0.5);
});

test('a transition can be interrupted from its current interpolated state', () => {
  const clock = makeClock(), seen = [];
  let renderedFrames = 0;
  const transition = createTransitionController({
    initial: {day: 1}, apply: state => seen.push(state.day),
    onFrame: () => { renderedFrames++; },
    now: clock.now, requestFrame: clock.requestFrame, cancelFrame: clock.cancelFrame,
  });
  assert.equal(renderedFrames, 1);
  transition.set({day: 0});
  clock.advance(750);
  assert.equal(transition.current.day, 0.5);
  assert.equal(renderedFrames, 2, 'each scheduled lighting frame requests an on-demand render');
  transition.set({day: 1});
  clock.advance(1500);
  assert.equal(transition.current.day, 1);
  assert.equal(seen.at(-1), 1);
  assert.equal(renderedFrames, 3);
  transition.dispose();
});

test('facade source selection is exact to the retained cover mesh and material', () => {
  assert.equal(isConfirmedAllianzFacadeMaterial(coverEntry, {material: 'view.006', texture: null}), true);
  assert.equal(isConfirmedAllianzFacadeMaterial({...coverEntry, name: 'front3_0.003'},
    {material: 'view.006', texture: null}), false);
  assert.equal(isConfirmedAllianzFacadeMaterial(coverEntry, {material: 'view.006', texture: 'source.webp'}), false);
  assert.equal(isConfirmedAllianzFacadeMaterial({...coverEntry, pathId: 'other'},
    {material: 'view.006', texture: null}), false);
  assert.equal(isConfirmedAllianzFacadeMaterial({...coverEntry, bounds: [[-114, 25, -130], [114, 53, 130]]},
    {material: 'view.006', texture: null}), false);
});

test('facade partition selects outward near-vertical shell faces only', () => {
  const positions = new Float32Array([
    10,38,0, 10,39,0, 10,38,1,
    10,50,0, 10,50,1, 11,50,0,
    10,38,0, 10,38,1, 10,39,0,
  ]);
  const result = splitFacadeTriangles(positions, new Uint32Array([0,1,2,3,4,5,6,7,8]));
  assert.deepEqual(result.facadeIndices, [0,1,2]);
  assert.deepEqual(result.remainingIndices, [3,4,5,6,7,8]);
  const uv = projectFacadeUv(positions);
  assert.equal(uv[0], .5);
  assert.ok(Math.abs(uv[1] - (38 - 36.8) / (52.2 - 36.8)) < .00001);
});

test('interior material treatments follow source steel-frame and wall names only', () => {
  assert.deepEqual(sourceMaterialFinish('st011_stfr103.003'),
    {role: 'steel-frame', roughness: .56, metalness: .24});
  assert.deepEqual(sourceMaterialFinish('st011_wall101.003'),
    {role: 'wall', roughness: .92, metalness: 0});
  assert.equal(sourceMaterialFinish('st011_star002.079'), null);
  assert.equal(sourceMaterialFinish('st011_vnyl101.002'), null);
});

test('presentation support is exact to source and club; other clubs are a no-op', () => {
  assert.equal(supportsAllianzPresentation(presentation, manifest), true);
  assert.equal(supportsAllianzPresentation({...presentation, clubFmiId: 916}, manifest), false);
  assert.equal(supportsAllianzPresentation(presentation, {...manifest, sourceSha256: 'other'}), false);
});

test('reduced motion snaps immediately and disposal cancels pending work', () => {
  const clock = makeClock(), seen = [];
  const transition = createTransitionController({
    initial: {day: 1}, apply: state => seen.push(state.day),
    reducedMotion: true, now: clock.now,
    requestFrame: clock.requestFrame, cancelFrame: clock.cancelFrame,
  });
  transition.set({day: 0});
  assert.equal(transition.current.day, 0);
  assert.equal(clock.callbacks.size, 0);
  transition.set({day: 1}, {immediate: false});
  assert.equal(transition.current.day, 1);
  transition.dispose();

  const cancellable = createTransitionController({
    initial: {day: 1}, apply: () => {}, now: clock.now,
    requestFrame: clock.requestFrame, cancelFrame: clock.cancelFrame,
  });
  cancellable.set({day: 0});
  assert.equal(clock.callbacks.size, 1);
  cancellable.dispose();
  assert.equal(clock.callbacks.size, 0);
  clock.advance(2000);
  assert.equal(cancellable.current.day, 1);
});
