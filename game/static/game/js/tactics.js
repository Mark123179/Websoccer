(function () {
    const form = document.querySelector('.tactics-form');
    if (!form) {
        return;
    }

    const formationData = readJson('tactics-formation-data', {});
    const players = readJson('tactics-player-data', []);
    const playerById = new Map(players.map((player) => [String(player.id), player]));
    const staticPrefix = form.dataset.staticPrefix || '/static/';
    const formationOrder = [
        'defense',
        'defensive_midfield',
        'midfield',
        'offensive_midfield',
        'attack',
    ];

    function readJson(id, fallback) {
        const node = document.getElementById(id);
        if (!node) {
            return fallback;
        }
        try {
            return JSON.parse(node.textContent);
        } catch (_error) {
            return fallback;
        }
    }

    function selectedFormationCode() {
        return formationOrder
            .map((part) => {
                const select = form.querySelector(`[data-formation-part="${part}"]`);
                return select ? select.value : '';
            })
            .join('-');
    }

    function playerOptionLabel(player) {
        return `${player.name} · ${player.position} · ${player.freshness_label}`;
    }

    function addPlayerOptions(select, selectedValue, emptyLabel) {
        select.innerHTML = '';
        const empty = document.createElement('option');
        empty.value = '';
        empty.textContent = emptyLabel || 'Leer';
        select.append(empty);

        players.forEach((player) => {
            const option = document.createElement('option');
            option.value = String(player.id);
            option.textContent = playerOptionLabel(player);
            option.selected = String(selectedValue || '') === String(player.id);
            select.append(option);
        });
    }

    function matchState(player, code) {
        if (!player) {
            return 'empty';
        }
        if ((player.main_positions || []).includes(code)) {
            return 'main';
        }
        if ((player.secondary_positions || []).includes(code)) {
            return 'secondary';
        }
        return 'foreign';
    }

    function freshnessTone(player) {
        return player ? player.freshness_tone : 'empty';
    }

    function freshnessValue(player) {
        return player && player.freshness !== null ? player.freshness : 0;
    }

    function normalizedMinuteValue(value) {
        const text = String(value || '').trim();
        if (!text) {
            return '';
        }
        const match = text.match(/\d+/);
        if (!match) {
            return '';
        }
        const minute = Math.min(120, Math.max(1, Number.parseInt(match[0], 10)));
        return String(minute);
    }

    function bindMinuteInputs() {
        form.querySelectorAll('[data-minute]').forEach((input) => {
            input.addEventListener('keydown', (event) => {
                if (['e', 'E', '+', '-', '.', ','].includes(event.key)) {
                    event.preventDefault();
                }
            });

            const sanitize = () => {
                const nextValue = normalizedMinuteValue(input.value);
                if (input.value !== nextValue) {
                    input.value = nextValue;
                }
            };
            input.addEventListener('input', sanitize);
            input.addEventListener('blur', sanitize);
        });
    }

    function bindTemplateSave() {
        const saveButton = form.querySelector('[data-save-template]');
        const nameInput = form.querySelector('[data-template-name]');
        if (!saveButton || !nameInput) {
            return;
        }

        const focusNameInput = (event) => {
            event.preventDefault();
            nameInput.classList.add('is-attention');
            nameInput.focus();
        };

        saveButton.addEventListener('click', (event) => {
            if (!nameInput.value.trim()) {
                focusNameInput(event);
            }
        });

        form.addEventListener('submit', (event) => {
            const submitter = event.submitter;
            const isTemplateSave = submitter && submitter.name === 'action' && submitter.value === 'save_template';
            if (isTemplateSave && !nameInput.value.trim()) {
                focusNameInput(event);
            }
        });

        nameInput.addEventListener('input', () => {
            nameInput.classList.remove('is-attention');
        });
    }

    const attackZones = readJson('tactics-attack-zones', {});

    function hiddenByName(name) {
        return form.querySelector(`input[type="hidden"][name="${name}"]`);
    }

    function setToggle(button, on) {
        button.classList.toggle('is-on', on);
        button.setAttribute('aria-pressed', on ? 'true' : 'false');
        const hidden = hiddenByName(button.dataset.target);
        if (hidden) {
            hidden.value = on ? '1' : '0';
        }
    }

    function setSegment(button) {
        const group = button.closest('[data-segmented]');
        if (!group) {
            return;
        }
        group.querySelectorAll('.tactics-segment').forEach((item) => {
            item.classList.toggle('is-active', item === button);
        });
        const hidden = hiddenByName(group.dataset.target);
        if (hidden) {
            hidden.value = button.dataset.value;
        }
    }

    function applyAttackFocus(value) {
        const list = form.querySelector('[data-focus-list]');
        if (!list) {
            return;
        }
        const hidden = list.querySelector('[data-focus-input]');
        if (hidden) {
            hidden.value = value;
        }
        list.querySelectorAll('[data-focus-option]').forEach((option) => {
            option.classList.toggle('is-active', option.dataset.value === value);
        });
        const zones = attackZones[value];
        const pitch = form.querySelector('[data-focus-pitch]');
        if (zones && pitch) {
            ['left', 'center', 'right'].forEach((zone) => {
                const node = pitch.querySelector(`[data-zone="${zone}"]`);
                if (node) {
                    node.style.setProperty('--intensity', zones[zone]);
                }
            });
        }
    }

    function tempoLabel(value) {
        if (value <= 25) {
            return 'Ruhig';
        }
        if (value <= 49) {
            return 'Kontrolliert';
        }
        if (value === 50) {
            return 'Normal';
        }
        if (value <= 75) {
            return 'Zügig';
        }
        return 'Sehr schnell';
    }

    function conditionRows() {
        return Array.from(form.querySelectorAll('[data-conditions-body] [data-condition-row]'));
    }

    function updateConditionAddState() {
        const wrap = form.querySelector('[data-conditions]');
        const addButton = form.querySelector('[data-condition-add]');
        if (!wrap || !addButton) {
            return;
        }
        const max = parseInt(wrap.dataset.max, 10) || 8;
        addButton.disabled = conditionRows().length >= max;
    }

    function reindexConditions() {
        conditionRows().forEach((row, index) => {
            row.querySelectorAll('[name]').forEach((field) => {
                field.name = field.name.replace(/condition_\d+_/, `condition_${index}_`);
            });
            const toggle = row.querySelector('[data-toggle]');
            if (toggle) {
                toggle.dataset.target = `condition_${index}_active`;
            }
        });
        updateConditionAddState();
    }

    function addConditionRow() {
        const wrap = form.querySelector('[data-conditions]');
        const body = form.querySelector('[data-conditions-body]');
        const template = form.querySelector('[data-condition-template]');
        if (!wrap || !body || !template) {
            return;
        }
        const max = parseInt(wrap.dataset.max, 10) || 8;
        if (conditionRows().length >= max) {
            return;
        }
        const index = conditionRows().length;
        const markup = template.innerHTML.replace(/__INDEX__/g, String(index)).trim();
        const holder = document.createElement('div');
        holder.innerHTML = markup;
        const row = holder.firstElementChild;
        if (!row) {
            return;
        }
        body.appendChild(row);
        reindexConditions();
    }

    const TRIGGER_BUDGET = 3;

    function triggerBudgetUsed() {
        let used = 0;
        form.querySelectorAll('[data-trigger-grid] [data-cost].is-on').forEach((btn) => {
            used += parseInt(btn.dataset.cost, 10) || 0;
        });
        return used;
    }

    function updateTriggerBudget() {
        const counter = form.querySelector('[data-trigger-budget]');
        if (!counter) {
            return;
        }
        const used = triggerBudgetUsed();
        counter.textContent = `${used}/${TRIGGER_BUDGET}`;
        counter.classList.toggle('is-over', used >= TRIGGER_BUDGET);
        form.querySelectorAll('[data-trigger-grid] [data-cost]').forEach((btn) => {
            if (!btn.classList.contains('is-on')) {
                const cost = parseInt(btn.dataset.cost, 10) || 0;
                btn.disabled = used + cost > TRIGGER_BUDGET;
            } else {
                btn.disabled = false;
            }
        });
    }

    function bindInstructions() {
        form.addEventListener('click', (event) => {
            const toggle = event.target.closest('[data-toggle]');
            if (toggle && form.contains(toggle)) {
                const turningOn = !toggle.classList.contains('is-on');
                if (turningOn && toggle.dataset.cost !== undefined) {
                    const cost = parseInt(toggle.dataset.cost, 10) || 0;
                    if (triggerBudgetUsed() + cost > TRIGGER_BUDGET) {
                        return;
                    }
                }
                setToggle(toggle, turningOn);
                if (toggle.dataset.cost !== undefined) {
                    updateTriggerBudget();
                }
                return;
            }
            const segment = event.target.closest('.tactics-segment');
            if (segment && form.contains(segment)) {
                setSegment(segment);
                return;
            }
            const focusOption = event.target.closest('[data-focus-option]');
            if (focusOption && form.contains(focusOption)) {
                applyAttackFocus(focusOption.dataset.value);
                return;
            }
            const addButton = event.target.closest('[data-condition-add]');
            if (addButton && form.contains(addButton)) {
                addConditionRow();
                return;
            }
            const removeButton = event.target.closest('[data-condition-remove]');
            if (removeButton && form.contains(removeButton)) {
                const row = removeButton.closest('[data-condition-row]');
                if (row) {
                    row.remove();
                    reindexConditions();
                }
            }
        });

        form.addEventListener('change', (event) => {
            const minute = event.target.closest('[data-minute]');
            if (!minute) {
                return;
            }
            let value = parseInt(String(minute.value).replace(/\D/g, ''), 10);
            if (!Number.isFinite(value)) {
                value = 1;
            }
            value = Math.max(1, Math.min(120, value));
            minute.value = String(value).padStart(2, '0');
        });

        const tempo = form.querySelector('[data-tempo]');
        if (tempo) {
            tempo.addEventListener('input', () => {
                const value = parseInt(tempo.value, 10) || 0;
                const valueNode = form.querySelector('[data-tempo-value]');
                const labelNode = form.querySelector('[data-tempo-label]');
                if (valueNode) {
                    valueNode.textContent = value;
                }
                if (labelNode) {
                    labelNode.textContent = tempoLabel(value);
                }
            });
        }

        updateConditionAddState();
        updateTriggerBudget();
    }

    function updateSlotCard(slotNode) {
        const select = slotNode.querySelector('select[data-assignment]');
        const player = playerById.get(String(select.value || ''));
        const code = slotNode.dataset.code;
        slotNode.className = `tactics-slot is-${matchState(player, code)}`;

        const portraitWrap = slotNode.querySelector('.tactics-slot-portrait');
        portraitWrap.innerHTML = '';
        if (player) {
            const image = document.createElement('img');
            image.src = `${staticPrefix}${player.portrait}`;
            image.alt = player.name;
            portraitWrap.append(image);
        } else {
            portraitWrap.append(document.createElement('span'));
        }

        slotNode.querySelector('.tactics-slot-name').textContent = player ? player.name : 'Leer';
        const freshness = slotNode.querySelector('.tactics-freshness');
        freshness.className = `tactics-freshness is-${freshnessTone(player)}`;
        freshness.style.setProperty('--freshness', freshnessValue(player));
        freshness.textContent = player ? player.freshness_label : '-';
    }

    function updateBenchRow(select) {
        const row = select.closest('.tactics-bench-row');
        if (!row) {
            return;
        }
        const media = row.querySelector('img, i');
        const player = playerById.get(String(select.value || ''));
        if (player) {
            const image = document.createElement('img');
            image.src = `${staticPrefix}${player.portrait}`;
            image.alt = player.name;
            media.replaceWith(image);
        } else {
            const placeholder = document.createElement('i');
            media.replaceWith(placeholder);
        }
        const name = row.querySelector('strong');
        const position = row.querySelector('.tactics-bench-position');
        const freshness = row.querySelector('.tactics-freshness');
        if (name) {
            name.textContent = player ? player.name : 'Leer';
        }
        if (position) {
            position.textContent = player ? player.position : '-';
        }
        if (freshness) {
            freshness.className = `tactics-freshness is-${freshnessTone(player)}`;
            freshness.style.setProperty('--freshness', freshnessValue(player));
            freshness.textContent = player ? player.freshness_label : '-';
        }
    }

    function assignmentSelects() {
        return Array.from(form.querySelectorAll('select[data-assignment]'));
    }

    function handleAssignmentChange(event) {
        const changed = event.currentTarget;
        const value = changed.value;
        if (value) {
            assignmentSelects().forEach((select) => {
                if (select !== changed && select.value === value) {
                    select.value = '';
                    if (select.dataset.area === 'lineup') {
                        updateSlotCard(select.closest('.tactics-slot'));
                    } else {
                        updateBenchRow(select);
                    }
                }
            });
        }
        if (changed.dataset.area === 'lineup') {
            updateSlotCard(changed.closest('.tactics-slot'));
        } else {
            updateBenchRow(changed);
        }
        updateStatusNumbers();
        updateRosterList();
        refreshStandardOptions();
        refreshSubstitutionOptions();
        updateCaptainBadges();
    }

    function bindAssignments() {
        assignmentSelects().forEach((select) => {
            select.removeEventListener('change', handleAssignmentChange);
            select.addEventListener('change', handleAssignmentChange);
        });
    }

    function currentLineupSelections() {
        const selections = {};
        form.querySelectorAll('[data-slots-layer] select[data-assignment]').forEach((select) => {
            const key = select.dataset.slotKey;
            selections[key] = select.value;
        });
        return selections;
    }

    function createSlot(slot, selectedValue) {
        const slotNode = document.createElement('article');
        slotNode.className = 'tactics-slot is-empty';
        slotNode.dataset.slot = slot.key;
        slotNode.dataset.code = slot.code;
        slotNode.dataset.group = slot.group;
        slotNode.style.left = `${slot.x}%`;
        slotNode.style.top = `${slot.y}%`;

        const card = document.createElement('div');
        card.className = 'tactics-slot-card';

        const position = document.createElement('span');
        position.className = 'tactics-slot-position';
        position.textContent = slot.code;

        const captainBadge = document.createElement('img');
        captainBadge.className = 'tactics-captain-badge';
        captainBadge.dataset.captainBadge = '';
        captainBadge.src = `${staticPrefix}game/images/icons/captain-armband.png?v=yellow-20260519`;
        captainBadge.alt = 'Kapitän';

        const portrait = document.createElement('div');
        portrait.className = 'tactics-slot-portrait';
        portrait.append(document.createElement('span'));

        const name = document.createElement('strong');
        name.className = 'tactics-slot-name';
        name.textContent = 'Leer';

        const freshness = document.createElement('em');
        freshness.className = 'tactics-freshness is-empty';
        freshness.style.setProperty('--freshness', 0);
        freshness.textContent = '-';

        const select = document.createElement('select');
        select.name = `lineup_${slot.key}`;
        select.dataset.assignment = '';
        select.dataset.area = 'lineup';
        select.dataset.slotKey = slot.key;
        select.dataset.slotCode = slot.code;
        select.setAttribute('aria-label', `${slot.code} besetzen`);
        addPlayerOptions(select, selectedValue, 'Leer');

        card.append(position, captainBadge, portrait, name, freshness, select);
        slotNode.append(card);
        updateSlotCard(slotNode);
        return slotNode;
    }

    function updateFormationSummary(summaryRows) {
        const summary = form.querySelector('[data-formation-summary]');
        if (!summary) {
            return;
        }
        summary.innerHTML = '';
        summaryRows.forEach((row) => {
            const wrap = document.createElement('div');
            const dt = document.createElement('dt');
            const dd = document.createElement('dd');
            const code = document.createElement('b');
            dt.textContent = row.label;
            code.textContent = row.code;
            dd.append(code, ` ${row.positions}`);
            wrap.append(dt, dd);
            summary.append(wrap);
        });
    }

    function applyFormation() {
        const code = selectedFormationCode();
        const data = formationData[code];
        if (!data) {
            return;
        }
        const selections = currentLineupSelections();
        const pitch = form.querySelector('[data-slots-layer]');
        pitch.innerHTML = '';
        data.slots.forEach((slot) => {
            pitch.append(createSlot(slot, selections[slot.key] || ''));
        });
        form.querySelectorAll('[data-formation-label]').forEach((label) => {
            label.textContent = code;
        });
        updateFormationSummary(data.summaries);
        updateFormationMini(data.slots);
        updateLayerCounts(data.slots);
        bindAssignments();
        updateStatusNumbers();
        updateRosterList();
        refreshStandardOptions();
        refreshSubstitutionOptions();
        updateCaptainBadges();
    }

    function selectedLineupPlayers() {
        return Array.from(form.querySelectorAll('[data-slots-layer] select[data-assignment]'))
            .filter((select) => select.value)
            .map((select) => ({
                id: select.value,
                name: playerById.get(select.value)?.name || select.value,
            }));
    }

    function selectedBenchPlayers() {
        return Array.from(form.querySelectorAll('.tactics-bench-row select[data-assignment]'))
            .filter((select) => select.value)
            .map((select) => ({
                id: select.value,
                name: playerById.get(select.value)?.name || select.value,
            }));
    }

    function selectedFieldCount() {
        return Array.from(form.querySelectorAll('[data-slots-layer] .tactics-slot'))
            .filter((slot) => slot.dataset.group !== 'goalkeeper')
            .filter((slot) => slot.querySelector('select[data-assignment]')?.value)
            .length;
    }

    function averageFreshness() {
        const values = Array.from(form.querySelectorAll('[data-slots-layer] select[data-assignment]'))
            .map((select) => playerById.get(String(select.value || '')))
            .filter((player) => player && player.freshness !== null)
            .map((player) => Number(player.freshness));

        if (!values.length) {
            return '-';
        }
        return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
    }

    function updateStatusNumbers() {
        const fieldCount = form.querySelector('[data-field-count]');
        if (fieldCount) {
            const count = selectedFieldCount();
            fieldCount.textContent = `${count}/10`;
            const indicator = fieldCount.parentElement.querySelector('span');
            if (indicator) {
                indicator.classList.toggle('is-complete', count === 10);
            }
        }
        const average = form.querySelector('[data-average-freshness]');
        if (average) {
            average.textContent = averageFreshness();
        }
    }

    function updateFormationMini(slots) {
        const mini = form.querySelector('[data-formation-dots]');
        if (!mini) {
            return;
        }
        mini.innerHTML = '';
        slots.forEach((slot) => {
            const dot = document.createElement('i');
            dot.className = `is-${slot.group}`;
            dot.style.left = `${slot.x}%`;
            dot.style.top = `${slot.y}%`;
            mini.append(dot);
        });
    }

    function updateLayerCounts(slots) {
        const counts = slots.reduce((result, slot) => {
            if (slot.group === 'attack') {
                result.attack += 1;
            } else if (slot.group === 'defense') {
                result.defense += 1;
            } else if (slot.group === 'goalkeeper') {
                result.goalkeeper += 1;
            } else {
                result.midfield += 1;
            }
            return result;
        }, { attack: 0, midfield: 0, defense: 0, goalkeeper: 0 });

        Object.entries(counts).forEach(([key, value]) => {
            const node = form.querySelector(`[data-count-${key}]`);
            if (node) {
                node.textContent = value;
            }
        });
    }

    function updateRosterList() {
        const selected = new Set(
            Array.from(form.querySelectorAll('[data-slots-layer] select[data-assignment]'))
                .map((select) => select.value)
                .filter(Boolean)
        );
        form.querySelectorAll('[data-roster-player]').forEach((row) => {
            row.classList.toggle('is-on-pitch', selected.has(row.dataset.rosterPlayer));
        });
    }

    function replaceOptions(select, playersList, emptyLabel) {
        const previous = select.value;
        select.innerHTML = '';
        const empty = document.createElement('option');
        empty.value = '';
        empty.textContent = emptyLabel;
        select.append(empty);
        playersList.forEach((player) => {
            const option = document.createElement('option');
            option.value = player.id;
            option.textContent = player.name;
            option.selected = previous === player.id;
            select.append(option);
        });
    }

    function refreshStandardOptions() {
        const lineup = selectedLineupPlayers();
        form.querySelectorAll('[data-standard-select]').forEach((select) => {
            replaceOptions(select, lineup, 'Nicht gesetzt');
        });
    }

    function refreshSubstitutionOptions() {
        const lineup = selectedLineupPlayers();
        const bench = selectedBenchPlayers();
        form.querySelectorAll('[data-sub-out]').forEach((select) => {
            replaceOptions(select, lineup, 'Spieler raus');
        });
        form.querySelectorAll('[data-sub-in]').forEach((select) => {
            replaceOptions(select, bench, 'Spieler rein');
        });
    }

    function clearLineupAndBench() {
        assignmentSelects().forEach((select) => {
            select.value = '';
            if (select.dataset.area === 'lineup') {
                updateSlotCard(select.closest('.tactics-slot'));
            } else {
                updateBenchRow(select);
            }
        });
        updateStatusNumbers();
        updateRosterList();
        refreshStandardOptions();
        refreshSubstitutionOptions();
        updateCaptainBadges();
    }

    function updateCaptainBadges() {
        const captainSelect = form.querySelector('[data-standard-select="captain"]');
        const captainId = captainSelect ? String(captainSelect.value || '') : '';
        form.querySelectorAll('[data-slots-layer] .tactics-slot').forEach((slot) => {
            const select = slot.querySelector('select[data-assignment]');
            const badge = slot.querySelector('[data-captain-badge]');
            if (badge) {
                badge.classList.toggle('is-visible', Boolean(captainId && select && select.value === captainId));
            }
        });
    }

    form.querySelectorAll('[data-orientation]').forEach((range) => {
        range.addEventListener('input', () => {
            const value = range.closest('.tactics-orientation').querySelector('strong');
            value.textContent = range.value;
        });
    });

    const applyButton = form.querySelector('[data-apply-formation]');
    if (applyButton) {
        applyButton.addEventListener('click', applyFormation);
    }

    const clearLineupButton = form.querySelector('[data-clear-lineup]');
    if (clearLineupButton) {
        let clearConfirmTimer = null;

        function resetClearButton() {
            clearTimeout(clearConfirmTimer);
            clearConfirmTimer = null;
            clearLineupButton.classList.remove('is-confirming');
            clearLineupButton.innerHTML = clearLineupButton.dataset.originalHtml;
        }

        clearLineupButton.dataset.originalHtml = clearLineupButton.innerHTML;

        clearLineupButton.addEventListener('click', () => {
            if (clearLineupButton.classList.contains('is-confirming')) {
                resetClearButton();
                clearLineupAndBench();
            } else {
                clearLineupButton.classList.add('is-confirming');
                clearLineupButton.innerHTML = '<span class="tactics-clear-lineup-confirm-label">Sicher?</span>';
                clearConfirmTimer = setTimeout(resetClearButton, 2000);
            }
        });
    }

    bindAssignments();
    bindMinuteInputs();
    bindTemplateSave();
    bindInstructions();
    updateStatusNumbers();
    updateRosterList();
    refreshStandardOptions();
    refreshSubstitutionOptions();
    updateCaptainBadges();

    form.querySelectorAll('[data-standard-select]').forEach((select) => {
        select.addEventListener('change', updateCaptainBadges);
    });
}());
