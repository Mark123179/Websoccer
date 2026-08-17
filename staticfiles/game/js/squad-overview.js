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
        return getCookie('csrftoken');
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

        updateSelectionUI();
        applyFilters();
    });
})();
