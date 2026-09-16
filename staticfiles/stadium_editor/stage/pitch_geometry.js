export const PITCH = Object.freeze({length: 105, width: 68});

export function pitchWorldPoint(point, rotation) {
  const c = Math.cos(rotation), s = Math.sin(rotation);
  const rotatedX = point[0] * c - point[1] * s;
  const rotatedY = point[0] * s + point[1] * c;
  return [-rotatedX, rotatedY];
}

export function buildPitchLayout(rotation, stripeCount = 10) {
  if (!Number.isFinite(rotation) ||
      !Number.isInteger(stripeCount) || stripeCount < 1 || stripeCount > 100) {
    throw new Error('Ungültige Spielfeldgeometrie.');
  }
  const hx = PITCH.length / 2, hy = PITCH.width / 2;
  const stripeWidth = PITCH.length / stripeCount;
  const point = value => pitchWorldPoint(value, rotation);
  const stripes = Array.from({length: stripeCount}, (_unused, index) => {
    const x0 = -hx + stripeWidth * index;
    const x1 = x0 + stripeWidth;
    return {
      index,
      quad: [
        point([x0, -hy]), point([x1, -hy]),
        point([x1, hy]), point([x0, hy]),
      ],
    };
  });
  const lines = [];
  const line = (name, x0, y0, x1, y1) => lines.push({
    name, from: point([x0, y0]), to: point([x1, y1]),
  });
  line('touchline-near', -hx, -hy, hx, -hy);
  line('touchline-far', -hx, hy, hx, hy);
  line('goal-line-left', -hx, -hy, -hx, hy);
  line('goal-line-right', hx, -hy, hx, hy);
  line('halfway', 0, -hy, 0, hy);
  for (const side of [-1, 1]) {
    const goalX = side * hx;
    const penaltyX = side * (hx - 16.5);
    const goalAreaX = side * (hx - 5.5);
    line(`penalty-top-${side}`, goalX, -20.16, penaltyX, -20.16);
    line(`penalty-bottom-${side}`, goalX, 20.16, penaltyX, 20.16);
    line(`penalty-side-${side}`, penaltyX, -20.16, penaltyX, 20.16);
    line(`goal-area-top-${side}`, goalX, -9.16, goalAreaX, -9.16);
    line(`goal-area-bottom-${side}`, goalX, 9.16, goalAreaX, 9.16);
    line(`goal-area-side-${side}`, goalAreaX, -9.16, goalAreaX, 9.16);
  }
  return {stripes, lines, center: point([0, 0]), radius: 9.15};
}