/* Transfersystem v2 — Kader anbieten, Meine Deals, Deal-Builder (Task #821).
 *
 * Ein Skript für alle drei Seiten; die Abschnitte initialisieren sich nur,
 * wenn die zugehörigen DOM-Knoten vorhanden sind. Countdown-Logik ist
 * identisch zum Transfermarkt (transfer_v2.js), hier bewusst schlank kopiert,
 * damit die Marktseite unangetastet bleibt.
 */
(function () {
  'use strict';

  /* ── Helfer ─────────────────────────────────────────────────────────── */

  function euro(v) {
    var n = Math.round(Number(v) || 0);
    return n.toLocaleString('de-DE') + ' €';
  }

  function parseAmount(raw) {
    if (!raw) return 0;
    var s = String(raw).replace(/\./g, '').replace(/\s/g, '').replace(',', '.');
    var n = parseFloat(s);
    return isNaN(n) ? 0 : n;
  }

  function jsonData(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  /* Countdown-Chips (data-ends = Epoch-ms). */
  function initCountdowns() {
    var nodes = document.querySelectorAll('[data-ends]');
    if (!nodes.length) return;
    function tick() {
      var now = Date.now();
      nodes.forEach(function (el) {
        var ends = parseInt(el.getAttribute('data-ends'), 10);
        if (!ends) { el.textContent = '—'; return; }
        var diff = ends - now;
        if (diff <= 0) { el.textContent = 'beendet'; el.classList.add('is-over'); return; }
        var d = Math.floor(diff / 86400000);
        var h = Math.floor((diff % 86400000) / 3600000);
        var m = Math.floor((diff % 3600000) / 60000);
        var s = Math.floor((diff % 60000) / 1000);
        if (d > 0) el.textContent = d + 'T ' + h + 'h';
        else if (h > 0) el.textContent = h + 'h ' + m + 'm';
        else el.textContent = m + 'm ' + s + 's';
        el.classList.toggle('is-hot', diff < 3600000);
      });
    }
    tick();
    window.setInterval(tick, 1000);
  }

  /* Chip-Gruppen (ein aktiver Chip, hidden-Feld synchron). */
  function initChipGroup(groupId, hiddenId, onChange) {
    var group = document.getElementById(groupId);
    if (!group) return;
    group.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.tv2-chip');
      if (!btn || btn.classList.contains('tv2-chip-suffix')) return;
      group.querySelectorAll('.tv2-chip').forEach(function (c) { c.classList.remove('is-on'); });
      btn.classList.add('is-on');
      var hidden = hiddenId ? document.getElementById(hiddenId) : null;
      if (hidden) hidden.value = btn.getAttribute('data-val');
      if (onChange) onChange(btn.getAttribute('data-val'));
    });
  }

  /* ══════════════════════════════════════════════════════════════════════
   *  KADER ANBIETEN
   * ════════════════════════════════════════════════════════════════════ */

  function initOfferBoard() {
    var data = jsonData('tv2-listing-data');
    var urls = document.getElementById('tv2-board-urls');
    if (!urls) return;

    /* Beobachter auf-/zuklappen. */
    document.querySelectorAll('[data-eye-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var panel = document.getElementById('tv2-watchers-' + btn.getAttribute('data-eye-toggle'));
        if (panel) panel.hidden = !panel.hidden;
      });
    });

    /* Listing-Modal. */
    var backdrop = document.getElementById('tv2-listing-backdrop');
    if (backdrop && data) {
      var sheets = {};
      data.forEach(function (s) { sheets[s.id] = s; });
      var minFloor = parseFloat(urls.getAttribute('data-min-floor')) || 500000;
      var cur = null;

      function renderGuidance(g) {
        var box = document.getElementById('tv2-li-guidance');
        if (!g || !g.show) {
          box.innerHTML = '<div class="tv2-footnote">Noch zu wenige vergleichbare Transfers (mind. 3 nötig) — keine Preisempfehlung.</div>';
          return;
        }
        var html = '<div class="tv2-li-range">Empfohlene Spanne: <b>' + euro(g.lo) + ' – ' + euro(g.hi) + '</b></div>';
        html += g.refs.map(function (r) {
          return '<div class="tv2-li-ref">' + esc(r.hp) + ' · ' + esc(r.name) + ' (' + esc(r.age) + ') — ' + euro(r.price) + (r.date ? ' · ' + esc(r.date) : '') + '</div>';
        }).join('');
        box.innerHTML = html;
      }

      function renderLevy(sheet, basis) {
        var box = document.getElementById('tv2-li-levy');
        var rows = sheet.levy || [];
        if (!rows.length) {
          box.innerHTML = '<div class="tv2-footnote">Keine Ausbildungsvereine hinterlegt — keine Abgabe.</div>';
          return;
        }
        var pct = sheet.levyPctLabel || '';
        var minJe = sheet.levyMin || 0;
        var html = rows.map(function (r) {
          var anteil = basis > 0 ? Math.max(basis * r.share, minJe) : minJe;
          return '<div class="tv2-li-ref">' + esc(r.club) + ' — ' + euro(anteil) + '</div>';
        }).join('');
        html += '<div class="tv2-footnote">' + esc(pct) + ' vom Verkaufspreis, mind. ' + euro(minJe) + ' je Ausbildungsverein. Zahler: Verkäufer.</div>';
        box.innerHTML = html;
      }

      function validate() {
        var minV = parseAmount(document.getElementById('tv2-li-min').value);
        var buyRaw = document.getElementById('tv2-li-buy').value;
        var buyV = parseAmount(buyRaw);
        var check = document.getElementById('tv2-li-check');
        var cta = document.getElementById('tv2-li-cta');
        var msgs = [];
        if (minV < minFloor) msgs.push('Mindestgebot unter ' + euro(minFloor) + '.');
        if (buyRaw && buyV <= minV) msgs.push('Sofortkaufpreis muss über dem Mindestgebot liegen.');
        check.innerHTML = msgs.map(function (m) { return '<div class="tv2-li-warn">' + esc(m) + '</div>'; }).join('');
        cta.disabled = msgs.length > 0;
        if (cur) renderLevy(cur, Math.max(minV, 0));
        document.getElementById('tv2-li-min-hidden').value = document.getElementById('tv2-li-min').value;
        document.getElementById('tv2-li-buy-hidden').value = buyRaw;
      }

      document.querySelectorAll('[data-listing-open]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var sheet = sheets[btn.getAttribute('data-listing-open')];
          if (!sheet) return;
          cur = sheet;
          document.getElementById('tv2-li-title').textContent = 'Auf Transfermarkt stellen — ' + sheet.name;
          document.getElementById('tv2-li-sub').textContent = sheet.sub;
          document.getElementById('tv2-li-pid').value = sheet.id;
          var suggested = Math.max(Math.round((sheet.mw || 0) * 0.9), minFloor);
          document.getElementById('tv2-li-min').value = suggested.toLocaleString('de-DE');
          document.getElementById('tv2-li-buy').value = '';
          renderGuidance(sheet.guidance);
          validate();
          backdrop.hidden = false;
        });
      });

      document.getElementById('tv2-li-min').addEventListener('input', validate);
      document.getElementById('tv2-li-buy').addEventListener('input', validate);
      initChipGroup('tv2-li-timing', 'tv2-li-timing-hidden');
      initChipGroup('tv2-li-duration', 'tv2-li-duration-hidden');
      document.getElementById('tv2-li-cancel').addEventListener('click', function () { backdrop.hidden = true; });
      backdrop.addEventListener('click', function (ev) { if (ev.target === backdrop) backdrop.hidden = true; });
    }

    /* Leih-Modal („Auf den Leihmarkt stellen", Task #822). */
    var loanBackdrop = document.getElementById('tv2-loan-backdrop');
    if (loanBackdrop && data) {
      var loanSheets = {};
      data.forEach(function (s) { loanSheets[s.id] = s; });
      var loanMinFee = parseFloat(urls.getAttribute('data-loan-min-fee')) || 1000000;

      function loanValidate() {
        var feeRaw = document.getElementById('tv2-lo-fee').value;
        var fee = parseAmount(feeRaw);
        var check = document.getElementById('tv2-lo-check');
        var cta = document.getElementById('tv2-lo-cta');
        var msgs = [];
        if (fee > 0 && fee < loanMinFee) msgs.push('Leihgebühr unter ' + euro(loanMinFee) + ' — nur 0 € (Partnerverein) oder ≥ Minimum.');
        if (fee === 0) msgs.push('Hinweis: 0-€-Gebühr können nur aktive Partnervereine annehmen.');
        check.innerHTML = msgs.map(function (m) { return '<div class="tv2-li-warn">' + esc(m) + '</div>'; }).join('');
        cta.disabled = fee > 0 && fee < loanMinFee;
        document.getElementById('tv2-lo-fee-hidden').value = feeRaw;
        document.getElementById('tv2-lo-buy-hidden').value = document.getElementById('tv2-lo-buy').value;
      }

      document.querySelectorAll('[data-loan-open]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var sheet = loanSheets[btn.getAttribute('data-loan-open')];
          if (!sheet) return;
          document.getElementById('tv2-lo-title').textContent = 'Auf den Leihmarkt stellen — ' + sheet.name;
          document.getElementById('tv2-lo-sub').textContent = sheet.sub;
          document.getElementById('tv2-lo-pid').value = sheet.id;
          document.getElementById('tv2-lo-fee').value = loanMinFee.toLocaleString('de-DE');
          document.getElementById('tv2-lo-buy').value = '';
          loanValidate();
          loanBackdrop.hidden = false;
        });
      });

      document.getElementById('tv2-lo-fee').addEventListener('input', loanValidate);
      document.getElementById('tv2-lo-buy').addEventListener('input', loanValidate);
      initChipGroup('tv2-lo-until', 'tv2-lo-until-hidden');
      document.getElementById('tv2-lo-cancel').addEventListener('click', function () { loanBackdrop.hidden = true; });
      loanBackdrop.addEventListener('click', function (ev) { if (ev.target === loanBackdrop) loanBackdrop.hidden = true; });
    }

    /* Forum-Post-Modal. */
    var forumBtn = document.getElementById('tv2-forum-btn');
    var forumBackdrop = document.getElementById('tv2-forum-backdrop');
    if (forumBtn && forumBackdrop) {
      forumBtn.addEventListener('click', function () {
        fetch(urls.getAttribute('data-forum-url'), { credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (j) {
            document.getElementById('tv2-forum-text').textContent =
              j.text || 'Keine Spieler mit Status ≠ Unverkäuflich.';
            forumBackdrop.hidden = false;
          });
      });
      document.getElementById('tv2-forum-close').addEventListener('click', function () { forumBackdrop.hidden = true; });
      forumBackdrop.addEventListener('click', function (ev) { if (ev.target === forumBackdrop) forumBackdrop.hidden = true; });
      document.getElementById('tv2-forum-copy').addEventListener('click', function () {
        var text = document.getElementById('tv2-forum-text').textContent;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            document.getElementById('tv2-forum-copy').textContent = 'Kopiert ✓';
          });
        }
      });
    }
  }

  /* ══════════════════════════════════════════════════════════════════════
   *  MEINE DEALS — Zusammenfassungs-Popup
   * ════════════════════════════════════════════════════════════════════ */

  function initDeals() {
    var data = jsonData('tv2-summaries-data');
    var backdrop = document.getElementById('tv2-summary-backdrop');
    var urls = document.getElementById('tv2-deal-urls');
    if (!data || !backdrop || !urls) return;

    var summaries = {};
    data.forEach(function (s) { summaries[s.id] = s; });
    var csrf = urls.getAttribute('data-csrf');
    var myClub = document.querySelector('.tv2-wrap').getAttribute('data-club') || '';

    function playerCard(p) {
      var badge = '';
      if (p.locked) badge = '<span class="tv2-pill tv2-pill--red">gesperrt</span>';
      return '<div class="tv2-sum-player">' +
        (p.flag ? '<img class="tv2-flag" src="' + esc(p.flag) + '" alt="" onerror="this.style.display=\'none\'">' : '') +
        '<a href="' + esc(p.player_url) + '">' + esc(p.name) + '</a>' +
        '<span class="tv2-board-meta">' + esc(p.age) + ' J. · ' + esc(p.hp) + ' · MW ' + esc(p.mw_fmt) + '</span>' + badge +
        '</div>';
    }

    function open(id, received) {
      var s = summaries[id];
      if (!s) return;
      document.getElementById('tv2-sum-title').textContent =
        s.from_club + ' ⇄ ' + s.to_club;
      document.getElementById('tv2-sum-sub').textContent =
        s.typ + ' · Zeitpunkt: ' + s.timing +
        (s.timing !== 'Sofort' ? ' (Vollzug als vorgemerkter Transfer)' : '');
      var quote = document.getElementById('tv2-sum-quote');
      if (s.message) { quote.textContent = '„' + s.message + '"'; quote.hidden = false; }
      else quote.hidden = true;

      document.getElementById('tv2-sum-from-head').textContent = s.from_club + ' gibt ab';
      document.getElementById('tv2-sum-to-head').textContent = s.to_club + ' gibt ab';

      var fromHtml = s.from_players.map(playerCard).join('');
      if (s.cash_from_fmt) fromHtml += '<div class="tv2-sum-cash">+ ' + esc(s.cash_from_fmt) + '</div>';
      if (s.is_loan && s.loan_fee_fmt) fromHtml += '<div class="tv2-sum-cash">Leihgebühr ' + esc(s.loan_fee_fmt) + '</div>';
      document.getElementById('tv2-sum-from').innerHTML = fromHtml || '<div class="tv2-empty">—</div>';

      var toHtml = s.to_players.map(playerCard).join('');
      if (s.cash_to_fmt) toHtml += '<div class="tv2-sum-cash">+ ' + esc(s.cash_to_fmt) + '</div>';
      if (s.is_loan && s.loan_until) toHtml += '<div class="tv2-sum-cash">Leihe bis ' + esc(s.loan_until) + (s.loan_buy_fmt ? ' · Kaufoption ' + esc(s.loan_buy_fmt) : '') + '</div>';
      document.getElementById('tv2-sum-to').innerHTML = toHtml || '<div class="tv2-empty">—</div>';

      function levyList(rows, label) {
        if (!rows.length) return '<div class="tv2-footnote">' + esc(label) + ': keine Abgabe.</div>';
        return '<div class="tv2-footnote">' + esc(label) + ':</div>' + rows.map(function (r) {
          return '<div class="tv2-li-ref">' + esc(r.player) + ' → ' + esc(r.club) + ': ' + esc(r.amt_fmt) + '</div>';
        }).join('');
      }
      document.getElementById('tv2-sum-levy-from').innerHTML = levyList(s.levy_from, 'zahlt ' + s.from_club);
      document.getElementById('tv2-sum-levy-to').innerHTML = levyList(s.levy_to, 'zahlt ' + s.to_club);

      var actions = document.getElementById('tv2-sum-actions');
      var formHtml = '';
      function form(url, label, cls) {
        return '<form method="post" action="' + url + '">' +
          '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrf + '">' +
          '<input type="hidden" name="deal_id" value="' + id + '">' +
          '<button type="submit" class="tv2-btn ' + cls + ' tv2-btn--tall">' + label + '</button></form>';
      }
      if (received) {
        formHtml = form(urls.getAttribute('data-decline-url'), 'Ablehnen', 'tv2-btn--decline') +
                   form(urls.getAttribute('data-accept-url'), 'Annehmen', 'tv2-btn--accept');
      } else {
        formHtml = form(urls.getAttribute('data-withdraw-url'), 'Zurückziehen', 'tv2-btn--decline');
      }
      actions.innerHTML = '<button type="button" class="tv2-btn tv2-btn--ghost tv2-btn--tall" id="tv2-sum-close">Schließen</button>' + formHtml;
      document.getElementById('tv2-sum-close').addEventListener('click', function () { backdrop.hidden = true; });
      backdrop.hidden = false;
    }

    var seg = new URLSearchParams(window.location.search).get('seg') || 'gebote';
    document.querySelectorAll('[data-summary-open]').forEach(function (row) {
      row.addEventListener('click', function (ev) {
        if (ev.target.closest('form') || ev.target.closest('a')) return;
        open(parseInt(row.getAttribute('data-summary-open'), 10), seg === 'erhalten');
      });
    });
    backdrop.addEventListener('click', function (ev) { if (ev.target === backdrop) backdrop.hidden = true; });
  }

  /* ══════════════════════════════════════════════════════════════════════
   *  DEAL-BUILDER
   * ════════════════════════════════════════════════════════════════════ */

  function initBuilder() {
    var countries = jsonData('tv2-countries-data');
    var ownPlayers = jsonData('tv2-own-players-data');
    var urls = document.getElementById('tv2-builder-urls');
    if (!countries || !ownPlayers || !urls) return;

    var maxSide = parseInt(urls.getAttribute('data-max-side'), 10) || 5;
    var targetUrl = urls.getAttribute('data-target-url');

    var state = {
      toClub: null, toClubName: '', targetPlayers: [],
      fromSel: [], toSel: [],
      fromSeg: 'profis', toSeg: 'profis',
      timing: 'SOFORT',
    };

    var selCountry = document.getElementById('tv2-b-country');
    var selLeague = document.getElementById('tv2-b-league');
    var selClub = document.getElementById('tv2-b-club');

    countries.forEach(function (c, i) {
      var o = document.createElement('option');
      o.value = String(i); o.textContent = c.name;
      selCountry.appendChild(o);
    });

    selCountry.addEventListener('change', function () {
      selLeague.innerHTML = '<option value="">Liga…</option>';
      selClub.innerHTML = '<option value="">Verein…</option>';
      selClub.disabled = true;
      var c = countries[parseInt(selCountry.value, 10)];
      if (!c) { selLeague.disabled = true; setTarget(null); return; }
      c.leagues.forEach(function (lg, i) {
        var o = document.createElement('option');
        o.value = String(i); o.textContent = lg.name;
        selLeague.appendChild(o);
      });
      selLeague.disabled = false;
      setTarget(null);
    });

    selLeague.addEventListener('change', function () {
      selClub.innerHTML = '<option value="">Verein…</option>';
      var c = countries[parseInt(selCountry.value, 10)];
      var lg = c && c.leagues[parseInt(selLeague.value, 10)];
      if (!lg) { selClub.disabled = true; setTarget(null); return; }
      lg.clubs.forEach(function (cl) {
        var o = document.createElement('option');
        o.value = String(cl.id);
        o.textContent = cl.name + (cl.is_ki ? ' · KI-GEFÜHRT' : (cl.manager ? ' · ' + cl.manager : ''));
        selClub.appendChild(o);
      });
      selClub.disabled = false;
      setTarget(null);
    });

    selClub.addEventListener('change', function () {
      var c = countries[parseInt(selCountry.value, 10)];
      var lg = c && c.leagues[parseInt(selLeague.value, 10)];
      var cl = lg && lg.clubs.find(function (x) { return String(x.id) === selClub.value; });
      setTarget(cl || null);
    });

    function setTarget(cl) {
      state.toClub = cl ? cl.id : null;
      state.toClubName = cl ? cl.name : '';
      state.toSel = [];
      state.targetPlayers = [];
      var info = document.getElementById('tv2-b-clubinfo');
      if (cl) {
        document.getElementById('tv2-b-crest').src = cl.crest || '';
        document.getElementById('tv2-b-clubname').textContent = cl.name;
        document.getElementById('tv2-b-manager').textContent = cl.is_ki ? 'KI-GEFÜHRT' : ('Manager: ' + cl.manager);
        info.hidden = false;
        document.getElementById('tv2-b-to-list').innerHTML = '<div class="tv2-empty">Lade Kader…</div>';
        fetch(targetUrl + '?club_id=' + cl.id, { credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (j) {
            state.targetPlayers = j.players || [];
            renderList('to');
            updateSummary();
          });
      } else {
        info.hidden = true;
        document.getElementById('tv2-b-to-list').innerHTML = '<div class="tv2-empty">Erst Zielverein wählen.</div>';
      }
      updateSummary();
    }

    function rowHtml(p, side, selected) {
      var cls = 'tv2-builder-row' + (selected ? ' is-sel' : '') + (p.selectable ? '' : ' is-blocked');
      var badge = '';
      if (p.locked) badge = '<span class="tv2-pill tv2-pill--red">gesperrt ' + esc(p.lock_days) + ' T</span>';
      else if (p.loaned_out || p.loaned_in) badge = '<span class="tv2-pill tv2-pill--gold">Leihe</span>';
      return '<div class="' + cls + '" data-side="' + side + '" data-pid="' + p.id + '">' +
        (p.flag ? '<img class="tv2-flag" src="' + esc(p.flag) + '" alt="" onerror="this.style.display=\'none\'">' : '') +
        '<span class="tv2-builder-row-name">' + esc(p.name) + '</span>' +
        '<span class="tv2-board-meta">' + esc(p.age) + ' · ' + esc(p.hp) + ' · ' + esc(p.mw_fmt) + '</span>' +
        badge +
        '<span class="tv2-builder-row-check">' + (selected ? '✓' : '+') + '</span>' +
        '</div>';
    }

    function renderList(side) {
      var listEl = document.getElementById(side === 'from' ? 'tv2-b-from-list' : 'tv2-b-to-list');
      var pool = side === 'from' ? ownPlayers : state.targetPlayers;
      var seg = side === 'from' ? state.fromSeg : state.toSeg;
      var sel = side === 'from' ? state.fromSel : state.toSel;
      var rows = pool.filter(function (p) { return seg === 'u21' ? p.youth : !p.youth; });
      if (!rows.length) {
        listEl.innerHTML = '<div class="tv2-empty">Keine Spieler in diesem Segment.</div>';
        return;
      }
      listEl.innerHTML = rows.map(function (p) {
        return rowHtml(p, side, sel.indexOf(p.id) !== -1);
      }).join('');
    }

    function toggle(side, pid) {
      var sel = side === 'from' ? state.fromSel : state.toSel;
      var pool = side === 'from' ? ownPlayers : state.targetPlayers;
      var p = pool.find(function (x) { return x.id === pid; });
      if (!p || !p.selectable) return;
      var idx = sel.indexOf(pid);
      if (idx !== -1) sel.splice(idx, 1);
      else {
        if (sel.length >= maxSide) return;
        sel.push(pid);
      }
      renderList(side);
      updateSummary();
    }

    document.getElementById('tv2-b-from-list').addEventListener('click', function (ev) {
      var row = ev.target.closest('.tv2-builder-row');
      if (row) toggle('from', parseInt(row.getAttribute('data-pid'), 10));
    });
    document.getElementById('tv2-b-to-list').addEventListener('click', function (ev) {
      var row = ev.target.closest('.tv2-builder-row');
      if (row) toggle('to', parseInt(row.getAttribute('data-pid'), 10));
    });

    initChipGroup('tv2-b-from-seg', null, function (v) { state.fromSeg = v; renderList('from'); });
    initChipGroup('tv2-b-to-seg', null, function (v) { state.toSeg = v; renderList('to'); });
    initChipGroup('tv2-b-timing', 'tv2-b-timing-hidden', function (v) {
      state.timing = v;
      var note = document.getElementById('tv2-b-timing-note');
      note.textContent = v === 'SOFORT' ? '' :
        'Geld fließt sofort bei Annahme, Spieler wechseln zur ' + (v === 'WP' ? 'Winterpause' : 'Saisonende') + ' (vorgemerkter Transfer).';
    });

    var cashFrom = document.getElementById('tv2-b-cash-from');
    var cashTo = document.getElementById('tv2-b-cash-to');
    cashFrom.addEventListener('input', updateSummary);
    cashTo.addEventListener('input', updateSummary);

    function selectedCards(side) {
      var sel = side === 'from' ? state.fromSel : state.toSel;
      var pool = side === 'from' ? ownPlayers : state.targetPlayers;
      return sel.map(function (id) { return pool.find(function (p) { return p.id === id; }); })
        .filter(Boolean);
    }

    function updateSummary() {
      document.getElementById('tv2-b-from-count').textContent = state.fromSel.length + '/' + maxSide;
      document.getElementById('tv2-b-to-count').textContent = state.toSel.length + '/' + maxSide;

      var cf = parseAmount(cashFrom.value);
      var ct = parseAmount(cashTo.value);
      var body = document.getElementById('tv2-b-summary-body');
      var send = document.getElementById('tv2-b-send');

      var fromCards = selectedCards('from');
      var toCards = selectedCards('to');

      var lines = [];
      if (fromCards.length) lines.push('<b>Ich gebe:</b> ' + fromCards.map(function (p) { return esc(p.name); }).join(', '));
      if (cf > 0) lines.push('<b>+ Geld von mir:</b> ' + euro(cf));
      if (toCards.length) lines.push('<b>Ich möchte:</b> ' + toCards.map(function (p) { return esc(p.name); }).join(', '));
      if (ct > 0) lines.push('<b>+ Geld vom Zielverein:</b> ' + euro(ct));
      lines.push('<b>Zeitpunkt:</b> ' + (state.timing === 'SOFORT' ? 'Sofort' : state.timing === 'WP' ? 'Winterpause' : 'Saisonende'));
      body.innerHTML = state.toClub ? lines.join('<br>') : 'Noch leer — Zielverein und Paket wählen.';

      /* Jugendabgabe-Hinweis (Vorschau, verbindlich erst bei Annahme). */
      var levyBox = document.getElementById('tv2-b-levy');
      if (toCards.length || fromCards.length) {
        levyBox.innerHTML = '<div class="tv2-footnote">Jugendspielerabgabe wird bei Annahme je Spieler fällig (Zahler = jeweiliger Käufer); Details in der Deal-Zusammenfassung unter „Anfragen gesendet".</div>';
      } else {
        levyBox.innerHTML = '';
      }

      /* Gültige Schemata (spiegelt Server-Validierung exakt):
       * - Tausch: Spieler auf BEIDEN Seiten, Geldausgleich höchstens einseitig.
       * - Kauf:   nur Zielspieler + mein Geld (> 0), kein Gegen-Geld.
       * - Verkauf: nur eigene Spieler + Empfänger-Geld (> 0), kein eigenes Geld. */
      var valid = false;
      if (state.toClub) {
        if (fromCards.length && toCards.length) {
          valid = !(cf > 0 && ct > 0);
        } else if (toCards.length) {
          valid = cf > 0 && !(ct > 0);
        } else if (fromCards.length) {
          valid = ct > 0 && !(cf > 0);
        }
      }
      send.disabled = !valid;

      document.getElementById('tv2-b-toclub-hidden').value = state.toClub || '';
      document.getElementById('tv2-b-from-hidden').value = state.fromSel.join(',');
      document.getElementById('tv2-b-to-hidden').value = state.toSel.join(',');
      document.getElementById('tv2-b-cashfrom-hidden').value = cashFrom.value;
      document.getElementById('tv2-b-cashto-hidden').value = cashTo.value;
    }

    document.getElementById('tv2-b-form').addEventListener('submit', function () {
      document.getElementById('tv2-b-msg-hidden').value = document.getElementById('tv2-b-msg').value;
    });

    renderList('from');
    updateSummary();
  }

  /* ── Init ───────────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initCountdowns();
    initOfferBoard();
    initDeals();
    initBuilder();

    /* Escape-Taste schließt offene Modals (alle vier Backdrops). */
    var _backdropIds = [
      'tv2-listing-backdrop',
      'tv2-loan-backdrop',
      'tv2-forum-backdrop',
      'tv2-summary-backdrop',
    ];
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      _backdropIds.forEach(function (id) {
        var el = document.getElementById(id);
        if (el && !el.hidden) el.hidden = true;
      });
    });
    /* bfcache-Guard: Browser-Back/-Forward kann ein offenes Modal einfrieren. */
    window.addEventListener('pageshow', function (e) {
      if (!e.persisted) return;
      _backdropIds.forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.hidden = true;
      });
    });
  });
})();
