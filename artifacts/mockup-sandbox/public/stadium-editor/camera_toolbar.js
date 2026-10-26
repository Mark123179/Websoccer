/* Present existing controls without replacing their state or event targets. */
(function () {
  'use strict';
  const bar = document.getElementById('rot3d');
  if (!bar || bar.classList.contains('camera-toolbar')) return;
  const icons = {
    camera: '<path d="M14 4h-4L8 7H4v13h16V7h-4z"/><circle cx="12" cy="13" r="4"/>',
    angle: '<path d="M4 19h16M5 19 17 5"/><path d="M10 19a5 5 0 0 0-2-4"/>',
    rotate: '<path d="M20 7v5h-5"/><path d="M19 12a7 7 0 1 0-2 5"/>',
    day: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
    light: '<path d="m5 3 14 5-3 8L2 11zM9 14l-2 7m7-5 2 5M19 13l3 2m-4 2 2 3"/>',
    roof: '<path d="m2 11 10-8 10 8M5 9v12h14V9"/>',
  };
  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML = icons[name];
    return svg;
  }
  const camera = document.getElementById('stageCamera');
  const yaw = document.getElementById('yawSlider');
  const tilt = document.getElementById('tiltSlider');
  const toggles = [
    ['stageDay', 'Tag', 'day'],
    ['stageFloodlight', 'Flutlicht', 'light'],
    ['roofChk', 'Dach', 'roof'],
  ].map(([id, text, glyph]) => ({input: document.getElementById(id), text, glyph}));
  if (!camera || !yaw || !tilt || toggles.some(item => !item.input)) return;
  const cameraGroup = document.createElement('label');
  cameraGroup.className = 'camera-preset';
  const caption = document.createElement('span');
  caption.textContent = 'Kamera';
  cameraGroup.append(icon('camera'), caption, camera);
  const angleGroup = document.createElement('div');
  angleGroup.className = 'camera-angles';
  for (const [input, text, glyph] of [[yaw, 'Drehung', 'rotate'], [tilt, 'Neigung', 'angle']]) {
    const label = document.createElement('label');
    label.className = 'camera-angle';
    const title = document.createElement('span');
    title.textContent = text;
    input.removeAttribute('style');
    label.append(icon(glyph), title, input);
    angleGroup.append(label);
  }
  const switches = document.createElement('div');
  switches.className = 'camera-switches';
  switches.setAttribute('role', 'group');
  switches.setAttribute('aria-label', 'Licht und Dach');
  for (const {input, text, glyph} of toggles) {
    const label = document.createElement('label');
    label.className = 'camera-toggle';
    input.setAttribute('role', 'switch');
    const title = document.createElement('span');
    title.textContent = text;
    const track = document.createElement('span');
    track.className = 'camera-toggle-track';
    track.setAttribute('aria-hidden', 'true');
    label.append(input, icon(glyph), title, track);
    switches.append(label);
  }
  bar.classList.add('camera-toolbar');
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', '3D-Ansicht einstellen');
  bar.replaceChildren(cameraGroup, angleGroup, switches);
  document.querySelector('.editor-toolbar')?.after(bar);
})();
