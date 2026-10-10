import assert from 'node:assert/strict';
import test from 'node:test';
import {createImageBackground} from './image_background_scene.js';

function fixture() {
  const decodes = [];
  globalThis.Image = class {
    naturalWidth = 1024;
    naturalHeight = 512;
    decode() {
      return new Promise((resolve, reject) => decodes.push({resolve, reject, image: this}));
    }
  };
  const node = () => ({
    dataset: {}, children: [],
    append(child) { this.children.push(child); },
    prepend(child) { this.children.unshift(child); },
    remove() { this.removed = true; },
    removeAttribute(key) { delete this[key]; },
  });
  globalThis.document = {createElement: node};
  const host = node();
  const config = {
    referenceSize: [1024, 512], aspect: 2,
    pitchCorners: [[421, 245], [604, 245], [621, 358], [403, 358]],
    pitchHalfSize: [34.080013275146484, 52.95001220703125],
    images: {day: {url: '/day.webp', size: [1024, 512]},
      night: {url: '/night.webp', size: [1024, 512]}},
  };
  return {host, decodes, background: createImageBackground(host, config)};
}

test('photo and lighting commit together, newest requested profile wins', async () => {
  const {background, decodes, host} = fixture();
  const commits = [];
  const day = background.setProfile('day', value => commits.push(value));
  const night = background.setProfile('night', value => commits.push(value));
  decodes[1].resolve(); assert.equal(await night, true);
  decodes[0].resolve(); assert.equal(await day, false);
  assert.deepEqual(commits, ['night']);
  assert.equal(host.dataset.imageProfile, 'night');
});
test('failed decode preserves old picture and permits retry', async () => {
  const {background, decodes, host} = fixture();
  const commits = [];
  const day = background.setProfile('day', value => commits.push(value));
  decodes[0].resolve(); await day;
  const failed = background.setProfile('night', value => commits.push(value));
  decodes[1].reject(new Error('network'));
  await assert.rejects(failed, /nicht geladen/);
  assert.equal(host.dataset.imageProfile, 'day');
  assert.deepEqual(commits, ['day']);
  const retried = background.setProfile('night', value => commits.push(value));
  decodes[2].resolve(); await retried;
  assert.equal(host.dataset.imageProfile, 'night');
});
test('dispose prevents pending decode from committing or recreating the image', async () => {
  const {background, decodes} = fixture();
  const commits = [];
  const pending = background.setProfile('night', value => commits.push(value));
  background.dispose();
  decodes[0].resolve();
  assert.equal(await pending, false);
  assert.equal(background.container.removed, true);
  assert.deepEqual(commits, []);
});
test('an image with an incompatible format cannot change lighting', async () => {
  const {background, decodes} = fixture();
  const commits = [];
  const pending = background.setProfile('night', value => commits.push(value));
  decodes[0].image.naturalHeight = 700;
  decodes[0].resolve();
  await assert.rejects(pending, /Bildformat/);
  assert.deepEqual(commits, []);
});
