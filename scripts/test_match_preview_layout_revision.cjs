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
function boot(value, revision = "2", denied = false) {
    const storage = new Map(value ? [[key, value]] : []);
    const sandbox = {
        document: {
            querySelector: () => ({dataset: {layoutOwner: "42", layoutRevision: revision},
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