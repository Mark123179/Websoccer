import './Retro.css';

export function Retro() {
  return (
    <main className="retro-timeline" aria-label="Manager-Karriere-Timeline">
      <div className="retro-timeline__crop">
        <div className="retro-timeline__paper-grain" aria-hidden="true" />
        <p className="retro-timeline__eyebrow">KARRIERE · SPIELTAGARCHIV</p>
        <h1 className="retro-timeline__heading">Karriere Timeline</h1>

        <section className="retro-timeline__track" aria-label="Timeline-Ausschnitt">
          <div className="retro-timeline__axis" aria-hidden="true" />
          <div className="retro-timeline__stem" aria-hidden="true" />
          <div className="retro-timeline__dot" aria-hidden="true" />

          <article className="retro-ticket">
            <div className="retro-ticket__photo" aria-hidden="true" />
            <div className="retro-ticket__ink-wash" aria-hidden="true" />
            <div className="retro-ticket__club-band" aria-hidden="true">
              <span>EINTRACHT</span>
              <span>FRANKFURT</span>
            </div>

            <div className="retro-ticket__main">
              <div className="retro-ticket__masthead">
                <span className="retro-ticket__mark">EFC</span>
                <span className="retro-ticket__competition">UEFA EUROPA LEAGUE</span>
                <span className="retro-ticket__edition">26</span>
              </div>
              <div className="retro-ticket__rule" />
              <div className="retro-ticket__match">
                <div className="retro-ticket__team">
                  <span className="retro-ticket__crest retro-ticket__crest--home">SGE</span>
                  <span className="retro-ticket__team-name">Eintracht<br />Frankfurt</span>
                </div>
                <div className="retro-ticket__score" aria-label="Endstand 2 zu 2">
                  <strong>2:2</strong>
                  <small>ENDSTAND</small>
                </div>
                <div className="retro-ticket__team retro-ticket__team--away">
                  <span className="retro-ticket__crest retro-ticket__crest--away">BVB</span>
                  <span className="retro-ticket__team-name">Borussia<br />Dortmund</span>
                </div>
              </div>
              <div className="retro-ticket__venue">
                <span>DEUTSCHE BANK PARK</span>
                <span>FRANKFURT AM MAIN</span>
              </div>
              <div className="retro-ticket__date">
                <span>DONNERSTAG</span>
                <b>14.05.2026</b>
                <span>21:00 UHR</span>
              </div>
              <div className="retro-ticket__stamp">MATCH<br />ARCHIVE</div>
            </div>

            <aside className="retro-ticket__stub" aria-label="Abreißbarer Ticketabschnitt">
              <span className="retro-ticket__stub-label">EINLASS</span>
              <strong>2:2</strong>
              <span className="retro-ticket__stub-date">14 MAI<br />2026</span>
              <div className="retro-ticket__barcode" aria-label="Ticketcode ETL 051426">
                {Array.from({ length: 18 }, (_, index) => <i key={index} style={{ width: `${index % 4 === 0 ? 3 : 1}px` }} />)}
              </div>
              <small>ETL · 051426</small>
              <span className="retro-ticket__serial">NO. 004782</span>
            </aside>
          </article>

          <span className="retro-timeline__tick">14.05.2026</span>
        </section>

        <p className="retro-timeline__context-label">Papierbeleg · Europa League</p>
      </div>
    </main>
  );
}