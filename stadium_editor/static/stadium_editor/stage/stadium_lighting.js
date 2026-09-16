const clamp = (value, minimum, maximum) =>
  Math.max(minimum, Math.min(maximum, value));

function targetFor(position) {
  return [
    clamp(-position[0] * 0.35, -36, 36),
    clamp(-position[1] * 0.25, -22, 22),
    0,
  ];
}

function mastPlan(scene, floodlights) {
  const bounds = scene.standsBounds || [-90, -60, 90, 60];
  const count = Math.max(1, Math.min(12, Math.round(floodlights.count || 4)));
  const height = Math.max(16, Number(floodlights.height) || 32);
  const corners = [
    [bounds[2] + 6, bounds[3] + 6],
    [bounds[0] - 6, bounds[3] + 6],
    [bounds[0] - 6, bounds[1] - 6],
    [bounds[2] + 6, bounds[1] - 6],
  ];
  return Array.from({length: count}, (_unused, index) => {
    const corner = corners[index % corners.length];
    const level = Math.floor(index / corners.length);
    const offset = level * 2;
    const position = [
      corner[0] + Math.sign(corner[0] || 1) * offset,
      corner[1] + Math.sign(corner[1] || 1) * offset,
      height + 1.5,
    ];
    return {
      id: `mast-${index + 1}`,
      kind: 'mast',
      position,
      target: targetFor(position),
      poleHeight: height,
    };
  });
}

function rimPlan(scene) {
  const highest = new Map();
  for (const block of scene.blocks || []) {
    if (!Array.isArray(block.quad) || block.quad.length !== 4) continue;
    const key = `${block.stand}|${block.order ?? 0}`;
    const current = highest.get(key);
    if (!current || Number(block.z1) > Number(current.z1) ||
        (Number(block.z1) === Number(current.z1) &&
          String(block.id).localeCompare(String(current.id)) < 0)) {
      highest.set(key, block);
    }
  }
  const fixtures = [];
  const blocks = [...highest.values()].sort((left, right) =>
    String(left.stand).localeCompare(String(right.stand)) ||
    Number(left.order || 0) - Number(right.order || 0) ||
    String(left.id).localeCompare(String(right.id)));
  for (const block of blocks) {
    const left = block.quad[3];
    const right = block.quad[2];
    const length = Math.hypot(right[0] - left[0], right[1] - left[1]);
    const count = Math.max(1, Math.round(length / 12));
    for (let index = 0; index < count; index += 1) {
      const t = (index + 0.5) / count;
      const position = [
        left[0] + (right[0] - left[0]) * t,
        left[1] + (right[1] - left[1]) * t,
        Number(block.z1) + 1.6,
      ];
      fixtures.push({
        id: `rim-${block.id}-${index + 1}`,
        kind: 'rim',
        position,
        target: targetFor(position),
        poleHeight: 1.6,
      });
    }
  }
  return fixtures;
}

function sideOf(position) {
  if (Math.abs(position[0]) >= Math.abs(position[1])) {
    return position[0] >= 0 ? 'east' : 'west';
  }
  return position[1] >= 0 ? 'north' : 'south';
}

function boundedRimSources(fixtures) {
  const groups = new Map();
  for (const fixture of fixtures) {
    const side = sideOf(fixture.position);
    if (!groups.has(side)) groups.set(side, []);
    groups.get(side).push(fixture);
  }
  const selected = [];
  for (const side of ['north', 'east', 'south', 'west']) {
    const fixturesOnSide = groups.get(side) || [];
    fixturesOnSide.sort((left, right) => {
      const axis = side === 'north' || side === 'south' ? 0 : 1;
      return left.position[axis] - right.position[axis] ||
        left.id.localeCompare(right.id);
    });
    const indices = fixturesOnSide.length <= 3
      ? fixturesOnSide.map((_fixture, index) => index)
      : [.2, .5, .8].map(ratio =>
        Math.min(
          fixturesOnSide.length - 1,
          Math.floor(fixturesOnSide.length * ratio),
        ));
    for (const index of new Set(indices)) {
      selected.push(fixturesOnSide[index]);
    }
  }
  return selected.map((fixture, index) => ({
    ...fixture,
    id: `rim-source-${index + 1}`,
  }));
}

export function buildFloodlightPlan(scene) {
  const floodlights = scene?.steckbrief?.floodlights;
  if (!floodlights) return {type: 'none', fixtures: [], sources: []};
  const type = floodlights.type === 'rim' ? 'rim' : 'mast';
  const fixtures = type === 'rim'
    ? rimPlan(scene)
    : mastPlan(scene, floodlights);
  return {
    type,
    fixtures,
    sources: type === 'rim' ? boundedRimSources(fixtures) : [...fixtures],
  };
}