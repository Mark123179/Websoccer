import './_group.css';
import { OriginalScene } from './_OriginalScene';

export function Current() {
  return (
    <main className="dortmund120">
      <header className="dortmund120__header">
        <div className="dortmund120__eyebrow">Signal Iduna Park · Originalgeometrie</div>
        <h1>Dortmund, aus Originaldaten.</h1>
        <p className="dortmund120__intro">
          Das Stadion verwendet die extrahierten Unity-Originalmeshes. Die
          Umgebung ist ein vereinfachter 3D-Auszug aus OSM und einem groben Höhenraster.
        </p>
      </header>

      <section className="dortmund120__capacity" aria-label="Spielkapazität">
        <span className="dortmund120__capacity-label">Spielkapazität</span>
        <strong>81.365</strong>
        <span className="dortmund120__capacity-unit">Plätze</span>
      </section>

      <section className="dortmund120__viewer" aria-label="Originale 3D-Stadionansicht">
        <OriginalScene />
        <div className="dortmund120__viewer-tag">Originalmeshes · nur ansehen</div>
        <div className="dortmund120__viewer-help">
          Ziehen: drehen <span>·</span> Mausrad: zoomen <span>·</span> Dach ein-/ausblenden
        </div>
      </section>

      <aside className="dortmund120__disclaimer">
        <strong>Wichtige Einordnung</strong>
        <p>
          Die Quelldatei der Unity-Stuhlpositionen enthält <b>71.659 Positionen</b>.
          Das ist eine Modell-/Quelldateizählung und ausdrücklich <b>keine
          Geschäftskapazität</b>. Die angezeigte Spielkapazität beträgt <b>81.365</b>.
        </p>
      </aside>
    </main>
  );
}