/* ── Wetter-Popup-Portal ──────────────────────────────────────────────────
   Die animierte "SPIELTAG-WETTER"-Karte steckt als .wx-pop im .wx-badge.
   Kalender-Kacheln haben overflow:hidden und der komplette Stage-Inhalt
   liegt in einem transform:scale()-Container (.dashboard-scaler) — ein
   position:fixed-Popup INNERHALB davon wäre falsch verankert und würde
   abgeschnitten. Deshalb: Beim ersten Hover wird das Popup an
   document.body portiert, fixed positioniert (Viewport-Koordinaten aus
   getBoundingClientRect) und mit --game-scale mitskaliert.             */
(function () {
    'use strict';

    var GAP = 9;       /* Abstand Badge ↔ Karte (unskaliert)  */
    var EDGE = 8;      /* Mindestabstand zum Viewport-Rand    */
    var current = null;

    function gameScale() {
        var v = parseFloat(
            getComputedStyle(document.documentElement).getPropertyValue('--game-scale')
        );
        return (v && v > 0) ? v : 1;
    }

    function place(badge, pop) {
        var scale = gameScale();
        var rect = badge.getBoundingClientRect();
        var w = pop.offsetWidth * scale;
        var h = pop.offsetHeight * scale;

        var left = rect.left + rect.width / 2 - w / 2;
        left = Math.max(EDGE, Math.min(left, window.innerWidth - w - EDGE));

        /* Bevorzugt über dem Icon; passt es dort nicht (Kalender ganz
           oben im Viewport), öffnet die Karte nach unten. */
        var top = rect.top - h - GAP * scale;
        if (top < EDGE) {
            top = rect.bottom + GAP * scale;
        }
        top = Math.min(top, window.innerHeight - h - EDGE);

        pop.style.left = left + 'px';
        pop.style.top = top + 'px';
        pop.style.transformOrigin = 'top left';
        pop.style.transform = 'scale(' + scale + ')';
    }

    function show(badge) {
        if (current === badge) { return; }
        hide();
        var pop = badge.__wxPop || badge.querySelector('.wx-pop');
        if (!pop) { return; }
        if (!badge.__wxPop) {
            badge.__wxPop = pop;
            pop.style.position = 'fixed';
            pop.style.bottom = 'auto';
            pop.style.margin = '0';
            document.body.appendChild(pop);
        }
        place(badge, pop);
        pop.classList.add('wx-pop--open');
        current = badge;
    }

    function hide() {
        if (!current) { return; }
        if (current.__wxPop) {
            current.__wxPop.classList.remove('wx-pop--open');
        }
        current = null;
    }

    document.addEventListener('mouseover', function (e) {
        var t = e.target;
        if (!t || !t.closest) { return; }
        var badge = t.closest('.wx-badge');
        if (badge && !badge.classList.contains('wx-badge--dim')) {
            show(badge);
        } else if (current && !current.contains(t)) {
            hide();
        }
    });

    document.addEventListener('focusin', function (e) {
        var t = e.target;
        if (!t || !t.closest) { return; }
        var badge = t.closest('.wx-badge');
        if (badge && !badge.classList.contains('wx-badge--dim')) {
            show(badge);
        } else {
            hide();
        }
    });

    document.addEventListener('focusout', function (e) {
        var t = e.target;
        if (t && t.closest && t.closest('.wx-badge')) { hide(); }
    });

    /* Beim Scrollen (auch in inneren Containern) und Resize nachführen. */
    window.addEventListener('scroll', function () {
        if (current && current.__wxPop) { place(current, current.__wxPop); }
    }, true);
    window.addEventListener('resize', function () {
        if (current && current.__wxPop) { place(current, current.__wxPop); }
    });

    /* Debug/Verifikation ohne Maus: ?wxdebug=N öffnet das Popup des
       N-ten sichtbaren Wetter-Icons (0-basiert) dauerhaft. */
    var dbg = /[?&]wxdebug=(\d+)/.exec(window.location.search);
    if (dbg) {
        window.addEventListener('load', function () {
            setTimeout(function () {
                var badges = document.querySelectorAll('.wx-badge:not(.wx-badge--dim)');
                var b = badges[parseInt(dbg[1], 10)];
                if (b) { show(b); }
            }, 350);
        });
    }
})();
