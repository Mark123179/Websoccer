import './_group.css';
import './Rundum.css';
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
    <section className="rundum120__raster" aria-label="Leseschlüssel für das Rangraster">
      <div className="rundum120__raster-art" aria-hidden="true">
        <div className="rundum120__raster-row"><i/><i/><i/><i/><i/><i/><i/><i/></div>
        <div className="rundum120__raster-row rundum120__raster-row--dark"><i/><i/><i/><i/><i/><i/><i/><i/></div>
        <div className="rundum120__raster-row"><i/><i/><i/><i/><i/><i/><i/><i/></div>
        <div className="rundum120__raster-aisle" />
        <div className="rundum120__raster-row rundum120__raster-row--dark"><i/><i/><i/><i/><i/><i/><i/><i/></div>
      </div>
      <div>
        <div className="dortmund120__label">Leseschlüssel · neue Rangflächen</div>
        <h2>Wie der Bestand gelesen werden kann.</h2>
        <p>Ja — die neue Rangfläche wird bereits als wiederholtes Raster mit einzelnen Sitzmarkierungen und ausgesparten Gängen gezeigt. Der Unterschied: Der Originalbestand kommt aus texturierten Unity-Crowdflächen; für den Ausbau gibt es kein belegtes Originalmesh für zusätzliche Plätze. Deshalb sind die neuen Reihen neutral grau und ausdrücklich schematisch.</p>
      </div>
      <div className="rundum120__raster-key"><span><b className="rundum120__swatch rundum120__swatch--seat"/>neue Sitz-/Stehmarkierung</span><span><b className="rundum120__swatch rundum120__swatch--aisle"/>Gang / Erschließung</span><span><b className="rundum120__swatch rundum120__swatch--source"/>Originalbestand</span></div>
    </section>
    <section className="dortmund120__source-grid">
      <div className="dortmund120__panel"><div className="dortmund120__label">Räumliche Strategie</div><h2>Vier Seiten. Geschlossene Hülle.</h2><p>Die neuen Rangflächen steigen an vier Seiten an und treffen sich in gemeinsamen Eckpunkten. Außenwände und durchgehende Sockel schließen den Raum bis zum Boden. Graue Sitzmarkierungen und freie Gänge zeigen ein mögliches Rangraster, ohne Plätze zu zählen.</p></div>
      <aside className="dortmund120__disclaimer"><strong>Geometrie-Legende</strong><p><b>Original</b> = Unity-Meshes samt verfügbaren UVs und vier exportierten Texturen. <b>Abgeleitet</b> = aus Originaldreiecken gedehntes Dach, Träger und Pylone; die Dachhaut ist zur Einsicht als transparenter Schnitt gerendert. <b>Neu angenommen</b> = neutrale graue Rangflächen, schematische Sitzmarkierungen, Sockel, Außenwände und Anschlüsse. Kein originaler Unity-Shader, nachgewiesener Sitzplan oder geprüftes Tragwerk.</p></aside>
    </section>
    <aside className="dortmund120__disclaimer"><strong>Warum 120.000 hier nicht exakt nachweisbar sind</strong><p><b>81.365</b> ist die Spielkapazität, <b>71.659</b> sind Quell-Stuhlpositionen und <b>38.635</b> ist nur die Differenz zum Zielbild. Die Originaldaten liefern weder zusätzliche Rangtiefe noch ein vollständiges neues Sitzmesh. Außerdem würden Treppen, Gänge, Sichtlinien, Fluchtwege, Deckenhöhen und die tragende Struktur Platz wegnehmen. Mit den gemessenen Originalmaßen reicht die kleine Ausbauprobe nur bis etwa <b>85.833 modellierte Sitze</b>. Für 120.000 müsste ein vollständig neuer, größerer Baukörper vermessen und geplant werden — das wäre ein neues Konzept, kein exaktes Abbild aus dem vorhandenen Stadionmesh.</p></aside>
  </main>;
}