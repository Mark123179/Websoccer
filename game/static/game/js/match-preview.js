(() => {
    const root = document.querySelector(".match-preview-page");
    if (!root) return;

    root.querySelectorAll("[data-stadium-tab]").forEach((tab, _index, tabs) => {
        if (_index !== 0) tab.tabIndex = -1;
        tab.addEventListener("click", () => activateTab(tab));
        tab.addEventListener("keydown", event => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const current = Array.from(tabs).indexOf(tab);
            const targetIndex = event.key === "Home" ? 0
                : event.key === "End" ? tabs.length - 1
                    : (current + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
            tabs[targetIndex].focus();
            activateTab(tabs[targetIndex]);
        });
    });

    function activateTab(selected) {
        const selectedView = root.querySelector(`#${CSS.escape(selected.getAttribute("aria-controls"))}`);
        if (!selectedView) return;
        root.querySelectorAll("[data-stadium-tab]").forEach(tab => {
            const isSelected = tab === selected;
            tab.setAttribute("aria-selected", String(isSelected));
            tab.tabIndex = isSelected ? 0 : -1;
        });
        root.querySelectorAll("[data-stadium-view]").forEach(view => {
            const isSelected = view === selectedView;
            view.hidden = !isSelected;
            view.classList.toggle("is-active", isSelected);
        });
    }

    root.querySelectorAll("img[data-fallback-image]").forEach(image => {
        image.addEventListener("error", () => {
            image.dataset.imageFailed = "true";
            const fallback = image.nextElementSibling;
            if (fallback?.matches("[data-image-fallback]")) {
                fallback.hidden = false;
                fallback.setAttribute("role", "img");
                fallback.setAttribute("aria-label", image.alt || "Bild nicht verfügbar");
            }
            image.setAttribute("aria-hidden", "true");
        }, { once: true });

        const markLoaded = () => {
            const fallback = image.nextElementSibling;
            if (fallback?.matches("[data-image-fallback]")) fallback.hidden = true;
        };
        image.addEventListener("load", markLoaded, { once: true });
        if (image.complete) {
            if (image.naturalWidth) markLoaded();
            else image.dispatchEvent(new Event("error"));
        }
    });
})();