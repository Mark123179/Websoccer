/* Regression checks for browser-local layout preservation without a browser. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname,
    "../game/static/game/js/match-preview-layout.js"), "utf8");
const prefix = source.slice(0, source.indexOf("// Stable presentation slots"));
const key = "fm:match-preview:layout:1:42";
const frame = {x: 0, y: 0, width: 100, height: 100, hidden: false};
function boot(value, revision = "2", denied = false, detailPatch = "0") {
    const storage = new Map(value ? [[key, value]] : []);
    const sandbox = {
        document: {
            querySelector: () => ({dataset: {layoutOwner: "42", layoutRevision: revision,
                layoutDetailPatch: detailPatch},
                querySelector: () => ({})}),
            getElementById: () => ({}),
        },
        localStorage: {
            getItem: name => { if (denied) throw Error("denied"); return storage.get(name); },
            setItem: (name, data) => storage.set(name, data),
        },
    };
    vm.runInNewContext(prefix +
        "globalThis.result = {saved, previousLayout, revision, backupKey, storageError};})();", sandbox);
    return {...sandbox.result, storage};
}
const old = JSON.stringify({version: 1, nodes: {"home-0": frame}});
const rebased = boot(old);
assert.equal(rebased.saved, null);
assert.equal(rebased.previousLayout, old);
assert.equal(rebased.storage.get(key), old, "old data must not be deleted on load");
assert.equal(rebased.backupKey, `${key}:before-revision-2`);
const current = JSON.stringify({version: 1, revision: 2, nodes: {"home-0": frame}});
assert.equal(boot(current).saved.revision, 2);
assert.equal(boot(current).previousLayout, null);
assert.equal(boot(current, "3").saved, null);
assert.equal(boot(current, "3").previousLayout, current);
assert.equal(boot(current, "3").backupKey, `${key}:before-revision-3`);
const detailBoot = boot(JSON.stringify({version: 1, revision: 3,
    nodes: {"home-0": frame}}), "3", false, "1");
assert.equal(detailBoot.saved.revision, 3, "detail patch must not discard the custom layout");
assert.ok(detailBoot.previousLayout);
assert.equal(detailBoot.backupKey, `${key}:before-revision-3:details-1`);
assert.equal(boot(JSON.stringify({version: 1, revision: 3,
    nodes: {"home-0": frame}}), "3").saved.revision, 3);
assert.equal(boot(old, "1").saved.revision, 1, "other page revisions still accept old frames");
assert.equal(boot('{"version":9}').saved, null);
assert.equal(boot(old, "2", true).saved, null);
assert.ok(boot(old, "2", true).storageError);
const backup = source.indexOf("localStorage.setItem(backupKey, previousLayout)");
assert.ok(backup > 0);
assert.ok(backup < source.indexOf("localStorage.setItem(key, JSON.stringify(value))"),
    "original must be backed up before an explicit save replaces it");
console.log("Layout revisions: preserve originals, rebase old geometry, retain current edits, reject invalid data.");

const kitItems = new Map();
function item(id, width, height) {
    const record = {id, size: {width, height}};
    kitItems.set(id, record);
    return record;
}
item("home-kit-0", 220, 260); item("away-kit-0", 240, 280);
item("home-form-0", 220, 260); item("away-form-0", 240, 280);
item("home-crest-0", 220, 260); item("venue-0", 220, 260);
const layout = {version: 1, detailPatch: 0, nodes: {
    "home-kit-0": {...frame}, "away-kit-0": {...frame, x: -10, y: 30, width: 140, height: 90},
    "home-crest-0": {...frame, x: 30, y: 10, width: 40, height: 25},
    "home-form-0": {...frame, height: 10}, "away-form-0": {...frame, height: 10},
    "venue-0": {...frame, y: 5},
}};
const originalAway = JSON.stringify(layout.nodes["away-kit-0"]);
const repairSource = source.slice(source.indexOf("function repairInitialDetails("),
    source.indexOf("function updateSelection("));
vm.runInNewContext(repairSource + "repairDetails(layout);", {
    layout, byId: kitItems, detailPatch: 1, dimensions: record => record.size,
    paint: () => {}, baseline: {}, items: [],
});
assert.equal(JSON.stringify(layout.nodes["away-kit-0"]), originalAway);
assert.ok(Math.abs(layout.nodes["home-kit-0"].width * 220 -
    layout.nodes["away-kit-0"].width * 240) < 0.001);
assert.ok(Math.abs(layout.nodes["home-kit-0"].height * 260 -
    layout.nodes["away-kit-0"].height * 280) < 0.001);
assert.equal(layout.nodes["home-kit-0"].layer, 0);
assert.equal(layout.nodes["home-crest-0"].layer, 2);
assert.ok(layout.nodes["away-form-0"].y >
    layout.nodes["away-kit-0"].y + layout.nodes["away-kit-0"].height);
assert.equal(layout.detailPatch, 1);
console.log("Detail repair: away kit untouched, home matches actual size, crest above, form below.");

const parent = {node: {querySelector: () => ({
    dataset: {mpLayoutItem: "absence-heading-1"},
})}};
const empty = {id: "suspension-empty-0", parent, size: {width: 200, height: 100}};
const heading = {id: "absence-heading-1", node: {scrollHeight: 24}};
const footerItems = new Map([[empty.id, empty], [heading.id, heading]]);
const secondPatch = {version: 1, detailPatch: 1, nodes: {
    "suspension-empty-0": {...frame, y: 0},
    "absence-heading-1": {...frame, y: 5, height: 20},
    "away-kit-0": {...layout.nodes["away-kit-0"]},
    "home-kit-0": {...layout.nodes["home-kit-0"]},
    "model-0": {...frame, x: 12, y: 34},
}};
const unchanged = JSON.stringify([
    secondPatch.nodes["away-kit-0"], secondPatch.nodes["home-kit-0"],
    secondPatch.nodes["model-0"],
]);
vm.runInNewContext(repairSource + "repairDetails(layout);", {
    layout: secondPatch, byId: footerItems, detailPatch: 2,
    dimensions: record => record.size, paint: () => {},
    items: [empty], baselineRefHeight: 0,
});
assert.equal(secondPatch.nodes[empty.id].y, 35);
assert.equal(secondPatch.detailPatch, 2);
assert.equal(JSON.stringify([
    secondPatch.nodes["away-kit-0"], secondPatch.nodes["home-kit-0"],
    secondPatch.nodes["model-0"],
]), unchanged);
console.log("Footer repair: clear heading gap, existing kit/model geometry preserved.");

const column = {
    clientTop: 0, getBoundingClientRect: () => ({top: 0}),
};
const photo = {id: "venue-photo-0", node: {
    offsetWidth: 200,
    getBoundingClientRect: () => ({left: 0, right: 200, top: 100, bottom: 200, width: 200}),
    closest: () => ({getBoundingClientRect: () => ({bottom: 500})}),
}};
const injuries = {id: "absence-group-0", parent: {node: column}};
const suspensions = {id: "absence-group-1", parent: {node: column}};
const expanded = {detailPatch: 2, nodes: {
    [photo.id]: {...frame, y: -20},
    [injuries.id]: {...frame}, [suspensions.id]: {...frame},
    "model-viewport-0": {...frame, y: -15},
}};
const pictureFrames = JSON.stringify([
    expanded.nodes[photo.id], expanded.nodes["model-viewport-0"],
]);
vm.runInNewContext(repairSource + "expandFooter(layout);", {
    layout: expanded, detailPatch: 3,
    byId: new Map([[photo.id, photo], [injuries.id, injuries], [suspensions.id, suspensions]]),
    items: [], baselineSizes: new Map([
        [injuries.id, {height: 60}], [suspensions.id, {height: 30}],
    ]),
    parentOf: item => item.parent.node,
    dimensions: () => ({width: 200, height: 400}),
    paint: () => {},
});
assert.equal(expanded.nodes[injuries.id].y, 53);
assert.equal(expanded.nodes[suspensions.id].y, 70);
assert.equal(expanded.detailPatch, 3);
assert.equal(JSON.stringify([
    expanded.nodes[photo.id], expanded.nodes["model-viewport-0"],
]), pictureFrames);
console.log("Expanded footer: follows elevated picture, preserves both picture frames.");