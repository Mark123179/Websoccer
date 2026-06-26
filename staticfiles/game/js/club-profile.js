(() => {
    const cards = document.querySelectorAll('[data-trophy-card]');

    cards.forEach((card) => {
        const pages = Array.from(card.querySelectorAll('[data-trophy-page]'));
        const pageButtons = Array.from(card.querySelectorAll('[data-trophy-index]'));
        const prevButton = card.querySelector('[data-trophy-prev]');
        const nextButton = card.querySelector('[data-trophy-next]');
        let activeIndex = 0;

        const render = () => {
            pages.forEach((page, index) => {
                page.classList.toggle('is-active', index === activeIndex);
            });
            pageButtons.forEach((button, index) => {
                button.classList.toggle('is-active', index === activeIndex);
            });
            if (prevButton) {
                prevButton.disabled = activeIndex === 0;
            }
            if (nextButton) {
                nextButton.disabled = activeIndex >= pages.length - 1;
            }
        };

        pageButtons.forEach((button, index) => {
            button.addEventListener('click', () => {
                activeIndex = index;
                render();
            });
        });

        if (prevButton) {
            prevButton.addEventListener('click', () => {
                activeIndex = Math.max(0, activeIndex - 1);
                render();
            });
        }

        if (nextButton) {
            nextButton.addEventListener('click', () => {
                activeIndex = Math.min(pages.length - 1, activeIndex + 1);
                render();
            });
        }

        render();
    });
})();
