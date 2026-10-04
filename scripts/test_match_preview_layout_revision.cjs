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
const repairSource = source.slice(source.indexOf("function repairDetails("),
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