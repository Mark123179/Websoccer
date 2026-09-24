import './_group.css';
import { StadiumScene } from './_OriginalScene';

export function SuedMaximum() {
  return <main className="dortmund120">
    <header className="dortmund120__header">
      <div className="dortmund120__eyebrow">SIGNAL IDUNA PARK · HYPOTHESE SÜD-MAXIMUM</div>
      <h1>Ein Stadion. Ein extremer Gedanke.</h1>
      <p className="dortmund120__intro">Die gesamte rechnerische Differenz sitzt in einer massiv asymmetrischen, sehr hohen neuen Tribüne an der angenommenen +x-Seite. Süd ist hier ein Diagrammbegriff und nicht georeferenziert.</p>
    </header>
    <section className="dortmund120__capacity dortmund120__calculation"><div><span className="dortmund120__capacity-label">Heute</span><strong>81.365</strong><span className="dortmund120__capacity-unit">Spielkapazität</span></div><span>+</span><div><span className="dortmund120__capacity-label">Konzeptdifferenz</span><strong>38.635</strong><span className="dortmund120__capacity-unit">nicht gemessene Plätze</span></div><span>=</span><div><span className="dortmund120__capacity-label">Zielbild</span><strong>120.000</strong><span className="dortmund120__capacity-unit">keine genehmigte Kapazität</span></div></section>
    <section className="dortmund120__viewer" aria-label="Drehbares Süd-Maximum-3D-Modell">
      <StadiumScene variant="sued" />
      <div className="dortmund120__viewer-tag">ORIGINAL + KONZEPTBAUTEILE · +X-SEITE</div>
      <div className="dortmund120__viewer-help">Ziehen: drehen <span>·</span> Mausrad: zoomen <span>·</span> Roof-corner zeigt die neue Dachkante</div>
    </section>
    <section className="dortmund120__strategy-grid"><div className="dortmund120__panel"><div className="dortmund120__label">Asymmetrische Strategie</div><h2>Ein neuer hoher Rang, eigenes Tragbild.</h2><p>Die angenommene +x-Tribüne, das ansteigende Dach und die Außenstützen sind zusammenhängende Konzeptgeometrie. Die Original-Dachhaut und Pylone sind in dieser Vergleichsansicht ausgeblendet; die Originaldatei bleibt unverändert.</p></div><div className="dortmund120__panel"><div className="dortmund120__label">Offene Prüfpunkte</div><ul><li>Statik und Fundamente unbekannt</li><li>Sichtlinien und Fluchtwege ungeprüft</li><li>Keine Sitzzählung oder Zulassung behauptet</li></ul></div></section>
    <aside className="dortmund120__disclaimer"><strong>Einordnung vor jeder Entscheidung</strong><p><b>81.365 + 38.635 = 120.000</b> ist eine konzeptionelle Rechenzeile, keine physische Kapazitätsmessung. Die 71.659 Positionen stammen aus der Quelldatei. Das +x/Süd-Modell ist eine Annahme; es behauptet weder Geografie noch bauliche Machbarkeit oder Genehmigung.</p></aside>
  </main>;
}