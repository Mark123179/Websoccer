import './collector.css';

export function Collector() {
  return (
    <main className="collector" aria-label="Manager-Karriere-Timeline, Sammlerticket">
      <div className="collector__crop">
        <header className="collector__header">
          <span className="collector__eyebrow">KARRIERE · ARCHIV 08</span>
          <h1>Karriere Timeline</h1>
          <span className="collector__rule" aria-hidden="true" />
        </header>

        <section className="collector__track" aria-label="Timeline-Ausschnitt">
          <div className="collector__axis" aria-hidden="true" />
          <div className="collector__stem" aria-hidden="true" />
          <div className="collector__dot" aria-hidden="true" />

          <article className="collector__ticket" aria-label="Champions League Finale, Bayer 04 Leverkusen 1 zu 0 RB Leipzig">
            <div className="collector__hero">
              <div className="collector__photo" />
              <div className="collector__shade" />
              <div className="collector__clubband">
                <span>BAYER 04</span>
                <span>WERKSELF</span>
              </div>
              <div className="collector__serial">PASS · 001 / 026</div>
              <div className="collector__competition">
                <span className="collector__cupmark" aria-hidden="true">✦</span>
                <span>UEFA CHAMPIONS LEAGUE</span>
                <strong>FINALE</strong>
              </div>
              <div className="collector__score" aria-label="Bayer 04 Leverkusen 1, RB Leipzig 0">
                <div className="collector__team collector__team--home">
                  <b>1</b>
                  <span>Bayer 04<br />Leverkusen</span>
                </div>
                <span className="collector__versus">—</span>
                <div className="collector__team collector__team--away">
                  <span>RB<br />Leipzig</span>
                  <b>0</b>
                </div>
              </div>
              <div className="collector__venue">
                <span>FINALE · MÜNCHEN</span>
                <span>30.05.2026</span>
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
                <span>FINALPASS</span>
                <strong>CL·26</strong>
              </div>
              <div className="collector__stub-star" aria-hidden="true">✦</div>
              <span className="collector__stub-label">SAMMLER-EDITION</span>
              <div className="collector__barcode" aria-label="Ticketcode 04CL260530">
                <i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i />
              </div>
              <code>04 · CL · 260530</code>
              <span className="collector__stub-no">NO. 000184</span>
            </aside>
          </article>

          <time className="collector__tick" dateTime="2026-05-30">30.05.2026</time>
        </section>

        <p className="collector__context-label">ENDSPIEL · SAMMLERPASS · 001 / 026</p>
      </div>
    </main>
  );
}