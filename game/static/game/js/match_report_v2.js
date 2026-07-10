(function () {
    "use strict";
    var FONT = "Inter, sans-serif";

    function drawMomentum(box, momentum, homeCrestUrl, awayCrestUrl, homeInitial, awayInitial) {
        if (!momentum || !momentum.length) { box.innerHTML = ''; return; }
        var W = 1000, H = 330, L = 76, R = 980, T = 52, B = 292, mid = (T + B) / 2, amp = (B - T) / 2 - 8;
        var s = momentum;
        function xF(m) { return L + (m / (s.length - 1)) * (R - L); }
        function yF(v) { return mid - v * amp; }
        var hp = "M " + L + " " + mid, ap = "M " + L + " " + mid, m, x, y;
        for (m = 0; m < s.length; m++) {
            x = xF(m).toFixed(1);
            y = yF(s[m]);
            hp += " L " + x + " " + Math.min(y, mid).toFixed(1);
            ap += " L " + x + " " + Math.max(y, mid).toFixed(1);
        }
        hp += " L " + R + " " + mid + " Z";
        ap += " L " + R + " " + mid + " Z";

        var gx = [0, 15, 30, 45, 60, 75, 90], vlines = "", hlines = "", xlabels = "", hh = [-0.66, -0.33, 0.33, 0.66];
        var scaleX = function (minute) { return xF(Math.min(s.length - 1, minute)); };
        gx.forEach(function (mm) {
            if (mm >= s.length) return;
            vlines += '<line x1="' + scaleX(mm) + '" y1="' + T + '" x2="' + scaleX(mm) + '" y2="' + B + '" stroke="rgba(255,255,255,.05)"/>';
        });
        hh.forEach(function (v) {
            hlines += '<line x1="' + L + '" y1="' + yF(v) + '" x2="' + R + '" y2="' + yF(v) + '" stroke="rgba(255,255,255,.04)"/>';
        });
        gx.forEach(function (mm) {
            if (mm >= s.length) return;
            xlabels += '<text x="' + scaleX(mm) + '" y="' + (B + 18) + '" fill="rgba(244,251,255,.38)" font-size="11" font-weight="900" text-anchor="middle" font-family="' + FONT + '">' + (mm === 45 ? "HT" : mm + "'") + '</text>';
        });

        var crestOrInitial = function (url, initial, cy) {
            if (url) return '<image href="' + url + '" x="3" y="' + cy + '" width="26" height="26" preserveAspectRatio="xMidYMid meet"/>';
            return '<text x="16" y="' + (cy + 19) + '" fill="rgba(244,251,255,.7)" font-size="13" font-weight="900" text-anchor="middle" font-family="' + FONT + '">' + initial + '</text>';
        };

        box.innerHTML =
            '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">' +
            '<defs>' +
            '<linearGradient id="spbGH" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#22e6ff" stop-opacity=".45"/><stop offset="100%" stop-color="#22e6ff" stop-opacity=".04"/></linearGradient>' +
            '<linearGradient id="spbGA" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ffd166" stop-opacity=".04"/><stop offset="100%" stop-color="#ffd166" stop-opacity=".42"/></linearGradient>' +
            '</defs>' +
            '<g>' + vlines + hlines + '</g>' +
            '<line x1="' + L + '" y1="' + mid + '" x2="' + R + '" y2="' + mid + '" stroke="rgba(255,255,255,.35)" stroke-width="1.2"/>' +
            '<line x1="' + scaleX(45) + '" y1="' + (T - 6) + '" x2="' + scaleX(45) + '" y2="' + B + '" stroke="rgba(255,255,255,.28)" stroke-dasharray="4 4"/>' +
            '<path d="' + hp + '" fill="url(#spbGH)" stroke="#22e6ff" stroke-width="1.4"/>' +
            '<path d="' + ap + '" fill="url(#spbGA)" stroke="#ffd166" stroke-width="1.4"/>' +
            xlabels +
            crestOrInitial(homeCrestUrl, homeInitial, T - 2) +
            '<text x="16" y="' + (mid + 4) + '" fill="rgba(244,251,255,.5)" font-size="10" font-weight="900" text-anchor="middle" font-family="' + FONT + '">0</text>' +
            crestOrInitial(awayCrestUrl, awayInitial, B - 24) +
            '</svg>';
    }

    function switchTab(name) {
        Array.prototype.forEach.call(document.querySelectorAll(".spb-report .tab"), function (t) {
            t.classList.toggle("active", t.getAttribute("data-tab") === name);
        });
        Array.prototype.forEach.call(document.querySelectorAll(".spb-report .panel"), function (p) {
            p.hidden = p.getAttribute("data-tab") !== name;
        });
        var panel = document.querySelector('.spb-report .panel[data-tab="' + name + '"]');
        if (panel) { panel.style.animation = "none"; void panel.offsetWidth; panel.style.animation = ""; }
        if (history.replaceState) {
            var url = new URL(window.location.href);
            url.hash = name;
            history.replaceState(null, "", url);
        }
    }

    function wireFilter(filterId, listId) {
        var fr = document.getElementById(filterId), list = document.getElementById(listId);
        if (!fr || !list) return;
        var chips = fr.querySelectorAll(".chip");
        var map = { tore: "goal", karten: "card", wechsel: "sub" };
        Array.prototype.forEach.call(chips, function (c) {
            c.addEventListener("click", function () {
                var f = c.getAttribute("data-f"), want = map[f];
                Array.prototype.forEach.call(chips, function (x) { x.classList.toggle("active", x === c); });
                Array.prototype.forEach.call(list.querySelectorAll(".ev-row"), function (r) {
                    r.style.display = (f === "alle" || r.getAttribute("data-type") === want) ? "" : "none";
                });
            });
        });
    }

    function init() {
        var root = document.querySelector(".spb-report");
        if (!root) return;

        var dataEl = document.getElementById("spb-momentum-data");
        if (dataEl) {
            try {
                var payload = JSON.parse(dataEl.textContent);
                var boxes = document.querySelectorAll(".spb-momentum-box");
                Array.prototype.forEach.call(boxes, function (box) {
                    drawMomentum(box, payload.momentum, payload.home_crest, payload.away_crest, payload.home_initial, payload.away_initial);
                });
            } catch (e) { /* keine Momentumdaten verfügbar */ }
        }

        Array.prototype.forEach.call(root.querySelectorAll(".tab"), function (t) {
            t.addEventListener("click", function () { switchTab(t.getAttribute("data-tab")); });
        });

        wireFilter("tickerFilter", "tickerFull");
        wireFilter("ovTickerFilter", "ovTickerList");

        var tt = document.getElementById("toTicker");
        if (tt) tt.addEventListener("click", function () { switchTab("ticker"); });

        var initialTab = (window.location.hash || '').replace('#', '');
        if (initialTab && document.querySelector('.spb-report .tab[data-tab="' + initialTab + '"]')) {
            switchTab(initialTab);
        }
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
