import './_group.css';
import './Current.css';
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

      <section className="dortmund120__site-detail" aria-label="Detaillierte Umgebungskarte">
        <div className="dortmund120__site-detail-head">
          <div>
            <div className="dortmund120__label">Lagebild · Dortmund Westfalenpark</div>
            <h2>Das Stadion im gewachsenen Umfeld.</h2>
          </div>
          <span className="dortmund120__site-badge">OSM · schematisch verdichtet</span>
        </div>
        <div className="dortmund120__map">
          <svg viewBox="0 0 960 420" role="img" aria-label="Detaillierte schematische Draufsicht mit Stadion, Straßen, Gebäuden und Grünflächen">
            <defs>
              <pattern id="dortmund-grid" width="28" height="28" patternUnits="userSpaceOnUse">
                <path d="M 28 0 L 0 0 0 28" fill="none" stroke="#174347" strokeWidth="1" opacity=".42" />
              </pattern>
              <filter id="dortmund-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="8" stdDeviation="7" floodColor="#02090a" floodOpacity=".7" />
              </filter>
            </defs>
            <rect width="960" height="420" fill="#071416" />
            <rect width="960" height="420" fill="url(#dortmund-grid)" />
            <path className="dortmund120__map-road" d="M-20 55 C150 85 230 70 360 112 S695 155 980 108" />
            <path className="dortmund120__map-road dortmund120__map-road--minor" d="M-20 354 C180 294 252 334 390 300 S710 285 985 345" />
            <path className="dortmund120__map-road" d="M124 -10 C165 90 154 171 198 221 S275 325 300 440" />
            <path className="dortmund120__map-road dortmund120__map-road--minor" d="M781 -10 C737 78 748 141 704 212 S667 330 681 440" />
            <path className="dortmund120__map-park" d="M28 125 L155 102 206 152 170 254 34 265Z" />
            <path className="dortmund120__map-park" d="M769 74 L941 48 956 206 835 235 774 194Z" />
            <path className="dortmund120__map-park" d="M735 298 L915 272 947 406 700 420Z" />
            <g className="dortmund120__map-buildings">
              <path d="M42 312h94v39H42zM166 286h78v52h-78zM264 64h96v44h-96zM778 249h114v41H778zM835 304h78v52h-78zM622 30h70v52h-70zM72 40h69v38H72z" />
              <path d="M383 22h72v49h-72zM472 56h105v38H472zM74 176h66v54H74zM822 105h92v42h-92z" />
            </g>
            <g className="dortmund120__map-tree-dots">
              <circle cx="85" cy="126" r="5"/><circle cx="119" cy="110" r="4"/><circle cx="159" cy="140" r="6"/>
              <circle cx="873" cy="82" r="5"/><circle cx="912" cy="116" r="4"/><circle cx="843" cy="183" r="5"/>
              <circle cx="760" cy="335" r="4"/><circle cx="804" cy="366" r="6"/><circle cx="879" cy="334" r="4"/>
              <circle cx="219" cy="373" r="5"/><circle cx="259" cy="389" r="4"/><circle cx="326" cy="359" r="5"/>
            </g>
            <g className="dortmund120__map-stadium" filter="url(#dortmund-shadow)" transform="translate(318 74)">
              <rect x="0" y="0" width="324" height="270" rx="62" />
              <rect x="20" y="20" width="284" height="230" rx="47" />
              <rect x="41" y="41" width="242" height="188" rx="33" />
              <rect className="dortmund120__map-bowl" x="62" y="57" width="200" height="156" rx="18" />
              <rect className="dortmund120__map-pitch" x="91" y="78" width="142" height="114" rx="2" />
              <path className="dortmund120__map-pitch-lines" d="M162 78v114M91 135h142M102 78v30h22v-30M200 78v30h22v-30M102 192v-30h22v30M200 192v-30h22v30" />
              <circle className="dortmund120__map-pitch-lines" cx="162" cy="135" r="17" />
              <path className="dortmund120__map-ring" d="M7 74h310M7 196h310M75 7v256M249 7v256" />
            </g>
            <g className="dortmund120__map-labels">
              <text x="328" y="368">SIGNAL IDUNA PARK</text>
              <text x="50" y="291">WESTFALENPARK</text>
              <text x="794" y="232">WESTFALENHALLEN</text>
              <text x="720" y="391">Strobelallee</text>
            </g>
          </svg>
          <div className="dortmund120__map-legend"><span><i className="is-stadium" />Originalstadion</span><span><i className="is-road" />Straßen / Wege</span><span><i className="is-park" />Grünraum</span></div>
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