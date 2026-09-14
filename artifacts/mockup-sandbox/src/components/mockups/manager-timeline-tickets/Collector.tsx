import './collector.css';

export function Collector() {
  return (
    <main className="collector" aria-label="Manager-Karriere-Timeline, kompakte Eintrittskarte">
      <div className="collector__crop">
        <header className="collector__header">
          <span className="collector__eyebrow">KARRIERE · SPIELTAG</span>
          <h1>Karriere Timeline</h1>
          <span className="collector__rule" aria-hidden="true" />
        </header>

        <section className="collector__track" aria-label="Timeline-Ausschnitt">
          <div className="collector__axis" aria-hidden="true" />
          <div className="collector__stem" aria-hidden="true" />
          <div className="collector__dot" aria-hidden="true" />

          <article className="collector__ticket" aria-label="Bayer 04 Leverkusen 1 zu 0 RB Leipzig">
            <div className="collector__hero">
              <div className="collector__photo" />
              <div className="collector__shade" />
              <div className="collector__clubband">
                <span>BUNDESLIGA</span>
                <span>15. JUN. 2026</span>
              </div>
              <div className="collector__competition">
                <span>BayArena · Leverkusen</span>
              </div>
              <div className="collector__score" aria-label="Bayer 04 Leverkusen 1, RB Leipzig 0">
                <div className="collector__team collector__team--home">
                  <span className="collector__crest collector__crest--home" aria-hidden="true">B04</span>
                  <span>Bayer 04<br />Leverkusen</span>
                </div>
                <strong className="collector__score-number">1 : 0</strong>
                <div className="collector__team collector__team--away">
                  <span>RB<br />Leipzig</span>
                  <span className="collector__crest collector__crest--away" aria-hidden="true">RB</span>
                </div>
              </div>
              <div className="collector__venue">
                <span>AMTSSPRACH · VEREIN</span>
                <span>1. SPIEL</span>
              </div>
            </div>

            <div className="collector__tear" aria-hidden="true">
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>

            <aside className="collector__stub" aria-label="Ticketabriss mit Seriennummer">
              <div className="collector__stub-top">
                <span>VEREIN</span>
                <strong>CL·26</strong>
              </div>
              <span className="collector__stub-label">EINTRITT</span>
              <div className="collector__barcode" aria-label="Ticketcode 04CL260530">
                <i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i />
              </div>
              <code>04 · 1:0 · 260615</code>
            </aside>
          </article>

          <time className="collector__tick" dateTime="2026-05-30">30.05.2026</time>
        </section>

        <p className="collector__context-label">ENDSPIEL · SAMMLERPASS · 001 / 026</p>
      </div>
    </main>
  );
}