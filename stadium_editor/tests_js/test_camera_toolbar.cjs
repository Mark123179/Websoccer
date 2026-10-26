const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

const source = fs.readFileSync('stadium_editor/static/stadium_editor/camera_toolbar.js', 'utf8');
function fixture() {
  class Element {
    constructor(id) {
      this.id = id;
      this.children = [];
      this.attrs = {};
      this.checked = false;
      this.value = 'orbit';
      this.style = {display: 'none'};
      this.className = '';
      this.classList = {
        contains: name => this.className.split(' ').includes(name),
        add: name => { this.className += ` ${name}`; },
      };
    }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(key, value) { this.attrs[key] = value; }
    removeAttribute(key) { delete this.attrs[key]; }
    after(element) { this.next = element; }
  }
  const nodes = Object.fromEntries(
    ['rot3d', 'stageCamera', 'yawSlider', 'tiltSlider', 'stageDay', 'stageFloodlight', 'roofChk',
      'seatDesignMode', 'clearSeatDesign', 'grassReset', 'grassVariant', 'grassPanel', 'seatPanel']
      .map(id => [id, new Element(id)]),
  );
  nodes.roofChk.checked = true;
  nodes.yawSlider.value = '35';
  nodes.tiltSlider.value = '54';
  nodes.clearSeatDesign.textContent = 'Eigenen Entwurf löschen';
  nodes.grassReset.textContent = 'Gespeicherte Auswahl wiederherstellen';
  nodes.grassPanel.append(nodes.grassVariant, nodes.grassReset);
  const toolbar = new Element('toolbar');
  return {
    nodes, toolbar,
    document: {
      getElementById: id => nodes[id] || null,
      createElement: () => new Element(),
      createElementNS: () => new Element(),
      querySelector: selector => ({
        '.editor-toolbar': toolbar,
        '.grass-editor-controls': nodes.grassPanel,
        '.seat-design-panel': nodes.seatPanel,
      })[selector],
    },
  };
}
test('camera toolbar preserves original inputs, values, listeners and visibility', () => {
  const f = fixture();
  const original = {...f.nodes};
  const listener = () => {};
  f.nodes.stageDay.onchange = listener;
  vm.runInNewContext(source, {document: f.document});
  const row = f.toolbar.next;
  assert.equal(row.children[0], original.rot3d);
  const [camera, angles] = f.nodes.rot3d.children;
  const switches = row.children.at(-1);
  assert.equal(camera.children.at(-1), original.stageCamera);
  assert.equal(angles.children[0].children.at(-1), original.yawSlider);
  assert.equal(angles.children[1].children.at(-1), original.tiltSlider);
  assert.equal(switches.children[0].children[0], original.stageDay);
  assert.equal(original.stageDay.onchange, listener);
  assert.equal(original.stageDay.checked, false);
  assert.equal(original.roofChk.checked, true);
  assert.equal(original.yawSlider.value, '35');
  assert.equal(original.rot3d.style.display, 'none');
  assert.equal(original.stageDay.attrs.role, 'switch');
  assert.equal(switches.attrs['aria-label'], 'Licht und Dach');
  assert.equal(row.children[1], original.grassPanel);
  assert.equal(row.children[2], original.seatPanel);
  assert.equal(original.seatPanel.children[1], original.seatDesignMode);
  assert.equal(original.seatPanel.children[2], original.clearSeatDesign);
  assert.equal(original.clearSeatDesign.attrs['aria-label'], 'Eigenen Entwurf löschen');
  assert.equal(original.grassReset.attrs.title, 'Gespeicherte Auswahl wiederherstellen');
  assert.equal(original.grassPanel.children[0], original.grassVariant);
  vm.runInNewContext(source, {document: f.document});
  assert.equal(f.nodes.rot3d.children[0], camera);
});
test('incomplete pages are left untouched', () => {
  const f = fixture();
  delete f.nodes.stageCamera;
  vm.runInNewContext(source, {document: f.document});
  assert.equal(f.toolbar.next, undefined);
});
