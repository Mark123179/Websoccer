(function () {
  'use strict';

  function fmtEuro(n) {
    return (Number(n) || 0).toLocaleString('de-DE') + ' \u20ac';
  }

  function clearActive(nodes) {
    nodes.forEach(function (n) { n.classList.remove('is-active'); });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var scopeKey = document.getElementById('scope_key');
    var scopeType = document.getElementById('scope_type');
    var positionField = document.getElementById('position_field');
    var profileField = document.getElementById('profile_field');
    var regionSelect = document.getElementById('region-select');
    var scopeStatus = document.getElementById('scope-status');

    var scopeChips = Array.prototype.slice.call(document.querySelectorAll('.scope-chip'));
    var markers = Array.prototype.slice.call(document.querySelectorAll('.scout-marker'));
    var posChips = Array.prototype.slice.call(document.querySelectorAll('.pos-chip'));
    var profileChips = Array.prototype.slice.call(document.querySelectorAll('.profile-chip'));

    function selectScope(type, key, label) {
      if (scopeType) scopeType.value = type;
      if (scopeKey) scopeKey.value = key;
      clearActive(scopeChips);
      markers.forEach(function (m) { m.classList.remove('is-selected'); });
      if (type === 'country') {
        scopeChips.forEach(function (c) {
          if (c.getAttribute('data-scope-key') === key) c.classList.add('is-active');
        });
        markers.forEach(function (m) {
          if (m.getAttribute('data-scope-key') === key) m.classList.add('is-selected');
        });
        if (regionSelect) regionSelect.value = '';
      }
      if (scopeStatus) {
        scopeStatus.textContent = '\u2713 ' + (label || key) + ' gew\u00e4hlt';
        scopeStatus.classList.add('ok');
      }
    }

    scopeChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        selectScope('country', chip.getAttribute('data-scope-key'), chip.textContent.trim());
      });
    });

    markers.forEach(function (m) {
      m.addEventListener('click', function () {
        if (m.getAttribute('data-scoutable') !== '1') return;
        selectScope('country', m.getAttribute('data-scope-key'), m.getAttribute('title'));
      });
    });

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
