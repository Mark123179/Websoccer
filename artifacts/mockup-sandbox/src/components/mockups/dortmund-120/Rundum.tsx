import './_group.css';
import { StadiumScene } from './_OriginalScene';

export function Rundum() {
  return <main className="dortmund120">
    <header className="dortmund120__header">
      <div className="dortmund120__eyebrow">STADIONSTUDIE 04 · DERIVED GEOMETRY</div>
      <h1>Rundum statt Anbau.</h1>
      <p className="dortmund120__intro">Vierseitige Ausbau-Hypothese mit einem neuen oberen Ring und einer geschlossenen Außenhülle. Das Dach und seine Träger sind aus der exportierten Originalgeometrie abgeleitet; der größere Unterbau ist eine neue Annahme.</p>
    </header>
    <section className="dortmund120__capacity"><span className="dortmund120__capacity-label">Konzeptziel</span><strong>120.000</strong><span className="dortmund120__capacity-unit">illustrative Plätze · nicht gemessen</span></section>
    <section className="dortmund120__viewer" aria-label="Drehbares Rundum-3D-Modell">
      <StadiumScene variant="rundum" />
      <div className="dortmund120__viewer-tag">ORIGINAL · ABGELEITET · NEU ANGENOMMEN</div>
      <div className="dortmund120__viewer-help">Ziehen: drehen <span>·</span> Mausrad: zoomen <span>·</span> Presets: Kamera</div>
    </section>
    <section className="dortmund120__source-grid">
      <div className="dortmund120__panel"><div className="dortmund120__label">Räumliche Strategie</div><h2>Vier Seiten. Geschlossene Hülle.</h2><p>Die neuen Rangflächen steigen an vier Seiten an und treffen sich in gemeinsamen Eckpunkten. Außenwände und durchgehende Sockel schließen den Raum bis zum Boden; Beton-, Sitz- und Dachmaterial orientieren sich an der exportierten Vorschau. Eine Kapazität je Tribüne ist daraus nicht ableitbar.</p></div>
      <aside className="dortmund120__disclaimer"><strong>Geometrie-Legende</strong><p><b>Original</b> = Unity-Meshes samt verfügbaren UVs und vier exportierten Texturen. <b>Abgeleitet</b> = aus Originaldreiecken gedehntes Dach, Träger und Pylone; die Dachhaut ist zur Einsicht als transparenter Schnitt gerendert. <b>Neu angenommen</b> = Rangflächen, Sockel, Außenwände und Anschlüsse mit Farben aus Original-Materialkategorien. Kein originaler Unity-Shader oder nachgewiesenes Tragwerk.</p></aside>
    </section>
    <aside className="dortmund120__disclaimer"><strong>Einordnung</strong><p><b>81.365</b> ist die Spielkapazität. <b>71.659</b> sind Quell-Stuhlpositionen. <b>38.635</b> ist nur die rechnerische Differenz zum Konzeptziel. Die gemessene kleine Ausbauprobe endet bei etwa <b>85.833 modellierten Sitzen</b>; diese große Hülle belegt keine 120.000 Plätze. Statik, Sichtlinien, Fluchtwege, Material und Genehmigung sind ungeprüft.</p></aside>
  </main>;
}