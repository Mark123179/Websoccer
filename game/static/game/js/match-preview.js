(() => {
    const root = document.querySelector(".match-preview-page");
    if (!root) return;

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