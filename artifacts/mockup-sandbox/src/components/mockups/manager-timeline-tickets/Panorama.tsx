import './Panorama.css';

export function Panorama() {
  return (
    <main className="panorama-ticket" aria-label="Manager-Karriere-Timeline">
      <div className="panorama-ticket__crop">
        <h1 className="panorama-ticket__heading">Karriere Timeline</h1>
        <section className="panorama-ticket__track" aria-label="Timeline-Ausschnitt">
          <div className="panorama-ticket__axis" aria-hidden="true" />
          <div className="panorama-ticket__stem" aria-hidden="true" />
          <div className="panorama-ticket__dot" aria-hidden="true" />
          <article className="panorama-ticket__card" aria-label="FC Bayern München 4 zu 1 Bayer 04 Leverkusen">
            <div className="panorama-ticket__main">
              <div className="panorama-ticket__meta">
                <span className="panorama-ticket__mark" aria-hidden="true" />
                <span>Heimspiel</span>
                <time className="panorama-ticket__date" dateTime="2026-03-08">08.03.2026</time>
              </div>
              <p className="panorama-ticket__competition">Bundesliga</p>
              <p className="panorama-ticket__fixture">Spieltag 25 · München</p>
              <div className="panorama-ticket__scoreline">
                <span className="panorama-ticket__team">FC Bayern München</span>
                <strong className="panorama-ticket__score">4:1</strong>
                <span className="panorama-ticket__team">Bayer 04 Leverkusen</span>
              </div>
              <p className="panorama-ticket__venue">ALLIANZ ARENA · 75.024 ZUSCHAUER</p>
            </div>
            <aside className="panorama-ticket__stub" aria-label="Abrissstreifen">
              <span className="panorama-ticket__stub-label">Souvenir</span>
              <span className="panorama-ticket__barcode" aria-hidden="true" />
              <span className="panorama-ticket__code">MUC 080326</span>
            </aside>
          </article>
          <span className="panorama-ticket__tick">08.03.2026</span>
        </section>
        <p className="panorama-ticket__context-label">Panorama · Heimspiel</p>
      </div>
    </main>
  );
}