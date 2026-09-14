import './_group.css';

export function Current() {
  return (
    <main className="manager-timeline-tickets" aria-label="Manager-Karriere-Timeline">
      <div className="manager-timeline-tickets__crop">
        <h1 className="manager-timeline-tickets__heading">Karriere Timeline</h1>

        <section className="manager-timeline-tickets__track" aria-label="Timeline-Ausschnitt">
          <div className="manager-timeline-tickets__axis" aria-hidden="true" />
          <div className="manager-timeline-tickets__stem" aria-hidden="true" />
          <div className="manager-timeline-tickets__dot" aria-hidden="true" />

          <article className="manager-timeline-tickets__card">
            <div className="manager-timeline-tickets__card-top">
              <span className="manager-timeline-tickets__chip-icon" aria-hidden="true">
                <svg
                  viewBox="0 0 12 12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                >
                  <path d="M3 2h6v3a3 3 0 0 1-6 0V2Z" />
                  <path d="M6 7v2M4 10h4" />
                </svg>
              </span>
              <span className="manager-timeline-tickets__category">FINALE</span>
              <time className="manager-timeline-tickets__date" dateTime="2026-05-24">
                24.05.2026
              </time>
            </div>

            <strong className="manager-timeline-tickets__title">
              DFB-Pokal Finale
              <span className="manager-timeline-tickets__result">3:2</span>
            </strong>
            <p className="manager-timeline-tickets__body">Borussia Dortmund · Berlin</p>
          </article>

          <span className="manager-timeline-tickets__tick">24.05.2026</span>
        </section>

        <p className="manager-timeline-tickets__context-label">Farbcode · Finale</p>
      </div>
    </main>
  );
}