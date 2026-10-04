/* No-browser tests for early preference restore and usable denied storage. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("game/static/game/js/navigation-shell.js", "utf8");
function boot(value, denied = false, mobile = false) {
    const events = {}, listeners = {}, attributes = {};
    let persisted = value, focused = false;
    const toggle = {
        setAttribute: (key, value) => { attributes[key] = value; },
        addEventListener: (name, fn) => { listeners.toggle = fn; },
        focus: () => {},
    };
    const search = {addEventListener: (name, fn) => { listeners.search = fn; }};
    const label = {textContent: "Übersicht"};
    const action = {dataset: {}, querySelectorAll: () => [label]};
    const nav = {querySelectorAll: () => [action]};
    const root = {dataset: {}};
    const desktop = {matches: !mobile, addEventListener: (name, fn) => { listeners.media = fn; }};
    const document = {
        documentElement: root, activeElement: null,
        addEventListener: (name, fn) => { events[name] = fn; },
        getElementById: id => ({
            "nav-toggle": toggle, "main-navigation": nav, "nav-search-open": search,
            "nav-search-input": {focus: () => { focused = true; }},
        }[id]),
    };
    vm.runInNewContext(source, {
        document, window: {matchMedia: () => desktop},
        localStorage: {
            getItem: key => { if (denied) throw Error("blocked"); return persisted; },
            setItem: (key, value) => { if (denied) throw Error("blocked"); persisted = value; },
        },
    });
    const earlyState = root.dataset.navState;
    events.DOMContentLoaded();
    return {root, attributes, listeners, desktop, action, earlyState,
        persisted: () => persisted, focused: () => focused};
}
for (const invalid of [undefined, null, "", "true", "collapsed", "2", "{bad}"]) {
    assert.equal(boot(invalid).earlyState, "expanded");
}
const saved = boot("1");
assert.equal(saved.earlyState, "collapsed", "preference applied before DOMContentLoaded");
assert.equal(saved.attributes["aria-expanded"], "false");
assert.equal(saved.action.dataset.navLabel, "Übersicht");
saved.listeners.toggle();
assert.equal(saved.root.dataset.navState, "expanded");
assert.equal(saved.persisted(), "0");
saved.listeners.toggle();
assert.equal(saved.attributes["aria-expanded"], "false");
saved.listeners.search();
assert.equal(saved.root.dataset.navState, "expanded");
assert.equal(saved.focused(), true);
assert.equal(saved.persisted(), "0");
const blocked = boot("1", true);
assert.equal(blocked.earlyState, "expanded");
blocked.listeners.toggle();
assert.equal(blocked.root.dataset.navState, "collapsed");
blocked.listeners.toggle();
assert.equal(blocked.root.dataset.navState, "expanded");
const responsive = boot("1", false, true);
assert.equal(responsive.attributes["aria-expanded"], "true", "mobile remains expanded");
responsive.desktop.matches = true;
responsive.listeners.media();
assert.equal(responsive.attributes["aria-expanded"], "false", "desktop preference restored");
console.log("Navigation: early restore, invalid/blocked storage, reversible toggle, search focus, mobile OK.");