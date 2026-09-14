import './classic.css';

export function Classic() {
  return (
    <main className="classic-ticket" aria-label="Manager-Karriere-Timeline">
      <div className="classic-ticket__wash" />
      <div className="classic-ticket__crop">
        <p className="classic-ticket__eyebrow">MANAGER KARRIERE · SPIELTAG 26</p>
        <h1 className="classic-ticket__heading">Karriere Timeline</h1>

        <section className="classic-ticket__track" aria-label="Timeline-Ausschnitt">
          <div className="classic-ticket__axis" aria-hidden="true" />
          <div className="classic-ticket__stem" aria-hidden="true" />
          <div className="classic-ticket__dot" aria-hidden="true" />

          <article className="classic-ticket__card" aria-label="Borussia Dortmund 3 zu 2 FC Bayern München">
            <div className="classic-ticket__image" />
            <div className="classic-ticket__club-band" />
            <div className="classic-ticket__body">
              <header className="classic-ticket__topline">
                <span className="classic-ticket__mark" aria-hidden="true">D</span>
                <span className="classic-ticket__label">DFB-POKAL · FINALE</span>
                <time dateTime="2026-05-24">24.05.26</time>
              </header>

              <p className="classic-ticket__stadium">OLYMPIASTADION BERLIN</p>
              <div className="classic-ticket__scoreline">
                <div className="classic-ticket__team classic-ticket__team--home">
                  <span className="classic-ticket__crest">BVB</span>
                  <span title="Borussia Dortmund">Borussia<br />Dortmund</span>
                </div>
                <strong className="classic-ticket__score" aria-label="3 zu 2">3:2</strong>
                <div className="classic-ticket__team classic-ticket__team--away">
                  <span className="classic-ticket__crest classic-ticket__crest--red">FCB</span>
                  <span title="FC Bayern München">FC Bayern<br />München</span>
                </div>
              </div>
              <div className="classic-ticket__footer">
                <span>ANPFIFF 20:00</span>
                <span>SIEG · FINALE</span>
              </div>
            </div>

            <aside className="classic-ticket__stub" aria-label="Ticketabriss">
              <span className="classic-ticket__stub-caption">EINLASS</span>
              <span className="classic-ticket__stub-seat">BLOCK 15<br />REIHE 08</span>
              <svg className="classic-ticket__barcode" viewBox="0 0 44 72" aria-label="Ticketcode" role="img">
                <path d="M2 0v72M5 0v72M9 0v72M11 0v72M16 0v72M18 0v72M22 0v72M27 0v72M29 0v72M34 0v72M37 0v72M42 0v72" />
              </svg>
              <span className="classic-ticket__code">BVB·052426·032</span>
            </aside>
          </article>

          <time className="classic-ticket__tick" dateTime="2026-05-24">24.05.2026</time>
        </section>
        <p className="classic-ticket__context-label">Farbcode · Finale · Heimspiel</p>
      </div>
    </main>
  );
}