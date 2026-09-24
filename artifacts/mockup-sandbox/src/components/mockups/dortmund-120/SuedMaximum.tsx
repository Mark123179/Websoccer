import { useState, type CSSProperties } from 'react';
import './_group.css';

const originalImage = '/__mockup/images/dortmund-120/original-2d.webp';

type ViewMode = 'concept' | 'reference';

export function SuedMaximum() {
  const [viewMode, setViewMode] = useState<ViewMode>('concept');

  return (
    <main className="dortmund120" style={{ maxWidth: 1100, margin: '0 auto' }}>
      <header className="dortmund120__header" style={{ position: 'relative' }}>
        <div className="dortmund120__eyebrow">Signal Iduna Park · Hypothese SÜD-MAXIMUM</div>
        <h1 style={{ maxWidth: 820 }}>Ein Stadion. Ein extremer Gedanke.</h1>
        <p className="dortmund120__intro" style={{ maxWidth: 780 }}>
          Was wäre, wenn die gesamte Kapazitätsdifferenz in einer neu gedachten Südtribüne
          konzentriert würde? Keine Bauzusage — ein architektonischer Stresstest für die
          Spielentscheidung.
        </p>
        <div style={{
          display: 'flex', gap: 6, width: 'max-content', marginTop: 16,
          padding: 4, border: '1px solid #3b4a4b', borderRadius: 8, background: '#121c1e',
        }}>
          <button type="button" onClick={() => setViewMode('concept')} style={buttonStyle(viewMode === 'concept')}>
            Konzept
          </button>
          <button type="button" onClick={() => setViewMode('reference')} style={buttonStyle(viewMode === 'reference')}>
            Original
          </button>
        </div>
      </header>

      <section className="dortmund120__capacity dortmund120__calculation" aria-label="Kapazitätsrechnung">
        <div>
          <span className="dortmund120__capacity-label">Spielkapazität heute</span>
          <strong style={{ display: 'block', fontSize: 38 }}>81.365</strong>
          <span className="dortmund120__capacity-unit">Plätze</span>
        </div>
        <span style={{ color: '#8d9a97', fontSize: 24 }}>+</span>
        <div>
          <span className="dortmund120__capacity-label">Süd-Maximum</span>
          <strong style={{ display: 'block', fontSize: 38, color: '#e4b844' }}>38.635</strong>
          <span className="dortmund120__capacity-unit">neue Plätze · ausschließlich Süd</span>
        </div>
        <span style={{ color: '#8d9a97', fontSize: 24 }}>=</span>
        <div style={{ borderLeft: '1px solid #625329', paddingLeft: 16 }}>
          <span className="dortmund120__capacity-label">Konzeptziel · Gesamt</span>
          <strong style={{ display: 'block', fontSize: 43, color: '#f5cb59' }}>120.000</strong>
          <span className="dortmund120__capacity-unit">keine genehmigte Kapazität</span>
        </div>
      </section>

      <section className="dortmund120__viewer" aria-label="Süd-Maximum Architekturstudie" style={{ height: 'min(58vw, 520px)', minHeight: 405 }}>
        {viewMode === 'reference' ? (
          <div className="dortmund120__fallback" style={{ background: '#131e20' }}>
            <img src={originalImage} alt="CPU-Render des originalen Signal Iduna Park Meshes" />
            <p>Original-CPU-Render als visuelle Referenz</p>
            <small>Extrahierte Unity-Meshes · keine georeferenzierte Nordausrichtung</small>
          </div>
        ) : (
          <div style={{ position: 'absolute', inset: 0 }}>
            <img
              src={originalImage}
              alt="Originalmesh als zurückhaltender Unterbau der Konzeptstudie"
              style={{ position: 'absolute', inset: '8% 11% 5%', width: '78%', height: '83%', objectFit: 'contain', opacity: .20, filter: 'grayscale(1) contrast(.8)' }}
            />
            <svg viewBox="0 0 1000 530" role="img" aria-label="Diagrammatische Massing-Studie mit überhöhter Südtribüne" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
              <defs>
                <linearGradient id="southMass" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0" stopColor="#f0c453" stopOpacity=".88" />
                  <stop offset=".56" stopColor="#b77d2b" stopOpacity=".90" />
                  <stop offset="1" stopColor="#5a4028" stopOpacity=".94" />
                </linearGradient>
                <linearGradient id="oldBowl" x1="0" x2="0" y1="0" y2="1">
                  <stop stopColor="#60716d" stopOpacity=".72" />
                  <stop offset="1" stopColor="#273638" stopOpacity=".82" />
                </linearGradient>
                <pattern id="ribs" width="16" height="16" patternUnits="userSpaceOnUse">
                  <path d="M0 16L16 0" stroke="#f5d77c" strokeOpacity=".28" strokeWidth="2" />
                </pattern>
              </defs>
              <ellipse cx="500" cy="300" rx="330" ry="125" fill="#0c1517" stroke="#778783" strokeWidth="2" />
              <ellipse cx="500" cy="300" rx="195" ry="74" fill="#192527" stroke="#899591" strokeWidth="2" />
              <path d="M305 298 Q500 225 695 298 L664 342 Q500 285 336 342Z" fill="#a3aaa0" opacity=".62" />
              <path d="M300 298 Q500 220 700 298 L684 348 Q500 292 316 348Z" fill="none" stroke="#c2cbc2" strokeWidth="8" opacity=".68" />
              <path d="M170 306 Q500 412 830 306 L790 404 Q500 478 210 404Z" fill="url(#southMass)" stroke="#f5d77c" strokeWidth="3" />
              <path d="M190 332 Q500 424 810 332 L781 391 Q500 455 219 391Z" fill="url(#ribs)" opacity=".9" />
              <path d="M190 306 Q500 402 810 306" fill="none" stroke="#ffecaa" strokeWidth="3" strokeDasharray="8 7" />
              <path d="M192 300 Q500 403 808 300" fill="none" stroke="#f0c453" strokeWidth="5" opacity=".86" />
              <path d="M168 305 Q500 164 832 305" fill="none" stroke="#e4b844" strokeWidth="6" opacity=".82" />
              <path d="M190 305 Q500 146 810 305" fill="none" stroke="#a9833b" strokeWidth="2" strokeDasharray="11 8" />
              {[245, 320, 395, 470, 545, 620, 695, 770].map((x) => <path key={x} d={`M${x} ${x < 500 ? 250 - (x - 245) * .11 : 250 - (x - 545) * .11} L${x - 10} 420`} stroke="#f3cc5e" strokeWidth="2" opacity=".58" />)}
              <path d="M163 305 L116 262 M837 305 L884 262" stroke="#dfbb5b" strokeWidth="4" />
              <path d="M160 303 L120 230 M840 303 L880 230" stroke="#73817e" strokeWidth="3" />
              <circle cx="167" cy="305" r="6" fill="#f5cb59" /><circle cx="833" cy="305" r="6" fill="#f5cb59" />
              <g fontFamily="system-ui, sans-serif">
                <rect x="64" y="56" width="255" height="65" rx="5" fill="#10191ddd" stroke="#52615e" />
                <text x="82" y="80" fill="#f5d77c" fontSize="13" fontWeight="700" letterSpacing="1.5">SÜD-MAXIMUM</text>
                <text x="82" y="101" fill="#d9e0db" fontSize="12">38.635 Plätze · ein neuer Rang</text>
                <path d="M300 120 L340 230" stroke="#f0c453" strokeWidth="1.5" strokeDasharray="4 4" />
                <rect x="686" y="58" width="245" height="65" rx="5" fill="#10191ddd" stroke="#52615e" />
                <text x="704" y="81" fill="#cad4cf" fontSize="12" fontWeight="700">NEUES DACH / TRAGWERK</text>
                <text x="704" y="102" fill="#aeb8b6" fontSize="11">eigene Abstützung, Ecken geschlossen</text>
                <path d="M744 124 L715 193" stroke="#cad4cf" strokeWidth="1.5" strokeDasharray="4 4" />
                <text x="500" y="498" textAnchor="middle" fill="#9eaaa5" fontSize="11" letterSpacing="1.2">SCHEMATISCHE MASSING-STUDIE · SÜD NUR DIAGRAMMATISCH</text>
              </g>
            </svg>
          </div>
        )}
        <div className="dortmund120__viewer-tag">{viewMode === 'concept' ? 'Konzept / nicht statisch geprüft' : 'Originalmeshes · nur Referenz'}</div>
        <div className="dortmund120__viewer-help">Südposition diagrammatisch <span>·</span> nicht georeferenziert</div>
      </section>

      <section className="dortmund120__strategy-grid">
        <div style={panelStyle}>
          <div style={labelStyle}>STRATEGIE</div>
          <h2 style={headingStyle}>Nicht rundum. Radikal einseitig.</h2>
          <p style={copyStyle}>
            Der gesamte Zuwachs sitzt in einer überhöhten, asymmetrischen Südtribüne. Ihre neue
            Dachkante läuft in geschlossenen Eckübergängen in den Bestand — ein vollständig neu
            gedachtes System, keine Verlängerung des bisherigen Dachs oder der alten Pylone.
          </p>
        </div>
        <div style={{ ...panelStyle, borderColor: '#664f24' }}>
          <div style={labelStyle}>OFFENE PRÜFPUNKTE</div>
          <ul style={{ ...copyStyle, margin: '10px 0 0', paddingLeft: 18 }}>
            <li>Fluchtwege und Sichtlinien unbekannt</li>
            <li>Statik, Fundamente, Material nicht geprüft</li>
            <li>Keine per-Stand-Zulassung behauptet</li>
          </ul>
        </div>
      </section>

      <aside className="dortmund120__disclaimer">
        <strong>Einordnung vor jeder Entscheidung</strong>
        <p>
          <b>81.365</b> ist die maßgebliche Spielkapazität. <b>71.659</b> bezeichnet ausschließlich
          Unity-Stuhlpositionen der Quelldatei. Diese Studie skizziert <b>38.635</b> zusätzliche
          Plätze — exakt 81.365 + 38.635 = <b>120.000</b>. Das Süd-Maximum ist ein extremer,
          spekulativer Stresstest und keine Aussage zur physischen Machbarkeit, Genehmigung oder
          geographischen Ausrichtung. Die Süd-Bezeichnung ist diagrammatisch.
        </p>
      </aside>
    </main>
  );
}

const buttonStyle = (active: boolean): CSSProperties => ({
  border: active ? '1px solid #e4b844' : '1px solid transparent',
  borderRadius: 5,
  background: active ? '#493b20' : 'transparent',
  color: active ? '#f5d77c' : '#9eaaa5',
  padding: '7px 10px',
  fontSize: 11,
  fontWeight: 700,
  cursor: 'pointer',
});

const panelStyle: CSSProperties = {
  border: '1px solid #344347',
  borderRadius: 8,
  background: '#172124',
  padding: '16px 18px',
};
const labelStyle: CSSProperties = { color: '#e7bd55', fontSize: 11, fontWeight: 800, letterSpacing: '.15em' };
const headingStyle: CSSProperties = { margin: '8px 0 4px', color: '#f1f2eb', fontSize: 22, letterSpacing: '-.03em' };
const copyStyle: CSSProperties = { margin: 0, color: '#b8c2be', fontSize: 13, lineHeight: 1.55 };