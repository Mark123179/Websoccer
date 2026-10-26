import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createTransitionController,
  buildAllianzLowerFacadeClosure,
  interpolate,
  isConfirmedAllianzFacadeMaterial,
  isConfirmedAllianzLowerFacade,
  projectFacadeUv,
  runtimeFixtureIntensity,
  smoothstep,
  sourceMaterialFinish,
  splitFacadeTriangles,
  splitLowerFacadeTriangles,
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

test('facade partition excludes the low inner roof return and inward walls', () => {
  const positions = new Float32Array([
    10,38,0, 10,39,0, 10,38,1,
    10,48,0, 10,48,1, 11,48,0,
    10,38,0, 10,38,1, 10,39,0,
  ]);
  const result = splitFacadeTriangles(positions, new Uint32Array([0,1,2,3,4,5,6,7,8]));
  assert.deepEqual(result.facadeIndices, [0,1,2]);
  assert.deepEqual(result.remainingIndices, [3,4,5,6,7,8]);
  const uv = projectFacadeUv(positions);
  assert.equal(uv[0], .5);
  assert.ok(Math.abs(uv[1] - (38 - 36.8) / (52.2 - 36.8)) < .00001);
});

test('facade includes the sloped seam row and outer roof, not inner return or underside', () => {
  const positions = new Float32Array([
    100,51,0, 100,51,1, 99,51.3,0,
    100,52.18,0, 100,52.18,1, 99,52.18,0,
    60,48,0, 60,48,1, 61,48,0,
    100,51,0, 100,51,1, 101,51,0,
  ]);
  const result = splitFacadeTriangles(positions, [0,2,1,3,5,4,6,7,8,9,11,10]);
  assert.deepEqual(result.facadeIndices, [0,2,1,3,5,4]);
  assert.deepEqual(result.remainingIndices, [6,7,8,9,11,10]);
});

test('Allianz photometric calibration preserves other stadiums and source values', () => {
  const fixture = {intensity:25, representedIds:['a','b','c','d']};
  assert.equal(runtimeFixtureIntensity(fixture), 400);
  assert.equal(runtimeFixtureIntensity(fixture, true), 3200);
  assert.deepEqual(fixture, {intensity:25, representedIds:['a','b','c','d']});
});

test('the grey inner roof return extends to the next circumferential source ring', () => {
  const positions = new Float32Array([
    62,49.67,0, 62,49.67,1, 65,50.08,0,
    65,50.08,0, 65,50.08,1, 68,50.5,0,
  ]);
  const result = splitFacadeTriangles(positions, [0,1,2,3,4,5]);
  assert.deepEqual(result.remainingIndices, [0,1,2]);
  assert.deepEqual(result.facadeIndices, [3,4,5]);
});

test('interior material treatments follow source steel-frame and wall names only', () => {
  assert.deepEqual(sourceMaterialFinish('st011_stfr103.003'),
    {role: 'steel-frame', roughness: .56, metalness: .24});
  assert.deepEqual(sourceMaterialFinish('st011_wall101.003'),
    {role: 'wall', roughness: .92, metalness: 0});
  assert.equal(sourceMaterialFinish('st011_star002.079'), null);
  assert.equal(sourceMaterialFinish('st011_vnyl101.002'), null);
});

test('lower facade is limited to the confirmed untextured perimeter wall source', () => {
  const entry = {name:'back1_probe_notdemo_1.003',pathId:'-3161811761645632254'};
  const part = {material:'st011_wall200.012',texture:null};
  assert.equal(isConfirmedAllianzLowerFacade(entry,part),true);
  assert.equal(isConfirmedAllianzLowerFacade({...entry,pathId:'wrong'},part),false);
  assert.equal(isConfirmedAllianzLowerFacade(entry,{...part,texture:'concrete.webp'}),false);
  assert.equal(isConfirmedAllianzLowerFacade({name:'back3_0.003'},part),false);
});

test('lower facade lights the upper perimeter only, with exterior-facing winding', () => {
  const positions = new Float32Array([
    100,29.108,0, 100,29.108,1, 100,34.508,0,
    100,15,0, 100,15,1, 100,29.108,0,
    100,34.508,0, 100,34.508,1, 101,34.508,0,
  ]);
  const split = splitLowerFacadeTriangles(positions,[0,1,2,3,4,5,6,7,8]);
  assert.deepEqual(split.facadeIndices,[0,2,1]);
  assert.deepEqual(split.remainingIndices,[3,4,5,6,7,8]);
});

test('derived lower facade closes only the gap between source wall profile bands', () => {
  const profile = [];
  for (let i = 0; i < 16; i++) {
    const a = i * Math.PI * 2 / 16;
    const r = 90 + 12 * Math.cos(a * 2);
    profile.push(r * Math.cos(a), 15.3734, r * Math.sin(a));
    profile.push(r * Math.cos(a), 29.1077, r * Math.sin(a));
  }
  const result = buildAllianzLowerFacadeClosure([new Float32Array(profile)], {samples: 64});
  assert.equal(result.positions.length, 64 * 2 * 3);
  assert.equal(result.uvs.length, 64 * 2 * 2);
  assert.equal(result.indices.length, 64 * 6);
  const heights = result.positions.filter((_, i) => i % 3 === 1);
  assert.ok(heights.slice(0, 64).every(value => Math.abs(value - 29.1077) < 1e-5));
  assert.ok(heights.slice(64).every(value => Math.abs(value - 15.3734) < 1e-5));
  assert.deepEqual(result.sourceProfile, {
    lowerY: 15.3734, upperY: 29.1077, lowerSamples: 16, upperSamples: 16,
  });
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
