(() => {
    const root = document.querySelector(".match-preview-page");
    if (!root) return;

    // The calendar can wrap to a second row on narrower screens.
    // Keep all three panels together and below its actual logical height.
    const header = root.querySelector(".ws-game-header");
    if (header) {
        const alignPanels = () => root.style.setProperty("--mp-header-bottom",
            `${header.offsetTop + header.offsetHeight}px`);
        alignPanels();
        new ResizeObserver(alignPanels).observe(header);
        window.addEventListener("resize", alignPanels);
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