/* ── Modal-Portal (Fixed-Popup im skalierten Stage) ──────────────────────
   Der komplette Seiteninhalt liegt in .dashboard-scaler mit
   transform: scale(--game-scale). Ein transform-Vorfahre fängt
   position:fixed ein — Modals wären falsch verankert/abgeschnitten.
   Lösung (weather.js/showauction-Muster): Beim Laden werden alle
   bekannten Modal-Backdrops an <body> portiert und der Inhalt per
   --game-scale mitskaliert, damit er optisch zur Stage passt.        */
(function () {
    'use strict';

    var SELECTORS = '.tv2-modal-backdrop, .tv2-modal-overlay, .sc-bid-modal';

    function portalAll() {
        document.querySelectorAll(SELECTORS).forEach(function (el) {
            if (el.parentElement !== document.body) {
                document.body.appendChild(el);
            }
            el.classList.add('is-portaled');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', portalAll);
    } else {
        portalAll();
    }
})();
