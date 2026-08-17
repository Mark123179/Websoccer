/* Show-Auktion — Bühne + Detailseite.
   Countdown lokal, Wahrheit kommt vom Server (status.json-Poll alle 15 s).
   Preise entscheidet IMMER der Server — das JS zeigt nur an (Spec §4.3).
   Modal wird an <body> portalt und mit --game-scale mitskaliert
   (Muster: weather.js — transform:scale-Vorfahre fängt position:fixed ein). */
(function () {
    'use strict';

    var root = document.querySelector('[data-sxa-root]');
    if (!root) return;
    var CSRF = root.getAttribute('data-csrf') || '';

    /* ---------- Formatierung ---------- */
    function fmtNum(n) { return Number(n).toLocaleString('de-DE'); }
    function fmtEuro(n) { return fmtNum(n) + ' €'; }
    function fmtWord(n) {
        if (!n) return '\u200b';
        if (n >= 1e6) return '= ' + (n / 1e6).toLocaleString('de-DE', { maximumFractionDigits: 1 }) + ' Millionen €';
        if (n >= 1e3) return '= ' + (n / 1e3).toLocaleString('de-DE', { maximumFractionDigits: 1 }) + ' Tausend €';
        return '= ' + fmtNum(n) + ' €';
    }
    function fmtTime(sec) {
        sec = Math.max(0, Math.floor(sec));
        var d = Math.floor(sec / 86400),
            h = Math.floor((sec % 86400) / 3600),
            m = Math.floor((sec % 3600) / 60),
            s = sec % 60,
            p = function (n) { return String(n).padStart(2, '0'); };
        return d > 0 ? d + 'T ' + p(h) + ':' + p(m) + ':' + p(s) : p(h) + ':' + p(m) + ':' + p(s);
    }

    /* ---------- Countdowns ---------- */
    var clocks = [];
    document.querySelectorAll('[data-sxa-countdown]').forEach(function (el) {
        var rem = parseInt(el.getAttribute('data-remaining'), 10);
        if (isNaN(rem)) return;
        clocks.push({ el: el, endAt: Date.now() + rem * 1000, expired: false });
    });

    var reloadArmed = false;
    function tick() {
        var now = Date.now();
        clocks.forEach(function (c) {
            var rem = (c.endAt - now) / 1000;
            var label = c.el.querySelector('[data-sxa-time]') || c.el;
            label.textContent = fmtTime(rem);
            if (rem < 3600) c.el.classList.add('is-hot');
            else c.el.classList.remove('is-hot');
            if (rem <= 0 && !c.expired) {
                c.expired = true;
                /* Ablauf: Serverseite entscheidet — einmal neu laden (Lazy-Resolve). */
                if (!reloadArmed) {
                    reloadArmed = true;
                    setTimeout(function () { window.location.reload(); }, 2500);
                }
            }
        });
    }
    if (clocks.length) { tick(); setInterval(tick, 1000); }

    /* ---------- HTTP ---------- */
    function post(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF,
            },
            credentials: 'same-origin',
            body: JSON.stringify(payload || {}),
        }).then(function (resp) {
            return resp.json().catch(function () {
                return { ok: false, fehler: 'Unerwartete Antwort des Servers.' };
            });
        }).catch(function () {
            return { ok: false, fehler: 'Netzwerkfehler — bitte erneut versuchen.' };
        });
    }

    /* ---------- Modal (Portal an <body>, --game-scale) ---------- */
    var modal = document.getElementById('sxaBidModal');
    var overlay = document.getElementById('sxaBidOverlay');
    var portaled = false;

    function gameScale() {
        var v = getComputedStyle(document.documentElement).getPropertyValue('--game-scale');
        var f = parseFloat(v);
        return isNaN(f) || f <= 0 ? 1 : f;
    }

    function openModal(mode) {
        if (!modal) return;
        if (!portaled) {
            document.body.appendChild(overlay);
            document.body.appendChild(modal);
            portaled = true;
        }
        modal.style.setProperty('--sxa-scale', String(gameScale()));
        modal.setAttribute('data-mode', mode);
        overlay.hidden = false;
        modal.hidden = false;
        var input = modal.querySelector('#sxaBidInput');
        var inputRows = modal.querySelectorAll('[data-sxa-only-bid]');
        inputRows.forEach(function (el) { el.hidden = (mode !== 'bid'); });
        var buyRows = modal.querySelectorAll('[data-sxa-only-buy]');
        buyRows.forEach(function (el) { el.hidden = (mode !== 'buy'); });
        if (mode === 'bid' && input) {
            input.value = '';
            syncBidState();
            setTimeout(function () { input.focus(); }, 40);
        } else {
            syncBuyState();
        }
        setErr('');
    }

    function closeModal() {
        if (!modal) return;
        overlay.hidden = true;
        modal.hidden = true;
    }

    function setErr(msg) {
        var el = modal && modal.querySelector('#sxaBidErr');
        if (el) el.textContent = msg || '\u200b';
    }

    /* ---------- Gebotslogik im Modal ---------- */
    function modalData() {
        return {
            min: parseInt(modal.getAttribute('data-min'), 10) || 0,
            konto: parseInt(modal.getAttribute('data-konto'), 10),
            bidUrl: modal.getAttribute('data-bid-url'),
            buyUrl: modal.getAttribute('data-buy-url'),
        };
    }

    function currentAmount() {
        var input = modal.querySelector('#sxaBidInput');
        var digits = (input.value || '').replace(/\D/g, '').slice(0, 12);
        return digits ? parseInt(digits, 10) : 0;
    }

    function syncBidState() {
        var d = modalData();
        var input = modal.querySelector('#sxaBidInput');
        var amt = currentAmount();
        input.value = amt ? fmtNum(amt) : '';
        modal.querySelector('#sxaBidWord').textContent = fmtWord(amt);

        var minOk = amt >= d.min;
        var kontoKnown = !isNaN(d.konto);
        var balanceOk = !kontoKnown || amt <= d.konto;
        var balEl = modal.querySelector('#sxaBalanceStatus');
        if (balEl) {
            balEl.textContent = !amt ? '—' : (balanceOk ? '✓ Gedeckt' : '✗ Nicht gedeckt');
            balEl.style.color = !amt ? 'var(--muted)' : (balanceOk ? 'var(--green)' : 'var(--red, #ff5570)');
        }
        if (amt && !minOk) setErr('Unter dem Mindestgebot von ' + fmtEuro(d.min));
        else if (amt && !balanceOk) setErr('Der Betrag übersteigt euer verfügbares Guthaben.');
        else setErr('');

        var btn = modal.querySelector('#sxaBidConfirm');
        var valid = amt > 0 && minOk && balanceOk;
        btn.classList.toggle('is-valid', valid);
        btn.disabled = !valid;
    }

    function syncBuyState() {
        var btn = modal.querySelector('#sxaBidConfirm');
        btn.classList.add('is-valid');
        btn.disabled = false;
    }

    if (modal) {
        var input = modal.querySelector('#sxaBidInput');
        if (input) {
            input.addEventListener('input', syncBidState);
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') { e.preventDefault(); submitModal(); }
            });
        }
        modal.querySelector('#sxaBidCancel').addEventListener('click', closeModal);
        overlay.addEventListener('click', closeModal);
        modal.querySelector('#sxaBidConfirm').addEventListener('click', submitModal);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.hidden) closeModal();
        });
        /* bfcache-Guard: Browser-Back/-Forward kann ein offenes Modal einfrieren. */
        window.addEventListener('pageshow', function (e) {
            if (e.persisted) { closeModal(); }
        });
    }

    var submitting = false;
    function submitModal() {
        if (submitting) return;
        var d = modalData();
        var mode = modal.getAttribute('data-mode');
        var btn = modal.querySelector('#sxaBidConfirm');
        if (btn.disabled) return;
        var req;
        if (mode === 'buy') {
            req = post(d.buyUrl, {});
        } else {
            var amt = currentAmount();
            if (!amt) return;
            req = post(d.bidUrl, { amount: amt });
        }
        submitting = true;
        btn.disabled = true;
        req.then(function (res) {
            submitting = false;
            if (res.ok) {
                window.location.reload();
            } else {
                btn.disabled = false;
                setErr(res.fehler || 'Aktion fehlgeschlagen.');
            }
        });
    }

    document.querySelectorAll('[data-sxa-open-bid]').forEach(function (btn) {
        btn.addEventListener('click', function () { openModal('bid'); });
    });
    document.querySelectorAll('[data-sxa-open-buy]').forEach(function (btn) {
        btn.addEventListener('click', function () { openModal('buy'); });
    });

    /* ---------- Beobachten ---------- */
    document.querySelectorAll('[data-sxa-watch]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            post(btn.getAttribute('data-sxa-watch'), {}).then(function (res) {
                if (!res.ok) return;
                btn.classList.toggle('is-watched', !!res.beobachtet);
                var label = btn.querySelector('[data-sxa-watch-label]');
                if (label) {
                    label.textContent = res.beobachtet
                        ? 'Auf der Beobachtungsliste' : 'Beobachten';
                }
            });
        });
    });

    /* ---------- Server-Resync (Detailseite) ---------- */
    var poll = document.querySelector('[data-sxa-poll]');
    if (poll) {
        var pollUrl = poll.getAttribute('data-sxa-poll');
        var initialStatus = poll.getAttribute('data-status');
        setInterval(function () {
            fetch(pollUrl, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (!d.ok) return;
                    if (d.status !== initialStatus) { window.location.reload(); return; }
                    /* Restzeit hart resyncen */
                    if (d.restzeit_s !== null && clocks.length) {
                        clocks.forEach(function (c) {
                            if (c.el.hasAttribute('data-sxa-main-clock')) {
                                c.endAt = Date.now() + d.restzeit_s * 1000;
                            }
                        });
                    }
                    var set = function (sel, val) {
                        var el = document.querySelector(sel);
                        if (el && val !== null && val !== undefined) el.textContent = val;
                    };
                    set('[data-sxa-live-bid]', d.preis_aktuell_fmt);
                    set('[data-sxa-live-count]', d.bid_count);
                    set('[data-sxa-live-min]', d.naechstes_min_fmt);
                    if (d.heat !== null && d.heat !== undefined) {
                        var fill = document.querySelector('[data-sxa-heat-fill]');
                        if (fill) fill.style.width = d.heat + '%';
                        set('[data-sxa-heat-label]', d.heat_label);
                    }
                    /* Mindestgebot im Modal nachziehen */
                    if (modal && d.naechstes_min_fmt) {
                        var raw = d.naechstes_min_fmt.replace(/[^\d]/g, '');
                        if (raw) {
                            modal.setAttribute('data-min', raw);
                            var minEl = modal.querySelector('#sxaBidMinValue');
                            if (minEl) minEl.textContent = d.naechstes_min_fmt;
                        }
                    }
                })
                .catch(function () { /* Poll-Fehler still — nächster Takt kommt */ });
        }, 15000);
    }
})();
