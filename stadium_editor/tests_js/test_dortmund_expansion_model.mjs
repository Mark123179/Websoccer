import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {countState, nextStep, warpPoint, addedChairPositions, terraceTriangles} from
  '../static/stadium_editor/dortmund_expansion_model.mjs';

const data = JSON.parse(readFileSync(
  new URL('../static/stadium_editor/dortmund_original/expansion-data.json', import.meta.url)));
const zero = {back: 0, front: 0, left: 0, right: 0};

test('measured seat steps meet the minimum and the cap, on every side', () => {
  assert.equal(data.baselineSeats, 71659);
  for (const side of Object.keys(zero)) {
    const {steps, count} = nextStep(data, zero, side);
    assert.ok(count.added >= 1000, `${side}: at least 1000 seats`);
    assert.equal(count.added, addedChairPositions(data, count.rows, side).length);
    const template = data.sides[side].template[0].position;
    const added = addedChairPositions(data, count.rows, side)[0].position;
    assert.equal(added[data.sides[side].axis],
      template[data.sides[side].axis] + data.sides[side].sign * data.rowDepth,
      `${side}: first added seat must not duplicate the occupied source row`);
    assert.ok(terraceTriangles(data, count.rows, side).length > 0,
      `${side}: added seats must have a connected surface`);
    assert.ok(count.total <= 120000);
    assert.ok(data.sides[side].roofExtent +
      count.rows[side] * data.rowDepth <=
      data.sides[side].pylonExtent - data.clearance);
    let current = steps;
    while (!nextStep(data, current, side).reason) {
      current = nextStep(data, current, side).steps;
    }
    assert.ok(nextStep(data, current, side).reason, `${side}: must stop`);
  }
});

test('four independent sides and their corners share one continuous deformation', () => {
  const steps = {back: 1, front: 0, left: 1, right: 0};
  const {rows, added} = countState(data, steps);
  assert.equal(added, rows.back * data.sides.back.template.length +
    rows.left * data.sides.left.template.length);
  const source = [93, 43, 119], corner = warpPoint(source, data, rows);
  assert.ok(corner[0] > source[0]);
  assert.ok(corner[1] > source[1]);
  assert.ok(corner[2] > source[2]);
  assert.deepEqual(warpPoint(source, data, rows), corner);
  assert.deepEqual(warpPoint([93, 0, 119], data, rows), [93, 0, 119],
    'pylon foot is anchored');
  assert.deepEqual(warpPoint(source, data, countState(data, zero).rows), source,
    'the unmodified original is preserved');
  const opposite = countState(data, {back: 1, front: 1, left: 0, right: 0});
  assert.ok(opposite.added >= 2000);
});

test('each of the four roof corners follows both adjacent stand changes', () => {
  for (const [xSide, zSide, x, z] of [
    ['back', 'left', 93, 119],
    ['back', 'right', 93, -115],
    ['front', 'left', -93, 119],
    ['front', 'right', -93, -115],
  ]) {
    const steps = {...zero, [xSide]: 1, [zSide]: 1};
    const {rows} = countState(data, steps);
    const moved = warpPoint([x, 40, z], data, rows);
    assert.ok(Math.abs(moved[0]) > Math.abs(x), `${xSide}/${zSide} x`);
    assert.ok(Math.abs(moved[2]) > Math.abs(z), `${xSide}/${zSide} z`);
    assert.ok(moved[1] > 40, `${xSide}/${zSide} roof rises`);
  }
});

test('measured geometry stops before the independent 120,000-seat ceiling', () => {
  const maximum = Object.fromEntries(Object.entries(data.sides).map(
    ([side, info]) => [side, Math.floor(info.maxRows / info.rowsPerStep)]));
  assert.equal(countState(data, maximum).total, 85833);
  for (const side of Object.keys(maximum)) {
    assert.ok(nextStep(data, maximum, side).reason);
  }
  assert.throws(() => countState({...data, limit: 80000}, maximum), RangeError);
});