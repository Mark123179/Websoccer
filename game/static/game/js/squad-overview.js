(function () {
    'use strict';

    function ready(fn) {
        if (document.readyState !== 'loading') { fn(); }
        else { document.addEventListener('DOMContentLoaded', fn); }
    }

    function getCookie(name) {
        const match = document.cookie.match(
            new RegExp('(^|;)\\s*' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : '';
    }

    function getCsrfToken() {
        const bar = document.getElementById('squadActionBar');
        const fromBar = bar && bar.getAttribute('data-csrf');
        if (fromBar) { return fromBar; }
        const bidModal = document.getElementById('bidModal');
        const fromBid = bidModal && bidModal.getAttribute('data-csrf');
        return fromBid || getCookie('csrftoken');
    }

    ready(function () {
        const body = document.getElementById('squadTableBody');
        if (!body) { return; }

        const rows = Array.from(body.querySelectorAll('.squad-row'));
        const search = document.getElementById('squadSearch');
        const filterBar = document.getElementById('squadFilterBar');
        const noMatch = document.getElementById('squadNoMatch');
        const checkAll = document.getElementById('squadCheckAll');
        const actionBar = document.getElementById('squadActionBar');
        const selCount = document.getElementById('selCount');
        const selClear = document.getElementById('selClear');
        const actYouth = document.getElementById('actYouth');
        const pitchNodes = Array.from(
            document.querySelectorAll('.pitch-node'));
        const toast = document.getElementById('squadToast');

        let activePos = 'ALL';
        let toastTimer = null;

        /* ---------------- toast ---------------- */
        function showToast(message, kind) {
            if (!toast) { return; }
            toast.textContent = message;
            toast.className = 'squad-toast' + (kind ? ' squad-toast--' + kind : '');
            toast.hidden = false;
            if (toastTimer) { clearTimeout(toastTimer); }
            toastTimer = setTimeout(function () { toast.hidden = true; }, 3200);
        }

        /* ---------------- filtering ---------------- */
        function rowMatches(row) {
            const term = (search && search.value || '').trim().toLowerCase();
            const name = row.getAttribute('data-name') || '';
            const positions = ' ' + (row.getAttribute('data-pos') || '') + ' ';
            const okName = !term || name.indexOf(term) !== -1;
            const okPos = activePos === 'ALL' ||
                positions.indexOf(' ' + activePos + ' ') !== -1;
            return okName && okPos;
        }

        function applyFilters() {
            let visible = 0;
            rows.forEach(function (row) {
                const show = rowMatches(row);
                row.style.display = show ? '' : 'none';
                if (show) { visible += 1; }
            });
            if (noMatch) { noMatch.hidden = visible !== 0 || rows.length === 0; }
            syncCheckAll();
        }

        /* ---------------- sorting ---------------- */
        const originalOrder = rows.slice();   // server-seitige Reihenfolge (nach Position)
        let sortKey = null;
        let sortDir = 'desc';

        function clearSortIndicators() {
            document.querySelectorAll('.sortable[data-sort-key]').forEach(function (h) {
                h.classList.remove('sort-asc', 'sort-desc', 'sort-pos');
                h.removeAttribute('aria-sort');
            });
        }

        document.querySelectorAll('.sortable[data-sort-key]').forEach(function (th) {
            th.addEventListener('click', function () {
                const key = th.getAttribute('data-sort-key');

                /* Position-Spalte: Originalreihenfolge wiederherstellen */
                if (key === 'pos') {
                    clearSortIndicators();
                    sortKey = null;
                    th.classList.add('sort-pos');
                    originalOrder.forEach(function (row) { body.appendChild(row); });
                    return;
                }

                if (sortKey === key) {
                    sortDir = sortDir === 'desc' ? 'asc' : 'desc';
                } else {
                    sortKey = key;
                    sortDir = 'desc';
                }
                clearSortIndicators();
                th.classList.add('sort-' + sortDir);
                th.setAttribute('aria-sort', sortDir === 'desc' ? 'descending' : 'ascending');

                const sorted = rows.slice().sort(function (a, b) {
                    const aCell = a.querySelector('[data-sort-key="' + key + '"]');
                    const bCell = b.querySelector('[data-sort-key="' + key + '"]');
                    const aVal = parseFloat((aCell && aCell.getAttribute('data-sort-val')) || '0');
                    const bVal = parseFloat((bCell && bCell.getAttribute('data-sort-val')) || '0');
                    if (sortDir === 'desc') {
                        if (aVal === 9999 && bVal !== 9999) { return 1; }
                        if (bVal === 9999 && aVal !== 9999) { return -1; }
                        return bVal - aVal;
                    }
                    if (aVal === 9999 && bVal !== 9999) { return 1; }
                    if (bVal === 9999 && aVal !== 9999) { return -1; }
                    return aVal - bVal;
                });
                sorted.forEach(function (row) { body.appendChild(row); });
            });
        });

        if (search) { search.addEventListener('input', applyFilters); }

        if (filterBar) {
            filterBar.addEventListener('click', function (event) {
                const chip = event.target.closest('.squad-chip');
                if (!chip) { return; }
                activePos = chip.getAttribute('data-pos') || 'ALL';
                filterBar.querySelectorAll('.squad-chip').forEach(function (c) {
                    c.classList.toggle('is-active', c === chip);
                });
                highlightPitch();
                applyFilters();
            });
        }

        function highlightPitch() {
            pitchNodes.forEach(function (node) {
                const code = node.getAttribute('data-pos');
                if (activePos === 'ALL') {
                    node.classList.remove('is-hot', 'is-dim');
                } else {
                    node.classList.toggle('is-hot', code === activePos);
                    node.classList.toggle('is-dim', code !== activePos);
                }
            });
        }

        /* ---------------- selection ---------------- */
        function selectedRows() {
            return rows.filter(function (row) {
                const cb = row.querySelector('.squad-row-check');
                return cb && cb.checked && row.style.display !== 'none';
            });
        }

        function syncCheckAll() {
            if (!checkAll) { return; }
            const visible = rows.filter(function (r) {
                return r.style.display !== 'none';
            });
            const checked = visible.filter(function (r) {
                const cb = r.querySelector('.squad-row-check');
                return cb && cb.checked;
            });
            checkAll.checked = visible.length > 0 && checked.length === visible.length;
            checkAll.indeterminate = checked.length > 0 &&
                checked.length < visible.length;
        }

        function updateSelectionUI() {
            const selected = selectedRows();
            rows.forEach(function (row) {
                const cb = row.querySelector('.squad-row-check');
                row.classList.toggle('is-selected', cb && cb.checked);
            });
            if (selCount) { selCount.textContent = String(selected.length); }
            if (actionBar) { actionBar.hidden = selected.length === 0; }
            if (actYouth) {
                const allYouth = selected.length > 0 && selected.every(function (r) {
                    return r.getAttribute('data-youth') === '1';
                });
                actYouth.disabled = !allYouth;
                actYouth.title = allYouth ? '' :
                    'Nur möglich, wenn alle Ausgewählten unter 21 sind.';
            }
            syncCheckAll();
        }

        body.addEventListener('change', function (event) {
            if (event.target.classList.contains('squad-row-check')) {
                updateSelectionUI();
            }
        });

        if (checkAll) {
            checkAll.addEventListener('change', function () {
                const visible = rows.filter(function (r) {
                    return r.style.display !== 'none';
                });
                visible.forEach(function (r) {
                    const cb = r.querySelector('.squad-row-check');
                    if (cb) { cb.checked = checkAll.checked; }
                });
                updateSelectionUI();
            });
        }

        if (selClear) {
            selClear.addEventListener('click', function () {
                rows.forEach(function (r) {
                    const cb = r.querySelector('.squad-row-check');
                    if (cb) { cb.checked = false; }
                });
                updateSelectionUI();
            });
        }

        /* ---------------- actions ---------------- */
        const shirtUrl = actionBar && actionBar.getAttribute('data-shirt-url');
        const youthUrl = actionBar && actionBar.getAttribute('data-youth-url');

        function postAction(url, playerId, extra) {
            const data = new URLSearchParams();
            data.append('player_id', playerId);
            if (extra) {
                Object.keys(extra).forEach(function (k) {
                    data.append(k, extra[k]);
                });
            }
            return fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: data.toString()
            }).then(function (r) {
                return r.json().then(function (j) {
                    return { ok: r.ok, data: j };
                });
            });
        }

        if (actionBar) {
            actionBar.addEventListener('click', function (event) {
                const btn = event.target.closest('.squad-act');
                if (!btn) { return; }
                const act = btn.getAttribute('data-act');
                const selected = selectedRows();
                if (selected.length === 0) { return; }

                if (act === 'shirt') {
                    openShirtModal(selected[0]);
                } else if (act === 'youth') {
                    if (btn.disabled) { return; }
                    runYouth(selected);
                } else if (act === 'edit') {
                    showToast('Bearbeitung beantragen – genaueres folgt.', 'ok');
                } else if (act === 'sale') {
                    openSaleModal(selected);
                } else if (act === 'loan') {
                    showToast('Auf Leihliste setzen – folgt.', 'ok');
                }
            });
        }

        function runYouth(selected) {
            let done = 0;
            let failed = 0;
            const total = selected.length;
            selected.forEach(function (row) {
                const pid = row.getAttribute('data-player');
                postAction(youthUrl, pid).then(function (res) {
                    if (res.ok && res.data.ok) { done += 1; }
                    else { failed += 1; }
                }).catch(function () { failed += 1; }).finally(function () {
                    if (done + failed === total) {
                        if (failed === 0) {
                            showToast(done + ' Spieler in die Jugend übernommen.', 'ok');
                        } else {
                            showToast(failed + ' von ' + total +
                                ' konnten nicht verschoben werden.', 'error');
                        }
                    }
                });
            });
        }

        /* ---------------- shirt modal ---------------- */
        const modal = document.getElementById('shirtModal');
        const modalPlayer = document.getElementById('shirtModalPlayer');
        const shirtInput = document.getElementById('shirtInput');
        const shirtError = document.getElementById('shirtError');
        const shirtSave = document.getElementById('shirtSave');
        let modalRow = null;

        function openShirtModal(row) {
            modalRow = row;
            const nameEl = row.querySelector('.squad-player__name');
            const shirtEl = row.querySelector('.squad-shirt');
            if (modalPlayer) {
                modalPlayer.textContent = nameEl ? nameEl.textContent : '';
            }
            if (shirtInput) {
                const cur = shirtEl ? shirtEl.textContent.trim() : '';
                shirtInput.value = /^\d+$/.test(cur) ? cur : '';
            }
            if (shirtError) { shirtError.hidden = true; }
            if (modal) { modal.hidden = false; }
            if (shirtInput) { shirtInput.focus(); }
        }

        function closeShirtModal() {
            if (modal) { modal.hidden = true; }
            modalRow = null;
        }

        if (modal) {
            modal.addEventListener('click', function (event) {
                if (event.target.hasAttribute('data-close')) { closeShirtModal(); }
            });
        }
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && modal && !modal.hidden) {
                closeShirtModal();
            }
        });

        if (shirtSave) {
            shirtSave.addEventListener('click', function () {
                if (!modalRow) { return; }
                const pid = modalRow.getAttribute('data-player');
                const value = (shirtInput.value || '').trim();
                shirtSave.disabled = true;
                postAction(shirtUrl, pid, { shirt_number: value })
                    .then(function (res) {
                        if (res.ok && res.data.ok) {
                            const shirtEl = modalRow.querySelector('.squad-shirt');
                            if (shirtEl) {
                                shirtEl.textContent = res.data.shirt_number == null
                                    ? '–' : res.data.shirt_number;
                            }
                            showToast('Rückennummer gespeichert.', 'ok');
                            closeShirtModal();
                        } else {
                            if (shirtError) {
                                shirtError.textContent = (res.data && res.data.error) ||
                                    'Speichern fehlgeschlagen.';
                                shirtError.hidden = false;
                            }
                        }
                    })
                    .catch(function () {
                        if (shirtError) {
                            shirtError.textContent = 'Netzwerkfehler.';
                            shirtError.hidden = false;
                        }
                    })
                    .finally(function () { shirtSave.disabled = false; });
            });
        }

        if (shirtInput) {
            shirtInput.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') { shirtSave.click(); }
            });
        }

        /* ---------------- sale modal (Verkaufsstatus) ---------------- */
        const saleModal = document.getElementById('saleModal');
        const saleModalPlayers = document.getElementById('saleModalPlayers');
        const saleCategory = document.getElementById('saleCategory');
        const saleVisible = document.getElementById('saleVisible');
        const saleError = document.getElementById('saleError');
        const saleSave = document.getElementById('saleSave');
        const saleUrl = actionBar && actionBar.getAttribute('data-sale-url');
        let saleRows = [];

        function openSaleModal(selected) {
            if (!saleModal) { return; }
            saleRows = selected;
            if (saleModalPlayers) {
                const names = selected.map(function (r) {
                    const el = r.querySelector('.squad-player__name');
                    return el ? el.textContent.trim() : '';
                }).filter(Boolean);
                saleModalPlayers.textContent = names.length <= 3
                    ? names.join(', ')
                    : names.slice(0, 3).join(', ') + ' + ' +
                      (names.length - 3) + ' weitere';
            }
            if (selected.length === 1) {
                saleCategory.value =
                    selected[0].getAttribute('data-sale-cat') || 'UVK';
                saleVisible.checked =
                    selected[0].getAttribute('data-sale-vis') === '1';
            } else {
                saleCategory.value = 'UVK';
                saleVisible.checked = false;
            }
            if (saleError) { saleError.hidden = true; }
            saleModal.hidden = false;
        }

        function closeSaleModal() {
            if (saleModal) { saleModal.hidden = true; }
            saleRows = [];
        }

        if (saleModal) {
            saleModal.addEventListener('click', function (event) {
                if (event.target.hasAttribute('data-close')) { closeSaleModal(); }
            });
        }

        if (saleSave) {
            saleSave.addEventListener('click', function () {
                if (!saleRows.length || !saleUrl) { return; }
                const data = new URLSearchParams();
                saleRows.forEach(function (r) {
                    data.append('player_ids', r.getAttribute('data-player'));
                });
                data.append('sale_category', saleCategory.value);
                data.append('sale_visible_to_ai', saleVisible.checked ? '1' : '0');
                saleSave.disabled = true;
                fetch(saleUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: data.toString()
                }).then(function (r) {
                    return r.json().then(function (j) {
                        return { ok: r.ok, data: j };
                    });
                }).then(function (res) {
                    if (res.ok && res.data.ok) {
                        showToast('Verkaufsstatus für ' + res.data.updated +
                            ' Spieler gespeichert.', 'ok');
                        closeSaleModal();
                        setTimeout(function () { window.location.reload(); }, 700);
                    } else if (saleError) {
                        saleError.textContent = (res.data && res.data.error) ||
                            'Speichern fehlgeschlagen.';
                        saleError.hidden = false;
                    }
                }).catch(function () {
                    if (saleError) {
                        saleError.textContent = 'Netzwerkfehler.';
                        saleError.hidden = false;
                    }
                }).finally(function () { saleSave.disabled = false; });
            });
        }

        /* ---------------- bid modal (Angebot an KI-Verein) ---------------- */
        const bidModal = document.getElementById('bidModal');
        const bidModalPlayer = document.getElementById('bidModalPlayer');
        const bidModalMv = document.getElementById('bidModalMv');
        const bidNegoInfo = document.getElementById('bidNegoInfo');
        const bidNegoText = document.getElementById('bidNegoText');
        const bidAcceptCounter = document.getElementById('bidAcceptCounter');
        const bidCancelNego = document.getElementById('bidCancelNego');
        const bidField = document.getElementById('bidField');
        const bidInput = document.getElementById('bidInput');
        const bidError = document.getElementById('bidError');
        const bidResult = document.getElementById('bidResult');
        const bidSend = document.getElementById('bidSend');
        let bidRow = null;

        function bidPost(url, params) {
            const data = new URLSearchParams();
            Object.keys(params).forEach(function (k) {
                data.append(k, params[k]);
            });
            return fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: data.toString()
            }).then(function (r) {
                return r.json().then(function (j) {
                    return { ok: r.ok, data: j };
                });
            });
        }

        function refreshBidModalState() {
            if (!bidRow) { return; }
            const negoId = bidRow.getAttribute('data-nego-id');
            const counterFmt = bidRow.getAttribute('data-nego-counter-fmt');
            const runde = bidRow.getAttribute('data-nego-runde');
            const cooldown = bidRow.getAttribute('data-nego-cooldown');
            if (bidNegoInfo) {
                bidNegoInfo.hidden = !negoId;
                if (negoId && bidNegoText) {
                    bidNegoText.textContent = 'Laufende Verhandlung (Runde ' +
                        runde + '): Der Verein fordert ' + counterFmt + '.';
                }
            }
            if (cooldown) {
                if (bidError) {
                    bidError.textContent = 'Abgelehnt — neues Angebot erst ab ' +
                        cooldown + ' möglich.';
                    bidError.hidden = false;
                }
                if (bidField) { bidField.hidden = true; }
                if (bidSend) { bidSend.disabled = true; }
            } else {
                if (bidField) { bidField.hidden = false; }
                if (bidSend) { bidSend.disabled = false; }
            }
        }

        function openBidModal(row) {
            if (!bidModal) { return; }
            bidRow = row;
            const nameEl = row.querySelector('.squad-player__name');
            if (bidModalPlayer) {
                bidModalPlayer.textContent = nameEl ? nameEl.textContent.trim() : '';
            }
            if (bidModalMv) {
                bidModalMv.textContent =
                    'Marktwert: ' + (row.getAttribute('data-mv') || '–');
            }
            if (bidInput) { bidInput.value = ''; }
            if (bidError) { bidError.hidden = true; }
            if (bidResult) { bidResult.hidden = true; }
            refreshBidModalState();
            bidModal.hidden = false;
            if (bidInput && !bidField.hidden) { bidInput.focus(); }
        }

        function closeBidModal() {
            if (bidModal) { bidModal.hidden = true; }
            bidRow = null;
        }

        function handleBidResponse(res) {
            if (!(res.ok && res.data.ok)) {
                if (bidError) {
                    bidError.textContent = (res.data && res.data.error) ||
                        'Aktion fehlgeschlagen.';
                    bidError.hidden = false;
                }
                return;
            }
            if (bidError) { bidError.hidden = true; }
            if (bidResult) {
                bidResult.textContent = res.data.message || '';
                bidResult.hidden = false;
            }
            const nego = res.data.negotiation || {};
            if (res.data.ergebnis === 'deal') {
                setTimeout(function () { window.location.reload(); }, 1400);
                return;
            }
            if (bidRow) {
                if (res.data.ergebnis === 'gegenforderung') {
                    bidRow.setAttribute('data-nego-id', nego.id);
                    bidRow.setAttribute('data-nego-runde', nego.runde);
                    bidRow.setAttribute('data-nego-counter', nego.gegenforderung);
                    bidRow.setAttribute('data-nego-counter-fmt',
                        nego.gegenforderung_fmt || '');
                } else {
                    bidRow.removeAttribute('data-nego-id');
                    bidRow.removeAttribute('data-nego-runde');
                    bidRow.removeAttribute('data-nego-counter');
                    bidRow.removeAttribute('data-nego-counter-fmt');
                    setTimeout(function () { window.location.reload(); }, 1400);
                }
            }
            refreshBidModalState();
        }

        if (bidModal) {
            bidModal.addEventListener('click', function (event) {
                if (event.target.hasAttribute('data-close')) { closeBidModal(); }
            });
            body.addEventListener('click', function (event) {
                const btn = event.target.closest('[data-bid]');
                if (!btn) { return; }
                const row = btn.closest('.squad-row');
                if (row) { openBidModal(row); }
            });
            document.addEventListener('keydown', function (event) {
                if (event.key === 'Escape' && !bidModal.hidden) {
                    closeBidModal();
                }
            });
        }

        if (bidSend) {
            bidSend.addEventListener('click', function () {
                if (!bidRow) { return; }
                const raw = (bidInput.value || '').trim();
                if (!raw) {
                    if (bidError) {
                        bidError.textContent = 'Bitte einen Betrag eingeben.';
                        bidError.hidden = false;
                    }
                    return;
                }
                bidSend.disabled = true;
                bidPost(bidModal.getAttribute('data-bid-url'), {
                    player_id: bidRow.getAttribute('data-player'),
                    betrag: raw
                }).then(handleBidResponse).catch(function () {
                    if (bidError) {
                        bidError.textContent = 'Netzwerkfehler.';
                        bidError.hidden = false;
                    }
                }).finally(function () { bidSend.disabled = false; });
            });
        }

        if (bidAcceptCounter) {
            bidAcceptCounter.addEventListener('click', function () {
                if (!bidRow) { return; }
                const negoId = bidRow.getAttribute('data-nego-id');
                if (!negoId) { return; }
                bidAcceptCounter.disabled = true;
                bidPost(bidModal.getAttribute('data-accept-url'), {
                    negotiation_id: negoId
                }).then(handleBidResponse).catch(function () {
                    if (bidError) {
                        bidError.textContent = 'Netzwerkfehler.';
                        bidError.hidden = false;
                    }
                }).finally(function () { bidAcceptCounter.disabled = false; });
            });
        }

        if (bidCancelNego) {
            bidCancelNego.addEventListener('click', function () {
                if (!bidRow) { return; }
                const negoId = bidRow.getAttribute('data-nego-id');
                if (!negoId) { return; }
                bidCancelNego.disabled = true;
                bidPost(bidModal.getAttribute('data-cancel-url'), {
                    negotiation_id: negoId
                }).then(handleBidResponse).catch(function () {
                    if (bidError) {
                        bidError.textContent = 'Netzwerkfehler.';
                        bidError.hidden = false;
                    }
                }).finally(function () { bidCancelNego.disabled = false; });
            });
        }

        /* ------- Manager-Postfach: eingehende KI-Kaufangebote (Phase 6) ------- */
        const aiPanel = document.getElementById('aiOfferPanel');
        if (aiPanel) {
            aiPanel.addEventListener('click', function (ev) {
                const btn = ev.target.closest('.ai-offer-act');
                if (!btn) { return; }
                const card = btn.closest('.ai-offer');
                const offerId = card && card.getAttribute('data-offer');
                if (!offerId) { return; }
                const accept = btn.getAttribute('data-act') === 'accept';
                const url = aiPanel.getAttribute(
                    accept ? 'data-accept-url' : 'data-reject-url');
                const params = new URLSearchParams();
                params.set('offer_id', offerId);
                card.querySelectorAll('.ai-offer-act').forEach(function (b) {
                    b.disabled = true;
                });
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': aiPanel.getAttribute('data-csrf') || getCsrfToken(),
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: params.toString(),
                    credentials: 'same-origin'
                }).then(function (r) { return r.json(); }).then(function (data) {
                    if (!data.ok) {
                        showToast(data.error || 'Aktion fehlgeschlagen.', 'error');
                        card.querySelectorAll('.ai-offer-act').forEach(function (b) {
                            b.disabled = false;
                        });
                        return;
                    }
                    showToast(data.message || 'Erledigt.', 'success');
                    setTimeout(function () { window.location.reload(); }, 1400);
                }).catch(function () {
                    showToast('Netzwerkfehler.', 'error');
                    card.querySelectorAll('.ai-offer-act').forEach(function (b) {
                        b.disabled = false;
                    });
                });
            });
        }

        updateSelectionUI();
        applyFilters();
    });
})();
