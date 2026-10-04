/* Independent shell preference. Never touches game/preview layout storage. */
(() => {
    "use strict";
    const root = document.documentElement;
    const key = "ws:navigation:collapsed";
    let collapsed = false;
    try {
        collapsed = localStorage.getItem(key) === "1";
    } catch {
        // Storage can be denied; the in-memory switch remains fully usable.
    }
    root.dataset.navState = collapsed ? "collapsed" : "expanded";

    document.addEventListener("DOMContentLoaded", () => {
        const toggle = document.getElementById("nav-toggle");
        const search = document.getElementById("nav-search-open");
        const input = document.getElementById("nav-search-input");
        const nav = document.getElementById("main-navigation");
        if (!toggle || !nav) return;
        const desktop = window.matchMedia("(min-width: 761px)");
        nav.querySelectorAll("a, .nav-logout-btn").forEach(action => {
            const label = [...action.querySelectorAll(".nav-label")]
                .map(node => node.textContent.trim()).join(" ");
            if (label) action.dataset.navLabel = label;
        });
        function sync() {
            const effective = collapsed && desktop.matches;
            root.dataset.navState = collapsed ? "collapsed" : "expanded";
            toggle.setAttribute("aria-expanded", String(!effective));
            const label = effective ? "Navigation ausklappen" : "Navigation einklappen";
            toggle.setAttribute("aria-label", label);
            toggle.title = label;
            // A responsive switch must not leave focus on a now-hidden control.
            if (!effective && document.activeElement === search) toggle.focus();
        }
        function setCollapsed(value) {
            collapsed = value;
            try {
                localStorage.setItem(key, value ? "1" : "0");
            } catch {
                // Preference persistence is optional, navigation is not.
            }
            sync();
        }
        toggle.addEventListener("click", () => setCollapsed(!collapsed));
        search?.addEventListener("click", () => {
            setCollapsed(false);
            input?.focus();
        });
        desktop.addEventListener("change", sync);
        sync();
    }, {once: true});
})();