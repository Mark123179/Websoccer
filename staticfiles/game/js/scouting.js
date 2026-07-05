(function () {
  'use strict';

  /* Kontinent-Fokus-ViewBoxen – exakt aus der Vorlage übernommen
     (projizierte Natural-Earth-Pixel des world.svg, viewBox 5.6 19.4 988.8 386.2).
     preserveAspectRatio="xMidYMid meet" lässt jeden Kontinent vollständig in die
     Stage einpassen; Letterbox-Ränder zeigen nur Ozean/Radar. */
  var CONTINENT_VIEW = {
    welt:        '5.6 19.4 988.8 386.2',
    europa:      '463.9 50 155.5 108.3',
    nordamerika: '27.8 44.4 333.3 191.7',
    suedamerika: '269.4 211.1 138.9 194.5',
    afrika:      '444.4 141.7 202.8 211.1',
    asien:       '572.2 77.8 344.5 202.8',
    ozeanien:    '800 266.7 200 122.2'
  };

  /* Regionen gehören zu einem Mutterkontinent (steuert das Dimming). */
  var REGION_CONT = {
    eu_west: 'europa', eu_central: 'europa', eu_south: 'europa', eu_east: 'europa',
    eu_north: 'europa', eu_balkan: 'europa', eu_britain: 'europa', eu_iberia: 'europa',
    na_usa: 'nordamerika', na_canada: 'nordamerika', na_mexico: 'nordamerika', na_caribbean: 'nordamerika',
    sa_brasil: 'suedamerika', sa_laplata: 'suedamerika',
    af_maghreb: 'afrika', af_west: 'afrika',
    as_west: 'asien', as_central: 'asien', as_south: 'asien',
    as_southeast: 'asien', as_east: 'asien', as_russia: 'asien',
    oc_australia: 'ozeanien', oc_newzealand: 'ozeanien'
  };

  /* Eigene Zoom-Ausschnitte je Region (exakt aus der Vorlage), damit jede Region
     auf ihr Gebiet heranzoomt. Regionen ohne Eintrag fallen auf ihren
     Mutterkontinent zurück. */
  var REGION_VIEW = {
    eu_west:       '472.2 97.2 69.5 38.9',
    eu_central:    '513.9 97.2 58.3 27.8',
    eu_south:      '472.2 119.4 105.6 33.3',
    eu_east:       '544.4 83.3 83.3 44.4',
    eu_north:      '511.1 52.8 77.8 47.2',
    eu_balkan:     '536.1 116.7 47.2 27.8',
    eu_britain:    '469.4 80.6 38.9 33.3',
    eu_iberia:     '472.2 127.8 36.1 25',
    na_usa:        '152.8 113.9 163.9 69.4',
    na_canada:     '108.3 55.6 247.2 77.8',
    na_mexico:     '172.2 158.3 113.9 72.2',
    na_caribbean:  '250 175 86.1 50',
    sa_brasil:     '291.7 233.3 113.9 111.1',
    sa_laplata:    '291.7 305.6 69.4 100',
    af_maghreb:    '475 144.4 91.7 33.3',
    af_west:       '450 200 94.4 41.7',
    as_west:       '572.2 133.3 102.8 83.3',
    as_central:    '627.8 94.4 116.7 58.3',
    as_south:      '666.7 147.2 105.6 88.9',
    as_southeast:  '755.6 186.1 138.9 94.4',
    as_east:       '777.8 100 127.8 94.4',
    as_russia:     '577.8 61.1 116.7 69.5',
    oc_australia:  '811.1 277.8 119.4 94.4',
    oc_newzealand: '944.4 338.9 55.6 50'
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
    var scopeKey      = document.getElementById('scope_key');
    var scopeType     = document.getElementById('scope_type');
    var positionField = document.getElementById('position_field');
    var profileField  = document.getElementById('profile_field');
    var regionSelect  = document.getElementById('region-select');
    var scopeStatus   = document.getElementById('scope-status');
    var continentSelect = document.getElementById('continent-select');
    var mapCanvas     = document.getElementById('scout-map-canvas');
    var tooltip       = document.getElementById('scout-map-tooltip');
    var mapHint       = document.getElementById('scout-map-hint');
    var mapStage      = mapCanvas ? mapCanvas.closest('.sc-map-stage') : null;

    var contract      = readContract();
    var scopeChips    = Array.prototype.slice.call(document.querySelectorAll('.scope-chip'));
    var posChips      = Array.prototype.slice.call(document.querySelectorAll('.pos-chip'));
    var profileChips  = Array.prototype.slice.call(document.querySelectorAll('.profile-chip'));

    var svgEl         = null;
    var countryPaths  = {};

    /* ── ViewBox-Animation ────────────────────────────────────────────── */
    var vbRAF;
    function zoomTo(targetStr, instant) {
      if (!svgEl || !targetStr) return;
      var target = targetStr.split(/\s+/).map(Number);
      var start  = (svgEl.getAttribute('viewBox') || CONTINENT_VIEW.welt).split(/\s+/).map(Number);
      cancelAnimationFrame(vbRAF);
      if (instant) { svgEl.setAttribute('viewBox', targetStr); return; }
      var t0  = performance.now(), dur = 580;
      function ease(t) { return t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t+2,2)/2; }
      function frame(now) {
        var k = Math.min(1, (now - t0) / dur), e = ease(k);
        svgEl.setAttribute('viewBox', target.map(function(v, i){ return (start[i]+(v-start[i])*e).toFixed(2); }).join(' '));
        if (k < 1) vbRAF = requestAnimationFrame(frame);
        else svgEl.setAttribute('viewBox', targetStr);
      }
      vbRAF = requestAnimationFrame(frame);
    }

    function applyDimming(key) {
      if (!svgEl) return;
      var all = svgEl.querySelectorAll('path[data-iso2]');
      Array.prototype.forEach.call(all, function (p) {
        if (!key || key === 'welt') { p.classList.remove('is-dimmed'); }
        else { p.classList.toggle('is-dimmed', p.getAttribute('data-continent') !== key); }
      });
    }

    function focusContinent(key, instant) {
      zoomTo(CONTINENT_VIEW[key] || CONTINENT_VIEW.welt, instant);
      applyDimming(key);
    }

    function focusRegion(key) {
      var cont = REGION_CONT[key] || 'welt';
      zoomTo(REGION_VIEW[key] || CONTINENT_VIEW[cont] || CONTINENT_VIEW.welt, false);
      applyDimming(cont);
    }

    /* ── Land hervorheben ─────────────────────────────────────────────── */
    function highlightCountry(key) {
      Object.keys(countryPaths).forEach(function (iso) {
        countryPaths[iso].classList.toggle('is-selected', iso === key);
      });
    }

    /* ── Suchgebiet wählen ────────────────────────────────────────────── */
    function selectScope(type, key, label) {
      if (scopeType) scopeType.value = type;
      if (scopeKey)  scopeKey.value  = key;
      clearActive(scopeChips);
      if (type === 'country') {
        scopeChips.forEach(function (c) {
          if (c.getAttribute('data-scope-key') === key) c.classList.add('is-active');
        });
        highlightCountry(key);
        if (regionSelect) regionSelect.value = '';
        var cont = (contract[key] || {}).continent;
        if (cont && CONTINENT_VIEW[cont]) {
          if (continentSelect) continentSelect.value = cont;
          focusContinent(cont, false);
        }
      } else {
        highlightCountry(null);
      }
      if (scopeStatus) {
        scopeStatus.textContent = '\u2713 ' + (label || key) + ' gew\u00e4hlt';
      }
      if (mapHint) mapHint.textContent = (label || key) + ' als Suchgebiet \u00fcbernommen.';
    }

    /* ── Tooltip ──────────────────────────────────────────────────────── */
    function showTooltip(evt, data) {
      if (!tooltip || !mapStage) return;
      var statusLine = '';
      if (data.status) {
        var ok = data.status === 'scoutable' || data.status === 'selected';
        statusLine = '<span style="color:' + (ok ? 'var(--sc-green)' : 'var(--sc-yellow)') + '">Status: '
          + (data.coverage_label || '') + '</span>';
      }
      tooltip.innerHTML = '<strong>' + data.name + '</strong>' + statusLine;
      tooltip.hidden = false;
      var rect = mapStage.getBoundingClientRect();
      var x = evt.clientX - rect.left + 14;
      var y = evt.clientY - rect.top  + 14;
      x = Math.min(x, rect.width  - tooltip.offsetWidth  - 8);
      y = Math.min(y, rect.height - tooltip.offsetHeight - 8);
      tooltip.style.left = Math.max(4, x) + 'px';
      tooltip.style.top  = Math.max(4, y) + 'px';
    }
    function hideTooltip() { if (tooltip) tooltip.hidden = true; }

    /* ── Deko-Partikel (wie Vorlage) ──────────────────────────────────── */
    function buildParticles() {
      var host = document.getElementById('sc-map-particles');
      if (!host) return;
      var html = '';
      for (var i = 0; i < 26; i++) {
        var x = (Math.random() * 100).toFixed(2);
        var y = (Math.random() * 100).toFixed(2);
        var o = (0.12 + Math.random() * 0.3).toFixed(2);
        html += '<i style="left:' + x + '%;top:' + y + '%;opacity:' + o + '"></i>';
      }
      host.innerHTML = html;
    }

    /* ── SVG laden & verdrahten ───────────────────────────────────────── */
    function wirePaths() {
      var paths = svgEl.querySelectorAll('path[data-iso2]');
      Array.prototype.forEach.call(paths, function (p) {
        var iso  = p.getAttribute('data-iso2');
        var data = contract[iso];
        if (!data) return;            /* neutrales Land bleibt sichtbar, nicht interaktiv */
        countryPaths[iso] = p;
        p.classList.add('is-' + data.status, 'is-interactive');
      });

      /* Delegierte Hover/Klick-Logik (ein Listener für alle Länder, wie Vorlage). */
      svgEl.addEventListener('mousemove', function (e) {
        var p = e.target.closest ? e.target.closest('path[data-iso2]') : null;
        if (!p) { hideTooltip(); return; }
        var iso = p.getAttribute('data-iso2');
        showTooltip(e, contract[iso] || { name: p.getAttribute('data-name') || iso });
      });
      svgEl.addEventListener('mouseleave', hideTooltip);
      svgEl.addEventListener('click', function (e) {
        var p = e.target.closest ? e.target.closest('path[data-iso2]') : null;
        if (!p) return;
        var iso = p.getAttribute('data-iso2');
        var data = contract[iso];
        if (!data) return;            /* neutrales Land: keine Auswahl */
        if (data.status === 'scoutable') selectScope('country', iso, data.name);
        else if (mapHint) mapHint.textContent = data.hint;
      });

      if (scopeKey && scopeKey.value && countryPaths[scopeKey.value]) {
        highlightCountry(scopeKey.value);
      }
    }

    if (mapCanvas && mapCanvas.getAttribute('data-svg-url')) {
      fetch(mapCanvas.getAttribute('data-svg-url'))
        .then(function (r) { return r.text(); })
        .then(function (txt) {
          mapCanvas.innerHTML = txt;
          svgEl = mapCanvas.querySelector('svg');
          if (!svgEl) return;
          buildParticles();
          wirePaths();
          focusContinent(continentSelect ? continentSelect.value : 'welt', true);
        })
        .catch(function () {
          if (mapHint) mapHint.textContent = 'Karte konnte nicht geladen werden.';
        });
    }

    /* ── Bedienelemente ───────────────────────────────────────────────── */
    scopeChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        selectScope('country', chip.getAttribute('data-scope-key'), chip.textContent.trim());
      });
    });

    if (continentSelect) {
      continentSelect.addEventListener('change', function () {
        if (regionSelect) regionSelect.value = '';
        focusContinent(continentSelect.value, false);
      });
    }

    if (regionSelect) {
      regionSelect.addEventListener('change', function () {
        if (!regionSelect.value) {
          focusContinent(continentSelect ? continentSelect.value : 'welt', false);
          return;
        }
        var label = regionSelect.options[regionSelect.selectedIndex].text;
        selectScope('region', regionSelect.value, label);
        focusRegion(regionSelect.value);
      });
    }

    /* Scoutable country-tiles unterhalb der Karte */
    document.querySelectorAll('.sc-country-tile--scoutable').forEach(function (tile) {
      tile.addEventListener('click', function () {
        var iso = tile.getAttribute('data-iso');
        if (iso && contract[iso] && contract[iso].status === 'scoutable') {
          selectScope('country', iso, contract[iso].name);
        }
      });
    });

    /* Positionen: Mehrfachauswahl. "Keine Vorgabe" (leeres data-pos) setzt zurück. */
    var posNone = posChips.filter(function (c) { return !(c.getAttribute('data-pos') || ''); })[0];
    function syncPositions() {
      var vals = posChips
        .filter(function (c) { return c.classList.contains('is-active') && (c.getAttribute('data-pos') || ''); })
        .map(function (c) { return c.getAttribute('data-pos'); });
      if (positionField) positionField.value = vals.join(',');
      if (posNone) posNone.classList.toggle('is-active', vals.length === 0);
    }
    posChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        if (!(chip.getAttribute('data-pos') || '')) {   /* "Keine Vorgabe" → alles abwählen */
          clearActive(posChips);
          chip.classList.add('is-active');
          if (positionField) positionField.value = '';
          return;
        }
        chip.classList.toggle('is-active');              /* einzelne Position umschalten */
        syncPositions();
      });
    });

    profileChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        clearActive(profileChips);
        chip.classList.add('is-active');
        if (profileField) profileField.value = chip.getAttribute('data-profile') || 'ergaenzung';
      });
    });

    /* ── Gebots-Dialog ────────────────────────────────────────────────── */
    var modal    = document.getElementById('bid-modal');
    var bidFindId= document.getElementById('bid-find-id');
    var bidAmount= document.getElementById('bid-amount');
    var bidTitle = document.getElementById('bid-modal-title');
    var bidHint  = document.getElementById('bid-min-hint');

    function openBid(find, name, min) {
      if (!modal) return;
      bidFindId.value = find;
      bidAmount.value = min;
      bidTitle.textContent = 'Angebot f\u00fcr ' + name;
      bidHint.textContent  = 'Mindestgebot: ' + fmtEuro(min);
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
