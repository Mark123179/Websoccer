/* Personal, browser-local presentation editor. Never changes game data. */
(() => {
    "use strict";
    const root = document.querySelector(".match-preview-scene");
    const canvas = root?.querySelector(".match-preview-panels");
    const open = document.getElementById("mp-layout-open");
    const tools = document.getElementById("mp-layout-tools");
    if (!root || !canvas || !open || !tools) return;

    const key = `fm:match-preview:layout:1:${root.dataset.layoutOwner || "guest"}`;
    const revision = Number(root.dataset.layoutRevision) || 1;
    const detailPatch = Number(root.dataset.layoutDetailPatch) || 0;
    const backupKey = `${key}:before-revision-${revision}${detailPatch ? `:details-${detailPatch}` : ""}`;
    const $ = name => document.getElementById(`mp-layout-${name}`);
    const status = message => { $("status").textContent = message; };
    const clone = value => JSON.parse(JSON.stringify(value));
    const limits = {
        x: [-10000, 10000], y: [-10000, 10000], width: [0.25, 500],
        height: [0.25, 500], font: [8, 96], layer: [0, 200],
    };
    const clean = raw => {
        if (!raw || raw.version !== 1 || typeof raw.nodes !== "object" || !raw.nodes) return null;
        const nodes = Object.create(null);
        Object.entries(raw.nodes).slice(0, 300).forEach(([id, data]) => {
            if (!/^[a-z0-9_-]{1,80}$/.test(id) || !data || typeof data !== "object") return;
            if (!["x", "y", "width", "height"].every(field =>
                Number.isFinite(data[field]) && data[field] >= limits[field][0] &&
                data[field] <= limits[field][1])) return;
            const frame = {
                x: data.x, y: data.y, width: data.width, height: data.height,
                hidden: data.hidden === true,
            };
            ["font", "layer"].forEach(field => {
                if (Number.isFinite(data[field]) && data[field] >= limits[field][0] &&
                    data[field] <= limits[field][1]) frame[field] = data[field];
            });
            nodes[id] = frame;
        });
        return {version: 1, revision: Number.isInteger(raw.revision) ? raw.revision : 1,
            detailPatch: Number.isInteger(raw.detailPatch) ? raw.detailPatch : 0, nodes};
    };
    let saved = null, previousLayout = null, storageError = "";
    try {
        const value = localStorage.getItem(key);
        if (value) {
            saved = clean(JSON.parse(value));
            if (!saved) storageError = "Das gespeicherte Layout ist ungültig. Standardansicht geladen.";
            else if (saved.revision !== revision) {
                // Approved screenshot-derived composition replaces old geometry,
                // not the stored original. Back it up before the next explicit save.
                previousLayout = value;
                saved = null;
                storageError = "Die abgestimmte Anordnung ist geladen. Dein bisheriger Entwurf bleibt gesichert.";
            }
            else if (saved.detailPatch < detailPatch) previousLayout = value;
        }
    } catch {
        storageError = "Der Browserspeicher ist nicht verfügbar. Änderungen können nicht gespeichert werden.";
    }

    // Stable presentation slots, not player IDs: the same layout works for next fixtures.
    const specs = [
        [".match-preview-panel--scout", "scout", "Linke Kachel"],
        [".match-preview-panel--center", "center", "Mittlere Kachel"],
        [".match-preview-panel--club", "club", "Rechte Kachel"],
        [".mp-panel-heading", "heading", "Kachelüberschrift"],
        [".mp-pitch", "pitch", "Spielfeld"],
        [".mp-player-marker", "player", "Aufstellung · Spieler"],
        [".mp-player-marker .mp-player-portrait", "player-photo", "Aufstellung · Porträt"],
        [".mp-player-marker .mp-player-name", "player-name", "Aufstellung · Name", "text"],
        [".mp-player-number", "shirt-number", "Aufstellung · Rückennummer", "text"],
        [".mp-player-grade", "grade", "Aufstellung · Note", "text"],
        [".mp-caption", "caption", "Beschriftung", "text"],
        [".mp-trainer", "trainer", "Trainerprofil"],
        [".mp-trainer .mp-avatar", "trainer-photo", "Trainer · Porträt"],
        [".mp-trainer-copy", "trainer-name", "Trainer · Name", "text"],
        [".mp-subsection", "section", "Gegner · Informationsblock"],
        [".mp-subsection .mp-form", "opponent-form", "Gegner · Form"],
        [".mp-last-result", "last-result", "Letztes Ergebnis"],
        [".mp-absence-list li", "absence", "Ausfall"],
        [".mp-absence-group", "absence-group", "Ausfälle / Sperren"],
        [".mp-absence-heading", "absence-heading", "Ausfälle · Überschrift", "text"],
        [".mp-competition", "competition", "Wettbewerb"],
        [".mp-competition-logo", "competition-logo", "Wettbewerbslogo"],
        [".mp-competition > div", "competition-text", "Wettbewerb · Beschriftung"],
        [".mp-competition h1", "competition-name", "Wettbewerbsname", "text"],
        [".mp-competition .mp-eyebrow", "matchday", "Spieltag", "text"],
        [".mp-versus", "matchup", "Mannschaftsvergleich"],
        [".mp-club--home", "home", "Heimmannschaft"],
        [".mp-club--away", "away", "Auswärtsmannschaft"],
        [".mp-club--home .mp-crest-link", "home-crest", "Heim · Wappen"],
        [".mp-club--away .mp-crest-link", "away-crest", "Auswärts · Wappen"],
        [".mp-club--home h2", "home-name", "Heim · Vereinsname", "text"],
        [".mp-club--away h2", "away-name", "Auswärts · Vereinsname", "text"],
        [".mp-club--home .mp-kit", "home-kit", "Heim · Trikot"],
        [".mp-club--away .mp-kit", "away-kit", "Auswärts · Trikot"],
        [".mp-club--home .mp-team-form", "home-form", "Heim · Form"],
        [".mp-club--away .mp-team-form", "away-form", "Auswärts · Form"],
        [".mp-versus-mark", "versus", "VS-Zeichen"],
        [".mp-versus-mark > span", "versus-symbol", "VS · Beschriftung", "text"],
        [".mp-kickoff", "kickoff", "Anstoß"],
        [".mp-home-venue", "venue", "Austragungsort", "text"],
        [".mp-match-facts", "facts", "Spieldetails"],
        [".mp-fact", "fact", "Spieldetail"],
        [".mp-form-stats", "stats", "Stadionfoto / Ausfälle"],
        [".mp-form-stats-photo", "venue-photo", "Stadionfoto"],
        [".mp-form-stats .mp-report-heading", "stats-heading", "Statistiküberschrift", "text"],
        [".mp-report-team", "team-stats", "Mannschaft · Statistik"],
        [".mp-report-team-link", "stats-team-name", "Statistik · Vereinsname", "text"],
        [".mp-report-team-heading time", "stats-date", "Statistik · Datum", "text"],
        [".mp-report-form", "stats-form", "Statistik · Form"],
        [".mp-report-stats > div", "stat", "Statistikwert", "text"],
        [".mp-model-card", "model", "3D / Schiedsrichter"],
        [".mp-model-card .mp-report-heading", "model-heading", "3D-Überschrift", "text"],
        [".mp-model-viewport", "model-viewport", "3D-Stadion"],
        [".mp-stadium-demo-note", "model-note", "3D-Testhinweis", "text"],
        [".mp-referee-profile", "referee", "Schiedsrichterprofil"],
        [".mp-referee-portrait", "referee-photo", "Schiedsrichter · Porträt"],
        [".mp-referee-info", "referee-info", "Schiedsrichter · Angaben", "text"],
        [".mp-referee-info h2", "referee-name", "Schiedsrichter · Name", "text"],
        [".mp-referee-meta", "referee-meta", "Schiedsrichter · Herkunft / Niveau", "text"],
        [".mp-referee-info > p", "referee-summary", "Schiedsrichter · Beschreibung", "text"],
        [".mp-referee-ratings", "referee-ratings", "Schiedsrichter · Werte"],
        [".mp-weather-profile", "weather", "Wetterprofil"],
        [".mp-weather-animation", "weather-scene", "Wetter · Animation"],
        [".mp-weather-info", "weather-info", "Wetter · Angaben", "text"],
        [".mp-spotlight", "spotlight", "Spieler im Fokus"],
        [".mp-spotlight-label", "spotlight-title", "Fokus · Überschrift", "text"],
        [".mp-avatar--spotlight", "spotlight-photo", "Fokus · Porträt"],
        [".mp-spotlight-copy", "spotlight-name", "Fokus · Name", "text"],
        [".mp-spotlight-value", "spotlight-value", "Fokus · Kennzahl", "text"],
        [".mp-news", "news", "Vereinsnews"],
        [".mp-news-item", "news-item", "Nachricht"],
        [".mp-subsection-heading", "subheading", "Abschnittsüberschrift", "text"],
    ];
    const items = [], byId = new Map();
    specs.forEach(([selector, prefix, label, kind]) => {
        canvas.querySelectorAll(selector).forEach((node, index) => {
            if (node.dataset.mpLayoutItem) return;
            const id = `${prefix}-${index}`;
            node.dataset.mpLayoutItem = id;
            const item = {id, node, label: `${label}${index ? ` ${index + 1}` : ""}`, kind};
            items.push(item);
            byId.set(id, item);
        });
    });
    // Ancestors first. Children can be restored into their original wrapper afterwards.
    const depth = node => {
        let value = 0;
        for (let parent = node.parentElement; parent && parent !== canvas; parent = parent.parentElement) value++;
        return value;
    };
    items.sort((a, b) => depth(a.node) - depth(b.node));
    items.forEach(item => {
        const parentNode = item.node.parentElement.closest("[data-mp-layout-item]");
        item.parent = parentNode ? byId.get(parentNode.dataset.mpLayoutItem) : null;
        item.originalStyle = item.node.getAttribute("style");
        item.originalFontSize = item.node.style.fontSize;
        item.originalZIndex = item.node.style.zIndex;
        item.anchor = document.createComment(`layout:${item.id}`);
        item.node.before(item.anchor);
        if (item.parent) item.parent.group = true;
    });

    document.body.append(open, tools);
    const selection = document.createElement("div");
    selection.className = "mp-layout-selection";
    selection.hidden = true;
    const dragLabel = document.createElement("button");
    dragLabel.type = "button";
    dragLabel.className = "mp-layout-drag-label";
    dragLabel.setAttribute("aria-label", "Ausgewähltes Element verschieben");
    selection.append(dragLabel);
    for (const edge of ["n", "ne", "e", "se", "s", "sw", "w", "nw"]) {
        const handle = document.createElement("button");
        handle.type = "button";
        handle.className = "mp-layout-resize-handle";
        handle.dataset.edge = edge;
        handle.setAttribute("aria-label", `Größe ändern (${edge.toUpperCase()})`);
        selection.append(handle);
    }
    document.body.append(selection);
    let editing = false, free = false, selected = null, baseline = null, draft = null;
    let gesture = null, raf = 0, openingDraft = "";

    const parentOf = item => item.parent?.node || canvas;
    const dimensions = item => {
        const parent = parentOf(item);
        return {width: parent.clientWidth || 1, height: parent.clientHeight || 1};
    };
    const empty = () => ({version: 1, revision, detailPatch, nodes: Object.create(null)});
    function captureBaseline() {
        const rects = new Map(items.map(item => [item.id, item.node.getBoundingClientRect()]));
        const canvasRect = canvas.getBoundingClientRect();
        const scale = canvasRect.width / (canvas.offsetWidth || 1);
        const layout = empty();
        items.forEach(item => {
            const rect = rects.get(item.id);
            const parentRect = item.parent ? rects.get(item.parent.id) : canvasRect;
            const parent = parentOf(item), size = dimensions(item);
            layout.nodes[item.id] = {
                x: ((rect.left - parentRect.left) / scale - parent.clientLeft) / size.width * 100,
                y: ((rect.top - parentRect.top) / scale - parent.clientTop) / size.height * 100,
                width: rect.width / scale / size.width * 100,
                height: rect.height / scale / size.height * 100,
                hidden: false,
            };
        });
        return layout;
    }
    function paint(item, frame) {
        if (!frame) return;
        Object.assign(item.node.style, {
            position: "absolute", left: `${frame.x}%`, top: `${frame.y}%`,
            width: `${frame.width}%`, height: `${frame.height}%`,
            margin: "0", transform: "none", translate: "none", flex: "none",
            right: "auto", bottom: "auto", boxSizing: "border-box",
        });
        item.node.style.fontSize = frame.font !== undefined ? `${frame.font}px` : item.originalFontSize;
        item.node.style.zIndex = frame.layer !== undefined ? frame.layer : item.originalZIndex;
        item.node.toggleAttribute("data-mp-layout-font", frame.font !== undefined);
        if (frame.font !== undefined) item.node.style.setProperty("--mp-layout-font", `${frame.font}px`);
        else item.node.style.removeProperty("--mp-layout-font");
        item.node.classList.toggle("mp-layout-item-hidden", frame.hidden);
    }
    function useFree(layout) {
        if (!free) {
            items.forEach(item => {
                item.node.classList.toggle("mp-layout-group", !!item.group);
            });
            root.classList.add("mp-layout-free");
            free = true;
        }
        items.forEach(item => paint(item, layout.nodes[item.id] || baseline.nodes[item.id]));
    }
    function useDefault() {
        items.forEach(item => {
            if (item.anchor.parentNode) item.anchor.after(item.node);
            if (item.originalStyle === null) item.node.removeAttribute("style");
            else item.node.setAttribute("style", item.originalStyle);
            item.node.classList.remove("mp-layout-item-hidden", "mp-layout-group");
            item.node.removeAttribute("data-mp-layout-font");
        });
        root.classList.remove("mp-layout-free");
        free = false;
    }
    function repairDetails(layout) {
        if (!detailPatch || layout.detailPatch >= detailPatch) return;
        // Preserve the user's away-kit geometry and all group positions.
        // Only the matching home kit, form placement and broken detail subtree change.
        const home = byId.get("home-kit-0"), away = byId.get("away-kit-0");
        if (home && away && layout.nodes[away.id]) {
            const a = dimensions(away), h = dimensions(home);
            const source = layout.nodes[away.id], target = layout.nodes[home.id];
            const crest = layout.nodes["home-crest-0"];
            target.width = source.width * a.width / h.width;
            target.height = source.height * a.height / h.height;
            target.y = source.y * a.height / h.height;
            if (crest) {
                target.x = crest.x + crest.width / 2 - target.width / 2;
                crest.layer = Math.max(2, crest.layer || 0);
                paint(byId.get("home-crest-0"), crest);
            }
            target.layer = 0;
            paint(home, target);
            for (const side of ["home", "away"]) {
                const kit = byId.get(`${side}-kit-0`), form = byId.get(`${side}-form-0`);
                if (!kit || !form) continue;
                const kitSize = dimensions(kit), formSize = dimensions(form);
                const kitFrame = layout.nodes[kit.id], formFrame = layout.nodes[form.id];
                formFrame.y = ((kitFrame.y + kitFrame.height) / 100 * kitSize.height + 8) /
                    formSize.height * 100;
                paint(form, formFrame);
            }
            const venue = byId.get("venue-0"), form = byId.get("home-form-0");
            if (venue && form) {
                const f = layout.nodes[form.id], v = layout.nodes[venue.id];
                v.y = Math.max(v.y, ((f.y + f.height) / 100 * dimensions(form).height + 8) /
                    dimensions(venue).height * 100);
                paint(venue, v);
            }
        }
        const model = byId.get("model-0");
        if (model) {
            layout.nodes[model.id].height = baseline.nodes[model.id].height;
            paint(model, layout.nodes[model.id]);
            items.forEach(item => {
                let parent = item.parent;
                while (parent && parent !== model) parent = parent.parent;
                if (parent !== model) return;
                layout.nodes[item.id] = clone(baseline.nodes[item.id]);
                paint(item, layout.nodes[item.id]);
            });
        }
        layout.detailPatch = detailPatch;
    }
    function updateSelection() {
        if (!editing || !selected) { selection.hidden = true; return; }
        const rect = selected.node.getBoundingClientRect();
        selection.hidden = false;
        Object.assign(selection.style, {
            left: `${rect.left}px`, top: `${rect.top}px`,
            width: `${rect.width}px`, height: `${rect.height}px`,
        });
        dragLabel.textContent = selected.label;
    }
    const refreshSelection = () => {
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(updateSelection);
    };
    function updateControls() {
        const frame = selected && draft.nodes[selected.id];
        const size = selected && dimensions(selected);
        ["x", "y", "width", "height"].forEach(field => {
            const input = $(field);
            input.disabled = !frame;
            input.value = frame ? Math.round(frame[field] / 100 *
                (["x", "width"].includes(field) ? size.width : size.height)) : "";
        });
        $("font").disabled = !selected || selected.kind !== "text";
        $("font").value = selected?.kind === "text"
            ? Math.round(frame?.font || parseFloat(getComputedStyle(selected.node).fontSize)) : "";
        $("visible").disabled = !frame;
        $("visible").checked = frame ? !frame.hidden : true;
        $("parent").disabled = !selected?.parent;
        $("back").disabled = $("front").disabled = !selected;
        $("select").value = selected?.id || "";
        refreshSelection();
    }
    function choose(item) {
        selected = item || null;
        updateControls();
    }
    function activate() {
        if (editing) return;
        // Capture normal flow while all geometry is measurable, then detach only presentation nodes.
        if (!free) baseline = captureBaseline();
        draft = clone(saved || empty());
        items.forEach(item => {
            if (!draft.nodes[item.id]) draft.nodes[item.id] = clone(baseline.nodes[item.id]);
        });
        openingDraft = JSON.stringify(draft);
        useFree(draft);
        editing = true;
        root.classList.add("mp-layout-editing");
        open.setAttribute("aria-expanded", "true");
        tools.hidden = false;
        open.hidden = true;
        choose(items[0]);
        status(storageError || "Element anklicken oder aus der Liste wählen. Änderungen sind noch nicht gespeichert.");
    }
    function close(keep) {
        if (!editing) return;
        gesture = null;
        editing = false;
        root.classList.remove("mp-layout-editing");
        open.setAttribute("aria-expanded", "false");
        tools.hidden = true;
        open.hidden = false;
        selection.hidden = true;
        if (keep) useFree(saved);
        else if (saved) useFree(saved);
        else useDefault();
        selected = null;
        open.focus();
    }
    function commit() {
        try {
            const value = clean(draft);
            if (!value) throw new Error("Invalid layout");
            if (previousLayout) localStorage.setItem(backupKey, previousLayout);
            localStorage.setItem(key, JSON.stringify(value));
            previousLayout = null;
            saved = value;
            storageError = "";
            close(true);
            open.textContent = "Layout bearbeiten";
        } catch {
            status("Speichern fehlgeschlagen. Dein Entwurf bleibt geöffnet. Bitte Browserspeicher freigeben.");
        }
    }
    function reset() {
        if (!window.confirm("Standardlayout wiederherstellen? Erst „Speichern“ ersetzt dein gespeichertes Layout.")) return;
        useDefault();
        baseline = captureBaseline();
        draft = clone(baseline);
        useFree(draft);
        choose(items[0]);
        status("Standardlayout wiederhergestellt. Speichern übernimmt es, Abbrechen behält dein bisheriges Layout.");
    }
    function change(field, value) {
        if (!selected || !Number.isFinite(value)) return;
        const frame = draft.nodes[selected.id];
        const size = dimensions(selected);
        const units = field === "font" ? value :
            value / (["x", "width"].includes(field) ? size.width : size.height) * 100;
        frame[field] = Math.max(limits[field][0], Math.min(limits[field][1], units));
        paint(selected, frame);
        updateControls();
        status("Ungespeicherte Änderungen.");
    }
    function begin(event, edge = "") {
        if (!editing || !selected || event.button !== 0) return;
        event.preventDefault();
        const parent = parentOf(selected), rect = parent.getBoundingClientRect();
        gesture = {
            id: event.pointerId, element: event.currentTarget, item: selected, edge,
            x: event.clientX, y: event.clientY, initial: clone(draft.nodes[selected.id]),
            parentWidth: rect.width - parent.clientLeft * 2 * rect.width / parent.offsetWidth,
            parentHeight: rect.height - parent.clientTop * 2 * rect.height / parent.offsetHeight,
        };
        event.currentTarget.setPointerCapture(event.pointerId);
    }
    function move(event) {
        if (!gesture || gesture.id !== event.pointerId) return;
        const {item, initial, edge} = gesture;
        const dx = (event.clientX - gesture.x) / (gesture.parentWidth || 1) * 100;
        const dy = (event.clientY - gesture.y) / (gesture.parentHeight || 1) * 100;
        const frame = {...initial};
        if (!edge) {
            frame.x += dx; frame.y += dy;
        } else {
            if (edge.includes("e")) frame.width += dx;
            if (edge.includes("s")) frame.height += dy;
            if (edge.includes("w")) { frame.x += dx; frame.width -= dx; }
            if (edge.includes("n")) { frame.y += dy; frame.height -= dy; }
            const size = dimensions(item);
            const minW = Math.min(100, 12 / size.width * 100);
            const minH = Math.min(100, 12 / size.height * 100);
            if (frame.width < minW) {
                frame.width = minW;
                if (edge.includes("w")) frame.x = initial.x + initial.width - minW;
            }
            if (frame.height < minH) {
                frame.height = minH;
                if (edge.includes("n")) frame.y = initial.y + initial.height - minH;
            }
        }
        ["x", "y", "width", "height"].forEach(field => {
            frame[field] = Math.max(limits[field][0], Math.min(limits[field][1], frame[field]));
        });
        draft.nodes[item.id] = frame;
        paint(item, frame);
        updateControls();
    }
    function end(event) {
        if (!gesture || gesture.id !== event.pointerId) return;
        if (event.type === "pointercancel") {
            draft.nodes[gesture.item.id] = gesture.initial;
            paint(gesture.item, gesture.initial);
        }
        gesture = null;
        updateControls();
        status("Ungespeicherte Änderungen.");
    }
    open.addEventListener("click", activate);
    $("save").addEventListener("click", commit);
    $("cancel").addEventListener("click", () => close(false));
    $("reset").addEventListener("click", reset);
    $("select").replaceChildren(...items.map(item => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.label;
        return option;
    }));
    $("select").addEventListener("change", event => choose(byId.get(event.target.value)));
    $("parent").addEventListener("click", () => choose(selected?.parent));
    ["x", "y", "width", "height", "font"].forEach(field =>
        $(field).addEventListener("change", event => {
            if (event.target.value.trim()) change(field, Number(event.target.value));
        }));
    $("visible").addEventListener("change", event => {
        if (!selected) return;
        draft.nodes[selected.id].hidden = !event.target.checked;
        paint(selected, draft.nodes[selected.id]);
        updateControls();
    });
    ["back", "front"].forEach((direction, index) =>
        $(direction).addEventListener("click", () => {
            if (!selected) return;
            const frame = draft.nodes[selected.id];
            frame.layer = Math.max(0, Math.min(200, (frame.layer || 1) + (index ? 1 : -1)));
            paint(selected, frame);
            updateControls();
        }));
    canvas.addEventListener("pointerdown", event => {
        if (!editing || event.button !== 0) return;
        const node = event.target.closest("[data-mp-layout-item]");
        if (!node) return;
        choose(byId.get(node.dataset.mpLayoutItem));
        begin(event);
    }, true);
    canvas.addEventListener("click", event => {
        if (!editing) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
    dragLabel.addEventListener("pointerdown", event => begin(event));
    selection.querySelectorAll("[data-edge]").forEach(handle =>
        handle.addEventListener("pointerdown", event => begin(event, handle.dataset.edge)));
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end);
    document.addEventListener("pointercancel", end);
    document.addEventListener("keydown", event => {
        if (!editing) return;
        if (event.key === "Escape") { event.preventDefault(); close(false); return; }
        if (event.target.closest("input, select, textarea, [contenteditable]")) return;
        if (!selected) return;
        const axes = {ArrowLeft: ["x", -1], ArrowRight: ["x", 1],
            ArrowUp: ["y", -1], ArrowDown: ["y", 1]};
        if (axes[event.key]) {
            event.preventDefault();
            const [field, sign] = axes[event.key], size = dimensions(selected);
            const px = draft.nodes[selected.id][field] / 100 *
                (field === "x" ? size.width : size.height);
            change(field, px + sign * (event.shiftKey ? 10 : 1));
        }
    });
    window.addEventListener("resize", refreshSelection);
    document.addEventListener("scroll", refreshSelection, true);
    window.addEventListener("beforeunload", event => {
        if (editing && JSON.stringify(draft) !== openingDraft) {
            event.preventDefault();
            event.returnValue = "";
        }
    });
    // The ordinary approved page stays in normal flow unless a saved override exists.
    requestAnimationFrame(() => {
        if (!baseline) baseline = captureBaseline();
        if (saved && !free) {
            items.forEach(item => {
                if (!saved.nodes[item.id]) saved.nodes[item.id] = clone(baseline.nodes[item.id]);
            });
            useFree(saved);
            repairDetails(saved);
        }
    });
})();