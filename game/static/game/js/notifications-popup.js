(() => {
    "use strict";
    const trigger = document.getElementById("notifications-trigger");
    const popup = document.getElementById("notifications-popup");
    if (!trigger || !popup) return;
    const badge = document.getElementById("notifications-badge");
    const content = popup.querySelector(".notifications-popup-content");
    const list = popup.querySelector(".notifications-popup-list");
    const status = popup.querySelector(".notifications-popup-status");
    const retry = popup.querySelector(".notifications-popup-retry");
    let requestNumber = 0;

    // The game stage is transformed and clipped. Position in viewport space.
    document.body.appendChild(popup);
    function position() {
        if (popup.hidden) return;
        const anchor = trigger.getBoundingClientRect();
        const margin = 12;
        const spaceBelow = window.innerHeight - anchor.bottom - 8 - margin;
        const spaceAbove = anchor.top - 8 - margin;
        const openAbove = spaceBelow < 160 && spaceAbove > spaceBelow;
        const available = openAbove ? spaceAbove : spaceBelow;
        popup.style.maxHeight = `${Math.max(100, Math.min(520, available))}px`;
        const width = popup.getBoundingClientRect().width;
        popup.style.left = `${Math.max(margin, Math.min(anchor.left, window.innerWidth - width - margin))}px`;
        const height = popup.getBoundingClientRect().height;
        const top = openAbove ? anchor.top - height - 8 : anchor.bottom + 8;
        popup.style.top = `${top}px`;
    }

    function setCount(count) {
        badge.textContent = String(count);
        badge.hidden = count === 0;
        badge.setAttribute("aria-label", `${count} ungelesene Benachrichtigungen`);
        trigger.setAttribute("aria-label", count
            ? `Benachrichtigungen, ${count} ungelesen` : "Benachrichtigungen");
    }

    function messageNode(item) {
        const row = document.createElement("li");
        row.className = "notifications-popup-item";
        if (item.is_new) row.classList.add("is-new");
        const message = document.createElement(item.url ? "a" : "div");
        message.className = "notifications-popup-message";
        if (item.url) {
            const url = new URL(item.url, window.location.href);
            if (url.origin === window.location.origin && ["http:", "https:"].includes(url.protocol)) {
                message.href = url.href;
            }
        }
        const title = document.createElement("strong");
        title.textContent = item.title;
        message.appendChild(title);
        if (item.body) {
            const body = document.createElement("p");
            body.textContent = item.body;
            message.appendChild(body);
        }
        const date = document.createElement("time");
        date.dateTime = item.created_at;
        date.textContent = item.date_label;
        message.appendChild(date);
        row.appendChild(message);
        return row;
    }

    async function load() {
        const number = ++requestNumber;
        content.setAttribute("aria-busy", "true");
        list.hidden = true;
        retry.hidden = true;
        status.hidden = false;
        status.textContent = "Benachrichtigungen werden geladen …";
        position();
        try {
            const response = await fetch(trigger.dataset.openUrl, {
                method: "POST", credentials: "same-origin",
                headers: {"X-CSRFToken": trigger.dataset.csrf, "Accept": "application/json"},
                cache: "no-store",
            });
            if (!response.ok || response.redirected) throw new Error("request failed");
            const data = await response.json();
            if (!Array.isArray(data.items) || !Number.isInteger(data.unread_count) || data.unread_count < 0) {
                throw new Error("invalid response");
            }
            if (number !== requestNumber) return;
            list.replaceChildren(...data.items.map(messageNode));
            setCount(data.unread_count);
            list.hidden = !data.items.length;
            status.hidden = !!data.items.length;
            status.textContent = "Noch keine Benachrichtigungen.";
        } catch {
            if (number !== requestNumber) return;
            status.hidden = false;
            status.textContent = "Benachrichtigungen konnten nicht geladen werden.";
            retry.hidden = false;
        } finally {
            if (number === requestNumber) {
                content.setAttribute("aria-busy", "false");
                position();
            }
        }
    }

    function close(restoreFocus = false) {
        popup.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
        if (restoreFocus) trigger.focus();
    }
    function toggle(event) {
        event.preventDefault();
        if (!popup.hidden) {
            close(true);
            return;
        }
        popup.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        position();
        popup.focus({preventScroll: true});
        load();
    }
    setCount(Number.parseInt(badge.textContent, 10) || 0);
    trigger.addEventListener("click", toggle);
    trigger.addEventListener("keydown", event => {
        if (event.key === " ") toggle(event);
    });
    popup.querySelector(".notifications-popup-close").addEventListener("click", () => close(true));
    retry.addEventListener("click", load);
    document.addEventListener("pointerdown", event => {
        if (!popup.hidden && !popup.contains(event.target) && !trigger.contains(event.target)) close();
    });
    document.addEventListener("keydown", event => {
        if (popup.hidden) return;
        if (event.key === "Escape") {
            event.preventDefault();
            close(true);
        }
    });
    document.addEventListener("focusin", event => {
        if (!popup.hidden && !popup.contains(event.target) && !trigger.contains(event.target)) close();
    });
    window.addEventListener("resize", position);
    document.addEventListener("scroll", position, true);
})();