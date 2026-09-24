import './_group.css';
import { StadiumScene } from './_OriginalScene';

export function SuedMaximum() {
  return <main className="dortmund120">
    <header className="dortmund120__header">
      <div className="dortmund120__eyebrow">SIGNAL IDUNA PARK · HYPOTHESE SÜD-MAXIMUM</div>
      <h1>Ein Stadion. Ein extremer Gedanke.</h1>
      <p className="dortmund120__intro">Das Zielbild konzentriert den rechnerischen Ausbau auf eine sehr hohe, asymmetrische Tribüne an der angenommenen +x-Seite. Deren Außenwand reicht bis zum Boden; „Süd“ ist ein Diagrammbegriff, nicht georeferenziert.</p>
    </header>
    <section className="dortmund120__capacity dortmund120__calculation"><div><span className="dortmund120__capacity-label">Heute</span><strong>81.365</strong><span className="dortmund120__capacity-unit">Spielkapazität</span></div><span>+</span><div><span className="dortmund120__capacity-label">Konzeptdifferenz</span><strong>38.635</strong><span className="dortmund120__capacity-unit">nicht gemessene Plätze</span></div><span>=</span><div><span className="dortmund120__capacity-label">Zielbild</span><strong>120.000</strong><span className="dortmund120__capacity-unit">keine genehmigte Kapazität</span></div></section>
    <section className="dortmund120__viewer" aria-label="Drehbares Süd-Maximum-3D-Modell">
      <StadiumScene variant="sued" />
      <div className="dortmund120__viewer-tag">ORIGINAL · ABGELEITET · NEU ANGENOMMEN</div>
      <div className="dortmund120__viewer-help">Ziehen: drehen <span>·</span> Mausrad: zoomen <span>·</span> Dach transparent zur Einsicht</div>
    </section>
    <section className="dortmund120__strategy-grid"><div className="dortmund120__panel"><div className="dortmund120__label">Asymmetrische Strategie</div><h2>Ein hoher Rang auf geschlossenem Unterbau.</h2><p>Die Original-Dach- und Pylonmeshes samt UVs werden an der +x-Seite als Konzept verformt, nicht nur ausgeblendet. Dachflächen sind zur Einsicht transparent. Neue Rangflächen, durchgehende Außenwand, Stirnwände und Anschlüsse verwenden vereinfachte Materialien nach Original-Kategorien; sie sind <b>keine</b> Originalbauteile. Die Quelldatei bleibt unverändert.</p></div><div className="dortmund120__panel"><div className="dortmund120__label">Offene Prüfpunkte</div><ul><li>Statik, Lastabtragung und Fundamente unbekannt</li><li>Sichtlinien und Fluchtwege ungeprüft</li><li>Keine Sitzzählung, Original-Shader oder Zulassung behauptet</li></ul></div></section>
    <aside className="dortmund120__disclaimer"><strong>Einordnung vor jeder Entscheidung</strong><p><b>81.365 + 38.635 = 120.000</b> ist eine konzeptionelle Rechenzeile, keine physische Kapazitätsmessung. Die 71.659 Positionen stammen aus der Quelldatei. Die gemessene kleine Original-Verformungsprobe endet bei etwa <b>85.833 modellierten Sitzen</b>; dieser Großbau geht weit darüber hinaus und ist nicht geometrisch als 120.000er Stadion belegt. Die +x-/Süd-Zuordnung ist eine Annahme.</p></aside>
  </main>;
}