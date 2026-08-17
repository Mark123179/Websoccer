/* ═══ Transfersystem v2 — Transfermarkt (Task #820) ═══════════════════════
   Countdowns (sekündlich), Client-Filter, Gebotsverlauf-Toggle und
   Deal-Sheet-Modal mit Live-Berechnung (Jugendabgabe, Auszahlung).
   Serverdaten kommen via json_script (#tv2-sheets-data) — kein |safe. */
(function () {
    'use strict';

    /* ── Deutsche Formatierung ─────────────────────────────────────── */
    function euro(n) {
        if (n === null || n === undefined || isNaN(n)) { return '—'; }
        return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' €';
    }
    function parseAmount(str) {
        var digits = String(str || '').replace(/[^\d]/g, '');
        return digits ? parseInt(digits, 10) : NaN;
    }

    /* ── Countdown ─────────────────────────────────────────────────── */
    function fmtRest(ms) {
        var s = Math.floor(ms / 1000);
        if (s < 3600) {
            var m = Math.floor(s / 60), sec = s % 60;
            return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec + ' min';
        }
        if (s < 86400) {
            return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
        }
        return Math.floor(s / 86400) + ' T ' + Math.floor((s % 86400) / 3600) + ' h';
    }
    function tickCountdowns() {
        var now = Date.now();
        var nodes = document.querySelectorAll('.tv2-cd[data-ends]');
        for (var i = 0; i < nodes.length; i++) {
            var el = nodes[i];
            var ends = parseInt(el.getAttribute('data-ends'), 10);
            if (!ends) { continue; } /* Vereinslos: „24h ab 1. Gebot" bleibt. */
            var rest = ends - now;
            el.classList.remove('tv2-cd--gold', 'tv2-cd--red', 'tv2-cd--over');
            if (rest <= 0) {
                el.textContent = 'beendet';
                el.classList.add('tv2-cd--over');
                continue;
            }
            el.textContent = fmtRest(rest);
            if (rest < 3600000) { el.classList.add('tv2-cd--red'); }
            else if (rest < 43200000) { el.classList.add('tv2-cd--gold'); }
        }
    }
    tickCountdowns();
    setInterval(tickCountdowns, 1000);

    /* ── Gebotsverlauf auf-/zuklappen ──────────────────────────────── */
    document.addEventListener('click', function (ev) {
        var toggle = ev.target.closest('[data-bids-toggle]');
        if (!toggle) { return; }
        var wrap = toggle.closest('.tv2-row-wrap');
        if (!wrap) { return; }
        var panel = wrap.querySelector('.tv2-bids-panel');
        if (panel) { panel.hidden = !panel.hidden; }
    });

    /* ── Filter ────────────────────────────────────────────────────── */
    var state = { scope: null, timing: null, pos: '', mwVon: NaN, mwBis: NaN };

    function applyFilters() {
        var rows = document.querySelectorAll('#tv2-all-listings [data-listing]');
        var shown = 0;
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i];
            var ok = true;
            if (state.scope && r.getAttribute('data-scope') !== state.scope) { ok = false; }
            if (ok && state.timing && r.getAttribute('data-timing') !== state.timing) { ok = false; }
            if (ok && state.pos) {
                var hp = (r.getAttribute('data-hp') || '').split(',');
                var np = (r.getAttribute('data-np') || '').split(',');
                if (hp.indexOf(state.pos) === -1 && np.indexOf(state.pos) === -1) { ok = false; }
            }
            if (ok && !isNaN(state.mwVon)) {
                if (parseFloat(r.getAttribute('data-mw')) < state.mwVon * 1000000) { ok = false; }
            }
            if (ok && !isNaN(state.mwBis)) {
                if (parseFloat(r.getAttribute('data-mw')) > state.mwBis * 1000000) { ok = false; }
            }
            r.hidden = !ok;
            if (ok) { shown++; }
        }
        var count = document.getElementById('tv2-count');
        if (count) { count.textContent = shown + ' von ' + rows.length + ' Listings sichtbar'; }
        var empty = document.getElementById('tv2-filter-empty');
        if (empty) { empty.hidden = (shown > 0 || rows.length === 0); }
    }

    document.querySelectorAll('.tv2-chip-group').forEach(function (group) {
        var key = group.getAttribute('data-filter-group');
        group.addEventListener('click', function (ev) {
            var chip = ev.target.closest('.tv2-chip');
            if (!chip) { return; }
            var val = chip.getAttribute('data-val');
            var wasOn = chip.classList.contains('is-on');
            group.querySelectorAll('.tv2-chip').forEach(function (c) { c.classList.remove('is-on'); });
            if (wasOn) {
                state[key] = null;
            } else {
                chip.classList.add('is-on');
                state[key] = val;
            }
            applyFilters();
        });
    });
    var posSel = document.getElementById('tv2-fpos');
    if (posSel) {
        posSel.addEventListener('change', function () { state.pos = posSel.value; applyFilters(); });
    }
    var mwVon = document.getElementById('tv2-mw-von');
    var mwBis = document.getElementById('tv2-mw-bis');
    function onMw() {
        state.mwVon = mwVon.value.trim() === '' ? NaN : parseFloat(mwVon.value.replace(',', '.'));
        state.mwBis = mwBis.value.trim() === '' ? NaN : parseFloat(mwBis.value.replace(',', '.'));
        applyFilters();
    }
    if (mwVon && mwBis) {
        mwVon.addEventListener('input', onMw);
        mwBis.addEventListener('input', onMw);
    }

    /* ── Deal-Sheet-Modal ──────────────────────────────────────────── */
    var sheetsEl = document.getElementById('tv2-sheets-data');
    var sheets = {};
    if (sheetsEl) {
        try {
            JSON.parse(sheetsEl.textContent).forEach(function (s) { sheets[s.id] = s; });
        } catch (e) { /* leer */ }
    }
    var urls = document.getElementById('tv2-urls');
    var bidUrl = urls ? urls.getAttribute('data-bid-url') : '';
    var buyUrl = urls ? urls.getAttribute('data-buy-url') : '';

    var backdrop = document.getElementById('tv2-sheet-backdrop');
    var elTitle = document.getElementById('tv2-sheet-title');
    var elImg = document.getElementById('tv2-sheet-img');
    var elName = document.getElementById('tv2-sheet-name');
    var elSub = document.getElementById('tv2-sheet-playersub');
    var elBidBlock = document.getElementById('tv2-sheet-bidblock');
    var elAmount = document.getElementById('tv2-sheet-amount');
    var elAmountHidden = document.getElementById('tv2-sheet-amount-hidden');
    var elMinHint = document.getElementById('tv2-sheet-minhint');
    var elSumLabel = document.getElementById('tv2-sheet-sumlabel');
    var elSum = document.getElementById('tv2-sheet-sum');
    var elLevyBlock = document.getElementById('tv2-sheet-levyblock');
    var elLevyPct = document.getElementById('tv2-sheet-levypct');
    var elLevy = document.getElementById('tv2-sheet-levy');
    var elDist = document.getElementById('tv2-sheet-dist');
    var elPayout = document.getElementById('tv2-sheet-payout');
    var elFaNote = document.getElementById('tv2-sheet-fanote');
    var elTiming = document.getElementById('tv2-sheet-timing');
    var elWarn = document.getElementById('tv2-sheet-warn');
    var elForm = document.getElementById('tv2-sheet-form');
    var elListing = document.getElementById('tv2-sheet-listing');
    var elCta = document.getElementById('tv2-sheet-cta');
    var current = null;
    var isBuy = false;

    function recalc() {
        if (!current) { return; }
        var amount = isBuy ? current.buyNow : parseAmount(elAmount.value);
        var valid = !isNaN(amount) && amount > 0;
        elSum.textContent = valid ? euro(amount) : '—';

        var hasLevy = !current.fa && current.levy && current.levy.length > 0;
        elLevyBlock.hidden = !hasLevy;
        if (hasLevy && valid) {
            /* Mindestabgabe je Ausbildungsverein kommt konfiguriert vom
               Server (JUGENDABGABE_MIN_JE_VEREIN) — nie hartkodieren. */
            var levyMin = current.levyMin || 0;
            var total = 0;
            var html = '';
            current.levy.forEach(function (d) {
                var val = Math.max(amount * d.pct_raw, levyMin);
                total += val;
                html += '<div class="tv2-sheet-dist-row"><span>\u21b3 ' + d.club +
                    ' (' + d.pct_label + ')</span><span>' + euro(val) + '</span></div>';
            });
            elDist.innerHTML = html;
            elLevy.textContent = euro(total);
            elPayout.textContent = euro(Math.max(amount - total, 0));
        } else if (hasLevy) {
            elDist.innerHTML = '';
            elLevy.textContent = '—';
            elPayout.textContent = '—';
        }
        elFaNote.hidden = !current.fa;

        var minOk = isBuy || (valid && amount >= current.nextMin);
        elCta.disabled = !(valid && minOk);
        if (!isBuy && valid && !minOk) {
            elMinHint.textContent = 'Zu niedrig — mindestens ' + euro(current.nextMin);
            elMinHint.style.color = '#ff8ba0';
        } else if (!isBuy) {
            elMinHint.textContent = 'Mindestens ' + euro(current.nextMin);
            elMinHint.style.color = '';
        }
    }

    function openSheet(id, buy) {
        current = sheets[id];
        if (!current || !backdrop) { return; }
        isBuy = !!buy;
        elTitle.textContent = isBuy ? 'Sofortkauf bestätigen' : 'Gebot abgeben';
        elImg.src = current.img || '';
        elName.textContent = current.name;
        elSub.textContent = current.sub;
        elBidBlock.hidden = isBuy;
        elSumLabel.textContent = isBuy ? 'Sofortkaufpreis' : 'Gebotssumme';
        if (elLevyPct && current.levyPctLabel) {
            elLevyPct.textContent = current.levyPctLabel;
        }
        elTiming.textContent = current.fa ? 'Sofort' : current.timing;
        elListing.value = id;
        elForm.action = isBuy ? buyUrl : bidUrl;
        elCta.textContent = isBuy ? 'Jetzt kaufen — verbindlich' : 'Gebot abgeben — verbindlich';
        elWarn.textContent = isBuy
            ? 'Sofortkauf ist verbindlich: Der Betrag wird sofort gebucht, die Auktion endet und der Transfer wird ausgeführt (21 Tage Wechselsperre).'
            : 'Gebote sind verbindlich: Der Betrag wird bis zum Auktionsende reserviert. Führst du am Ende, wird der Transfer ausgeführt (21 Tage Wechselsperre).';
        if (!isBuy) {
            elAmount.value = Math.round(current.nextMin).toString()
                .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        }
        recalc();
        backdrop.hidden = false;
        if (!isBuy) { elAmount.focus(); }
    }
    function closeSheet() {
        if (backdrop) { backdrop.hidden = true; }
        current = null;
    }

    document.addEventListener('click', function (ev) {
        var btn = ev.target.closest('[data-sheet-open]');
        if (btn) {
            openSheet(parseInt(btn.getAttribute('data-sheet-open'), 10),
                btn.getAttribute('data-buy') === '1');
        }
    });
    var cancel = document.getElementById('tv2-sheet-cancel');
    if (cancel) { cancel.addEventListener('click', closeSheet); }
    if (backdrop) {
        backdrop.addEventListener('click', function (ev) {
            if (ev.target === backdrop) { closeSheet(); }
        });
    }
    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') { closeSheet(); }
    });
    /* bfcache-Guard: Browser-Back/-Forward kann ein offenes Modal einfrieren. */
    window.addEventListener('pageshow', function (ev) {
        if (ev.persisted) { closeSheet(); }
    });
    if (elAmount) { elAmount.addEventListener('input', recalc); }
    if (elForm) {
        elForm.addEventListener('submit', function () {
            elAmountHidden.value = isBuy
                ? String(Math.round(current.buyNow))
                : String(parseAmount(elAmount.value) || '');
        });
    }
})();
