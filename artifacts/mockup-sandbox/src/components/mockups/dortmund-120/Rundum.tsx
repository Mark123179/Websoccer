import './_group.css';

type StandKey = 'Nord' | 'Süd' | 'Ost' | 'West';

const additions: Record<StandKey, number> = {
  Nord: 9400,
  Süd: 9520,
  Ost: 9820,
  West: 9895,
};

const format = (value: number) => value.toLocaleString('de-DE');

export function Rundum() {
  const illustratedAddition = Object.values(additions).reduce((sum, value) => sum + value, 0);

  return (
    <main
      className="dortmund120"
      style={{
        maxWidth: 1160,
        margin: '0 auto',
        padding: 'clamp(18px, 3vw, 34px)',
        background: '#0b1012',
      }}
    >
      <header
        className="dortmund120__header"
        style={{ maxWidth: 'none', marginBottom: 18 }}
      >
        <div className="dortmund120__eyebrow">STADIONSTUDIE 04 · VERTEILTE NEUORDNUNG</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 24, alignItems: 'end', flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ marginBottom: 8 }}>Rundum statt Anbau.</h1>
            <p className="dortmund120__intro" style={{ maxWidth: 720 }}>
              Eine illustrative Endzustands-Hypothese für Signal Iduna Park:
              zusätzliche Ränge werden über alle vier Seiten verteilt und von
              einem durchgehenden Dachring zusammengefasst.
            </p>
          </div>
          <div style={{ color: '#81918f', fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', paddingBottom: 5 }}>
            Konzept / nicht statisch geprüft
          </div>
        </div>
      </header>

      <section className="dortmund120__concept-grid">
        <div
          className="dortmund120__viewer"
          style={{
            height: 'min(54vw, 492px)',
            minHeight: 430,
            margin: 0,
            borderRadius: 10,
            background: '#101a1c',
          }}
          aria-label="Axonometrische Konzeptstudie mit kontinuierlichem Dachring"
        >
          <svg viewBox="0 0 760 500" role="img" aria-labelledby="concept-title concept-desc" style={{ width: '100%', height: '100%', display: 'block' }}>
            <title id="concept-title">Axonometrische Studie eines rundum erweiterten Signal Iduna Park</title>
            <desc id="concept-desc">Vier neu geordnete Ränge werden durch einen zusammenhängenden Dach- und Eckring verbunden.</desc>
            <defs>
              <linearGradient id="roof" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stopColor="#e5c65d" />
                <stop offset=".55" stopColor="#b58b2c" />
                <stop offset="1" stopColor="#786022" />
              </linearGradient>
              <linearGradient id="stand" x1="0" x2="0" y1="0" y2="1">
                <stop stopColor="#6e7c7c" />
                <stop offset="1" stopColor="#273638" />
              </linearGradient>
              <linearGradient id="newStand" x1="0" x2="0" y1="0" y2="1">
                <stop stopColor="#a99a56" />
                <stop offset="1" stopColor="#4f4e37" />
              </linearGradient>
              <pattern id="seatLines" width="9" height="9" patternUnits="userSpaceOnUse">
                <path d="M0 8L9 8" stroke="#d4c272" strokeOpacity=".42" strokeWidth="1" />
              </pattern>
              <filter id="softShadow" x="-30%" y="-30%" width="160%" height="180%">
                <feGaussianBlur stdDeviation="8" />
              </filter>
            </defs>

            <rect width="760" height="500" fill="#142225" />
            <path d="M88 418 L385 465 L687 375 L389 329 Z" fill="#0b1416" opacity=".8" filter="url(#softShadow)" />
            <path d="M128 358 L382 420 L635 340 L378 287 Z" fill="#152b28" stroke="#3b6252" strokeWidth="2" />
            <path d="M202 349 L380 391 L557 337 L379 302 Z" fill="#2e754d" stroke="#89a276" strokeWidth="1" />
            <path d="M215 344 L379 382 L544 333" fill="none" stroke="#b6ca9c" strokeOpacity=".5" strokeWidth="1" />
            <path d="M278 324 L380 349 L480 319" fill="none" stroke="#b6ca9c" strokeOpacity=".42" strokeWidth="1" />

            {/* existing lower bowl */}
            <path d="M104 290 L185 267 L381 315 L577 255 L652 278 L381 370 Z" fill="url(#stand)" stroke="#9aa9a8" strokeWidth="2" />
            <path d="M104 290 L185 267 L381 315 L577 255 L652 278 L381 370 Z" fill="url(#seatLines)" opacity=".7" />
            <path d="M104 290 L381 370 L652 278" fill="none" stroke="#d0b83f" strokeOpacity=".65" strokeWidth="4" />

            {/* redistributed new ranks, four connected masses */}
            <path d="M182 226 L381 273 L578 214 L605 232 L381 305 L155 249 Z" fill="url(#newStand)" stroke="#eed77e" strokeWidth="2" />
            <path d="M182 226 L381 273 L578 214 L605 232 L381 305 L155 249 Z" fill="url(#seatLines)" opacity=".75" />
            <path d="M182 226 L155 249 L381 305 L605 232 L578 214" fill="none" stroke="#f1dd88" strokeWidth="3" />

            {/* roof ring: four planes, corner connections intentionally legible */}
            <path d="M78 178 L179 145 L380 194 L585 135 L681 164 L606 194 L381 253 L155 201 Z" fill="url(#roof)" fillOpacity=".88" stroke="#f3db79" strokeWidth="3" />
            <path d="M78 178 L155 201 L155 249 L78 220 Z" fill="#806b2d" stroke="#d4b84d" strokeWidth="2" />
            <path d="M585 135 L681 164 L681 211 L606 194 Z" fill="#806b2d" stroke="#d4b84d" strokeWidth="2" />
            <path d="M179 145 L380 194 L380 253 L155 201 Z" fill="#b49b3f" fillOpacity=".36" />
            <path d="M380 194 L585 135 L606 194 L381 253 Z" fill="#b49b3f" fillOpacity=".48" />
            <path d="M155 201 L381 253 L606 194" fill="none" stroke="#fff0a6" strokeOpacity=".9" strokeWidth="2" />
            <path d="M154 201 L110 276 M606 194 L656 263 M179 145 L142 210 M585 135 L629 198" stroke="#d3bd59" strokeWidth="3" />

            {/* four structural corner ties */}
            <g fill="#d7c167" stroke="#574b24" strokeWidth="2">
              <circle cx="155" cy="201" r="7" /><circle cx="606" cy="194" r="7" />
              <circle cx="179" cy="145" r="6" /><circle cx="585" cy="135" r="6" />
            </g>
            <g fontFamily="ui-monospace, SFMono-Regular, monospace" fontSize="12" fill="#e9dfb0">
              <text x="89" y="168">NORD</text>
              <text x="604" y="127">OST</text>
              <text x="87" y="316">WEST</text>
              <text x="575" y="286">SÜD</text>
              <text x="330" y="470" fill="#829391">Spielfeld · schematisch</text>
            </g>
            <g fontFamily="ui-monospace, SFMono-Regular, monospace" fontSize="10" fill="#a6b2ad">
              <text x="92" y="185">neuer Rang + Dachanschluss</text>
              <text x="489" y="113">kontinuierlicher Dachring</text>
              <path d="M585 118 L548 141" stroke="#a6b2ad" strokeWidth="1" />
            </g>
          </svg>
          <div className="dortmund120__viewer-tag" style={{ borderColor: '#8b762c' }}>
            KONZEPTAXONOMETRIE · VERTEILT ÜBER 4 STÄNDE
          </div>
          <div className="dortmund120__viewer-help">
            gelbe Flächen = neue Ränge <span>·</span> Ring = zusammenhängende Dachstrategie
          </div>
        </div>

        <aside style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ border: '1px solid #574a26', borderRadius: 9, padding: 16, background: '#302a19' }}>
            <div style={{ color: '#f1d98f', fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase' }}>Zielbild</div>
            <strong style={{ display: 'block', color: '#f5cb59', fontSize: 39, lineHeight: 1, marginTop: 8 }}>120.000</strong>
             <span style={{ color: '#c4cfcb', fontSize: 12 }}>Illustrativer Endzustand · Plätze</span>
            <div style={{ borderTop: '1px solid #65562c', marginTop: 14, paddingTop: 11, color: '#ddd0a0', fontSize: 12, lineHeight: 1.45 }}>
              +{format(38635)} gegenüber der maßgeblichen Spielkapazität
            </div>
          </div>
          <div style={{ border: '1px solid #344347', borderRadius: 9, padding: 14, background: '#172124', flex: 1 }}>
            <div style={{ color: '#aeb8b6', fontSize: 11, letterSpacing: '.12em', textTransform: 'uppercase', marginBottom: 10 }}>Arbeitsverteilung</div>
            {(['Nord', 'Süd', 'Ost', 'West'] as StandKey[]).map((stand) => (
              <div
                key={stand}
                style={{
                  display: 'flex', justifyContent: 'space-between', width: '100%', margin: '0 0 7px',
                  padding: '8px 9px', borderRadius: 5, textAlign: 'left',
                  border: '1px solid #8e792d',
                  background: '#3b351e', color: '#d9e0d9',
                  font: 'inherit', fontSize: 12,
                }}
              >
                <span>● {stand}</span>
                <span style={{ color: '#f2d36d', fontVariantNumeric: 'tabular-nums' }}>+{format(additions[stand])}</span>
              </div>
            ))}
            <div style={{ marginTop: 14, paddingTop: 11, borderTop: '1px solid #344347', color: '#9eadaa', fontSize: 11, lineHeight: 1.4 }}>
              Beispielverteilung, keine feste Quote oder geprüfte Seitenbilanz.
              <strong style={{ display: 'block', color: '#f5cb59', marginTop: 5 }}>Σ Beispiel: +{format(illustratedAddition)}</strong>
            </div>
          </div>
          <div style={{ fontSize: 10, color: '#73817f', lineHeight: 1.4 }}>
            Süd / Nord sind hier Diagrammbegriffe. Die Originalansicht ist nicht georeferenziert registriert.
          </div>
        </aside>
      </section>

      <section className="dortmund120__source-grid">
        <div style={{ position: 'relative', minHeight: 142, overflow: 'hidden', border: '1px solid #344347', borderRadius: 9, background: '#142023' }}>
          <img
            src="/__mockup/images/dortmund-120/original-2d.webp"
            alt="Originale CPU-Projektion der extrahierten Signal-Iduna-Park-Meshes"
            style={{ width: '100%', height: '100%', minHeight: 142, objectFit: 'cover', opacity: .62, filter: 'saturate(.7)' }}
          />
          <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, #142023e8 0%, #14202399 48%, transparent)' }} />
          <div style={{ position: 'absolute', left: 15, top: 14, maxWidth: 270 }}>
            <div style={{ color: '#f0c453', fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase' }}>Quelle / Bestand</div>
            <strong style={{ display: 'block', marginTop: 6, color: '#f5f4ed', fontSize: 17 }}>Originalgeometrie als Referenz</strong>
            <p style={{ margin: '5px 0 0', color: '#bac6c2', fontSize: 11, lineHeight: 1.4 }}>CPU-Render aus den extrahierten Unity-Meshes. Keine erfundene Bestandsform.</p>
          </div>
        </div>
        <div className="dortmund120__disclaimer" style={{ margin: 0, borderRadius: 9, borderLeftWidth: 3, padding: '14px 16px', fontSize: 12 }}>
          <strong>Lesart der Studie</strong>
          <p>
            <b>81.365</b> ist die Spielkapazität. <b>71.659</b> bezeichnet ausschließlich
            Unity-Stuhlpositionen. Für das Zielbild fehlen rechnerisch <b>38.635</b> Plätze.
            Die vier Werte oben sind eine illustrative Verteilungs-Hypothese — eine exakte
            Sitzaufteilung je Seite ist <b>nicht festgelegt</b>.
          </p>
          <p style={{ marginTop: 6, color: '#aeb8b6' }}>
            Kontinuierliche Ecken und Dachanschlüsse zeigen eine mögliche strukturelle Strategie;
            Statik, Sichtlinien, Fluchtwege und Genehmigung sind nicht geprüft.
          </p>
        </div>
      </section>
    </main>
  );
}
