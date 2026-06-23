(function () {
  'use strict';

  // Hand-justierte Fokus-Ausschnitte (viewBox) je Kontinent. Insel-Territorien
  // (Kanaren, Galápagos, Spitzbergen) bleiben bewusst außen vor, damit der
  // Ausschnitt auf das Festland zentriert ist. viewBox des Welt-SVG: 0 0 1010 666.
  var CONTINENT_VIEW = {
    welt:        '0 0 1010 666',
    europa:      '440 200 188 200',
    suedamerika: '250 415 165 250',
    afrika:      '430 345 165 315',
    asien:       '565 275 370 385'
  };

  function fmtEuro(n) {
    return (Number(n) || 0).toLocaleString('de-DE') + ' \u20ac';
  }

  function clearActive(nodes) {
    nodes.forEach(function (n) { n.classList.remove('is-active'); });
  }

  function readContract() {
    var el = document.getElementById('scout-map-data');
    if (!el) return {};
    var byIso = {};
    try {
      JSON.parse(el.textContent).forEach(function (c) { byIso[c.iso2] = c; });
    } catch (e) { /* ignorieren – Karte bleibt ohne Status */ }
    return byIso;
  }

  document.addEventListener('DOMContentLoaded', function () {
    var scopeKey = document.getElementById('scope_key');
    var scopeType = document.getElementById('scope_type');
    var positionField = document.getElementById('position_field');
    var profileField = document.getElementById('profile_field');
    var regionSelect = document.getElementById('region-select');
    var scopeStatus = document.getElementById('scope-status');
    var continentSelect = document.getElementById('continent-select');
    var mapCanvas = document.getElementById('scout-map-canvas');
    var tooltip = document.getElementById('scout-map-tooltip');
    var mapHint = document.getElementById('scout-map-hint');
    var mapStage = mapCanvas ? mapCanvas.closest('.scout-map-stage') : null;

    var contract = readContract();
    var scopeChips = Array.prototype.slice.call(document.querySelectorAll('.scope-chip'));
    var posChips = Array.prototype.slice.call(document.querySelectorAll('.pos-chip'));
    var profileChips = Array.prototype.slice.call(document.querySelectorAll('.profile-chip'));

    var svgEl = null;            // injiziertes Welt-SVG
    var countryPaths = {};       // ISO2 → <path>

    function highlightCountry(key) {
      Object.keys(countryPaths).forEach(function (iso) {
        countryPaths[iso].classList.toggle('is-selected', iso === key);
      });
    }

    function selectScope(type, key, label) {
      if (scopeType) scopeType.value = type;
      if (scopeKey) scopeKey.value = key;
      clearActive(scopeChips);
      if (type === 'country') {
        scopeChips.forEach(function (c) {
          if (c.getAttribute('data-scope-key') === key) c.classList.add('is-active');
        });
        highlightCountry(key);
        if (regionSelect) regionSelect.value = '';
      } else {
        highlightCountry(null);
      }
      if (scopeStatus) {
        scopeStatus.textContent = '\u2713 ' + (label || key) + ' gew\u00e4hlt';
        scopeStatus.classList.add('ok');
      }
      if (mapHint) mapHint.textContent = (label || key) + ' als Suchgebiet \u00fcbernommen.';
    }

    // ── Tooltip ──────────────────────────────────────────────────────────
    function showTooltip(evt, data) {
      if (!tooltip || !mapStage) return;
      tooltip.innerHTML = '<strong>' + data.name + '</strong><span>' + data.coverage_label + '</span>';
      tooltip.hidden = false;
      var rect = mapStage.getBoundingClientRect();
      var x = evt.clientX - rect.left + 12;
      var y = evt.clientY - rect.top + 12;
      x = Math.min(x, rect.width - tooltip.offsetWidth - 8);
      tooltip.style.left = Math.max(4, x) + 'px';
      tooltip.style.top = Math.max(4, y) + 'px';
    }
    function hideTooltip() { if (tooltip) tooltip.hidden = true; }

    // ── Welt-SVG laden und verdrahten ───────────────────────────────────
    function wirePaths() {
      var paths = svgEl.querySelectorAll('path[data-iso2]');
      Array.prototype.forEach.call(paths, function (p) {
        var iso = p.getAttribute('data-iso2');
        var data = contract[iso];
        if (!data) { p.classList.add('is-out'); return; }
        countryPaths[iso] = p;
        p.classList.add('is-' + data.status);

        p.addEventListener('mousemove', function (e) { showTooltip(e, data); });
        p.addEventListener('mouseleave', hideTooltip);
        p.addEventListener('click', function () {
          if (data.status === 'scoutable') {
            selectScope('country', iso, data.name);
          } else {
            // Gesperrt/​im Aufbau/​nicht verfügbar: wählt nichts, nur Hinweis
            // (ohne jede Poolzahl – kommt direkt aus dem Backend-Vertrag).
            if (mapHint) mapHint.textContent = data.hint;
          }
        });
      });
      // Bereits gewähltes Land (z. B. nach Reload) markieren.
      if (scopeKey && scopeKey.value && countryPaths[scopeKey.value]) {
        highlightCountry(scopeKey.value);
      }
    }

    function focusContinent(key) {
      if (!svgEl) return;
      var vb = CONTINENT_VIEW[key] || CONTINENT_VIEW.welt;
      svgEl.setAttribute('viewBox', vb);
    }

    if (mapCanvas && mapCanvas.getAttribute('data-svg-url')) {
      fetch(mapCanvas.getAttribute('data-svg-url'))
        .then(function (r) { return r.text(); })
        .then(function (txt) {
          mapCanvas.innerHTML = txt;
          svgEl = mapCanvas.querySelector('svg');
          if (!svgEl) return;
          wirePaths();
          focusContinent(continentSelect ? continentSelect.value : 'welt');
        })
        .catch(function () {
          if (mapHint) mapHint.textContent = 'Karte konnte nicht geladen werden.';
        });
    }

    // ── Bedienelemente ──────────────────────────────────────────────────
    scopeChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        selectScope('country', chip.getAttribute('data-scope-key'), chip.textContent.trim());
      });
    });

    if (continentSelect) {
      continentSelect.addEventListener('change', function () {
        focusContinent(continentSelect.value);
      });
    }

    if (regionSelect) {
      regionSelect.addEventListener('change', function () {
        if (!regionSelect.value) return;
        var label = regionSelect.options[regionSelect.selectedIndex].text;
        selectScope('region', regionSelect.value, label);
      });
    }

    posChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        clearActive(posChips);
        chip.classList.add('is-active');
        if (positionField) positionField.value = chip.getAttribute('data-pos') || '';
      });
    });

    profileChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        clearActive(profileChips);
        chip.classList.add('is-active');
        if (profileField) profileField.value = chip.getAttribute('data-profile') || 'ergaenzung';
      });
    });

    // ── Gebots-Dialog ──────────────────────────────────────────────────
    var modal = document.getElementById('bid-modal');
    var bidFindId = document.getElementById('bid-find-id');
    var bidAmount = document.getElementById('bid-amount');
    var bidTitle = document.getElementById('bid-modal-title');
    var bidHint = document.getElementById('bid-min-hint');

    function openBid(find, name, min) {
      if (!modal) return;
      bidFindId.value = find;
      bidAmount.value = min;
      bidTitle.textContent = 'Angebot f\u00fcr ' + name;
      bidHint.textContent = 'Mindestgebot: ' + fmtEuro(min);
      modal.hidden = false;
    }
    function closeBid() { if (modal) modal.hidden = true; }

    document.querySelectorAll('.js-open-bid').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openBid(btn.getAttribute('data-find'), btn.getAttribute('data-name'), btn.getAttribute('data-min'));
      });
    });
    document.querySelectorAll('.js-close-bid').forEach(function (btn) {
      btn.addEventListener('click', closeBid);
    });
    if (modal) {
      modal.addEventListener('click', function (e) { if (e.target === modal) closeBid(); });
    }
  });
})();
