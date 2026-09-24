import './_group.css';
import { OriginalScene } from './_OriginalScene';

export function Current() {
  return (
    <main className="dortmund120">
      <header className="dortmund120__header">
        <div className="dortmund120__eyebrow">Signal Iduna Park · Originalgeometrie + Rekonstruktion</div>
        <h1>Dortmund, aus Originaldaten ergänzt.</h1>
        <p className="dortmund120__intro">
          Die Bestandsansicht zeigt einen Auszug der Unity-Meshes mit vereinfachten Materialien
          und nur vier repräsentativen Texturen – kein Unity-Originalrender. Die echten
          NoDraw-Außenwandflächen sind in dieser Vorschau an den Farbton der Rekonstruktion
          angeglichen; ihr exportierter Materialwert bleibt unverändert. Das ist keine
          belegte Unity-Originalfarbe, und die exakte Shaderwirkung bleibt ungeklärt.
          Die offene Gegenseite wird
          durch eine schlichte, separat gezeichnete Rekonstruktion geschlossen;
          diese Außenwand ist nicht durch die Unity-Datei belegt.
          Die Umgebung ist ein vereinfachter 3D-Auszug aus OSM und einem groben Höhenraster.
        </p>
      </header>

      <section className="dortmund120__capacity" aria-label="Spielkapazität">
        <span className="dortmund120__capacity-label">Spielkapazität</span>
        <strong>81.365</strong>
        <span className="dortmund120__capacity-unit">Plätze</span>
      </section>

      <section className="dortmund120__viewer" aria-label="3D-Vorschau des Unity-Mesh-Auszugs">
        <OriginalScene />
        <div className="dortmund120__viewer-tag">Unity-Mesh-Auszug + rekonstruierte Gegenseite (kein Unity-Original) · nur ansehen</div>
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