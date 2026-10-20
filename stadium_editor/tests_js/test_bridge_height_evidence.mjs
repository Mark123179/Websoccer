import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../static/stadium_editor/stage/vendor/three.module.js';
import {buildDortmundSurroundings} from '../static/stadium_editor/dortmund_surroundings.js';
import {bridgeHeightEvidence, bridgeHeightLabel, mountBridgeHeightNotice, BRIDGE_HEIGHT_LABEL}
  from '../static/stadium_editor/bridge_height_evidence.js';

function fixture() {
  const p = [[50, 50], [70, 50]];
  return {roads: [{p, w: 2}], groundLevel: 2.1,
    groundCutout: [[-10, -10], [10, -10], [10, 10], [-10, 10]],
    heightEvidence: {bridges: [{index: 0, osm: 'way/5229974', name: 'Aachener Straße',
      editorPoints: structuredClone(p), sourceTags: {bridge: 'yes', layer: '1'},
      status: 'unresolved_terrain_derivation', deckSource: null}]}};
}

test('bound bridge provenance does not change a single rendered ground or road vertex', () => {
  const data = fixture(), before = JSON.stringify(data);
  const marked = buildDortmundSurroundings(THREE, data);
  const legacy = structuredClone(data);
  delete legacy.heightEvidence;
  const plain = buildDortmundSurroundings(THREE, legacy);
  for (const name of ['ENV_ROADS', 'ENV_GROUND', 'ENV_ROAD_CONTOURS']) {
    assert.deepEqual(marked.group.getObjectByName(name).geometry.attributes.position.array,
      plain.group.getObjectByName(name).geometry.attributes.position.array);
  }
  assert.equal(marked.group.userData.bridgeHeightEvidence[0].deckSource, null);
  assert.equal(JSON.stringify(data), before);
  marked.dispose(); plain.dispose();
});

test('stale geometry, duplicate index and unsupported measured deck claims fail explicitly', () => {
  for (const change of [
    d => d.roads[0].p[0][0]++,
    d => d.heightEvidence.bridges.push(structuredClone(d.heightEvidence.bridges[0])),
    d => d.heightEvidence.bridges[0].deckSource = 'DGM1',
    d => d.heightEvidence.bridges[0].status = 'measured',
    d => d.heightEvidence.bridges[0].sourceTags.bridge = 'no',
    d => d.heightEvidence.bridges[0].sourceTags.bridge = ' ',
  ]) {
    const data = fixture(); change(data);
    assert.throws(() => bridgeHeightEvidence(data), /Brücken-Höhenbeleg/);
  }
  assert.deepEqual(bridgeHeightEvidence({}), []);
  assert.throws(() => bridgeHeightEvidence({heightEvidence: {bridges: null}}), /Ungültige/);
});

test('notice is visible text, source names remain plain text, disposal removes it', () => {
  let child;
  const node = {dataset: {}, style: {}, setAttribute(k, v) {this[k] = v;},
    remove() {child = null;}};
  const element = {ownerDocument: {createElement: () => node}, append(n) {child = n;}};
  const rows = fixture().heightEvidence.bridges;
  rows[0].name = '<img onerror=bad()>';
  const dispose = mountBridgeHeightNotice(element, rows);
  assert.equal(child.textContent, BRIDGE_HEIGHT_LABEL);
  assert.equal(child.role, 'note');
  assert.match(child.title, /<img/);
  assert.equal(child.innerHTML, undefined);
  dispose(); assert.equal(child, null);
  mountBridgeHeightNotice(element, []); assert.equal(child, null);
});

test('old DGM roads get an explicit unclassified warning, not invented bridge IDs', () => {
  const data = fixture();
  delete data.heightEvidence;
  data.groundElevation = {source: 'Geobasis NRW DGM1'};
  assert.deepEqual(bridgeHeightEvidence(data), []);
  assert.match(bridgeHeightLabel(data), /ohne Einzelzuordnung/);
  data.heightEvidence = {bridges: []};
  assert.equal(bridgeHeightLabel(data), ''); // explicitly checked empty inventory
  assert.equal(bridgeHeightLabel({roads: data.roads}), ''); // unchanged flat legacy scenes
});
