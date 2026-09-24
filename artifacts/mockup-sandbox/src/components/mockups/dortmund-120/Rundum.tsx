import './_group.css';
import { StadiumScene } from './_OriginalScene';

export function Rundum() {
  return <main className="dortmund120">
    <header className="dortmund120__header">
      <div className="dortmund120__eyebrow">STADIONSTUDIE 04 · DERIVED GEOMETRY</div>
      <h1>Rundum statt Anbau.</h1>
      <p className="dortmund120__intro">Eine vierseitige Ausbau-Hypothese: neue obere Ränge, geschlossene Eckübergänge, Außenstützen und ein eigener Dachring sitzen sichtbar auf dem vermessenen Originalmaßstab.</p>
    </header>
    <section className="dortmund120__capacity"><span className="dortmund120__capacity-label">Konzeptziel</span><strong>120.000</strong><span className="dortmund120__capacity-unit">illustrative Plätze · nicht gemessen</span></section>
    <section className="dortmund120__viewer" aria-label="Drehbares Rundum-3D-Modell">
      <StadiumScene variant="rundum" />
      <div className="dortmund120__viewer-tag">ORIGINAL + DERIVED · VIER SEITEN</div>
      <div className="dortmund120__viewer-help">Ziehen: drehen <span>·</span> Mausrad: zoomen <span>·</span> Presets: Kamera</div>
    </section>
    <section className="dortmund120__source-grid">
      <div className="dortmund120__panel"><div className="dortmund120__label">Räumliche Strategie</div><h2>Vier Seiten. Ein neuer oberer Ring.</h2><p>Die neuen Rangflächen steigen an allen vier Seiten an. Eckflächen, ein neuer Dachring und Außenstützen bilden eine gemeinsame, hypothetische Hülle. Eine Kapazität je Tribüne ist nicht aus dem Modell ableitbar.</p></div>
      <aside className="dortmund120__disclaimer"><strong>Geometrie-Legende</strong><p><b>Original</b> = geladene Unity-Meshes und Texturen. <b>Neu angenommen</b> = browserseitige obere Ränge, Ecken, Dach und Stützen. Die ursprüngliche Dachhaut und Pylone sind nur in dieser Konzeptansicht ausgeblendet; Originaldaten bleiben unverändert.</p></aside>
    </section>
    <aside className="dortmund120__disclaimer"><strong>Einordnung</strong><p><b>81.365</b> ist die Spielkapazität. <b>71.659</b> sind Quell-Stuhlpositionen. <b>38.635</b> ist nur die rechnerische Differenz zum Konzeptziel. Statik, Sichtlinien, Fluchtwege, Material, Fundamente und Genehmigung sind nicht geprüft.</p></aside>
  </main>;
}