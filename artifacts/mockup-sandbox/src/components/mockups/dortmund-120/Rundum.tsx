import { useMemo, useState } from 'react';
import './_group.css';
import './Rundum.css';
import { StadiumScene } from './_OriginalScene';

type Stand = 'Nord' | 'Ost' | 'Süd' | 'West';
type View = 'plan' | 'model';
type Preset = 1000 | 5000 | 10000 | 20000;

const standMeta: Record<Stand, { x: number; y: number; w: number; h: number; color: string }> = {
  Nord: { x: 110, y: 30, w: 300, h: 78, color: '#c9b44b' },
  Ost: { x: 388, y: 110, w: 78, h: 230, color: '#a69d80' },
  Süd: { x: 110, y: 342, w: 300, h: 78, color: '#b39a4b' },
  West: { x: 54, y: 110, w: 78, h: 230, color: '#929b98' },
};

export function Rundum() {
  const [view, setView] = useState<View>('plan');
  const [selected, setSelected] = useState<Stand>('Nord');
  const [depth, setDepth] = useState(3);
  const [rise, setRise] = useState(18);
  const [preset, setPreset] = useState<Preset>(5000);
  const [saved, setSaved] = useState(false);

  const total = useMemo(() => preset * 4, [preset]);
  const active = standMeta[selected];
  const rows = Math.max(4, Math.round(depth * 2.4));

  return <main className="dortmund120 rundum-editor">
    <header className="dortmund120__header rundum-editor__header">
      <div>
        <div className="dortmund120__eyebrow">STADIONSTUDIE 04 · AUSBAUEDITOR</div>
        <h1>Rundum planen.</h1>
        <p className="dortmund120__intro">2D-Rangflächen bearbeiten, Ausbaugrößen je Tribüne simulieren und das Ergebnis direkt im drehbaren 3D-Modell prüfen.</p>
      </div>
      <div className="rundum-editor__status"><i /> Entwurf · lokal gespeichert</div>
    </header>

    <section className="rundum-editor__toolbar" aria-label="Ansicht und Aktionen">
      <div className="rundum-editor__tabs">
        <button className={view === 'plan' ? 'is-active' : ''} onClick={() => setView('plan')}>2D bearbeiten</button>
        <button className={view === 'model' ? 'is-active' : ''} onClick={() => setView('model')}>3D prüfen</button>
      </div>
      <div className="rundum-editor__toolbar-actions">
        <span className="rundum-editor__save-state">{saved ? 'Gespeichert' : 'Ungespeicherte Änderung'}</span>
        <button className="rundum-editor__save" onClick={() => setSaved(true)}>Entwurf speichern</button>
      </div>
    </section>

    {view === 'plan' ? <section className="rundum-editor__workspace">
      <div className="rundum-editor__canvas-card">
        <div className="rundum-editor__canvas-head">
          <div><span className="dortmund120__label">Grundriss · Rangbearbeitung</span><h2>Tribüne auswählen und aufbauen</h2></div>
          <span className="rundum-editor__scale">1 Rasterfeld = 5 m</span>
        </div>
        <div className="rundum-editor__plan-wrap">
          <svg className="rundum-editor__plan" viewBox="0 0 520 450" role="img" aria-label="Bearbeitbarer Grundriss des Stadions">
            <defs><pattern id="editor-grid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="#315053" strokeWidth=".6" /></pattern></defs>
            <rect width="520" height="450" fill="url(#editor-grid)" />
            <rect x="30" y="20" width="460" height="410" rx="18" fill="none" stroke="#526563" strokeWidth="1" strokeDasharray="4 7" />
            <rect x="136" y="108" width="252" height="234" rx="32" fill="#132326" stroke="#d7b849" strokeWidth="2" />
            {(['Nord', 'Ost', 'Süd', 'West'] as Stand[]).map((name) => {
              const s = standMeta[name]; const isSelected = name === selected;
              return <g key={name} onClick={() => setSelected(name)} className="rundum-editor__stand" style={{ cursor: 'pointer' }}>
                <rect {...s} rx="8" fill={isSelected ? s.color : '#687674'} opacity={isSelected ? .94 : .72} stroke={isSelected ? '#f5df82' : '#a0aaa4'} strokeWidth={isSelected ? 3 : 1} />
                <text x={s.x + s.w / 2} y={s.y + s.h / 2 + 5} textAnchor="middle">{name.toUpperCase()}</text>
                {isSelected && <circle cx={s.x + s.w - 14} cy={s.y + 14} r="6" fill="#172124" stroke="#f5df82" />}
              </g>;
            })}
            <rect x="164" y="138" width="196" height="174" rx="5" fill="#246443" stroke="#76a47c" strokeWidth="1" />
            <path d="M262 138v174M164 225h196M180 138v38h28v-38M316 138v38h28v-38M180 312v-38h28v38M316 312v-38h28v38" fill="none" stroke="#b5d2a5" strokeWidth="1" opacity=".65" />
            <circle cx="262" cy="225" r="24" fill="none" stroke="#b5d2a5" opacity=".65" />
            <text x="262" y="232" textAnchor="middle" className="rundum-editor__pitch-label">SPIELFELD</text>
          </svg>
          <div className="rundum-editor__plan-legend"><span><i className="is-selected" />Ausgewählte Tribüne</span><span><i className="is-existing" />Bestand</span><span><i className="is-pitch" />Spielfeld</span></div>
        </div>
      </div>

      <aside className="rundum-editor__inspector">
        <div className="dortmund120__label">Tribünen-Inspector</div>
        <h2>{selected}-Tribüne</h2>
        <p className="rundum-editor__muted">Die Rangfläche bleibt schematisch. Maße verändern das Konzeptbild, nicht eine genehmigte Kapazität.</p>
        <div className="rundum-editor__stand-list">{(['Nord', 'Ost', 'Süd', 'West'] as Stand[]).map((name) => <button key={name} className={selected === name ? 'is-active' : ''} onClick={() => setSelected(name)}><span className="rundum-editor__stand-dot" style={{ background: standMeta[name].color }} />{name}<b>{preset.toLocaleString('de-DE')}</b></button>)}</div>
        <label className="rundum-editor__field"><span>Rangtiefe <b>{depth} Reihen</b></span><input type="range" min="1" max="8" value={depth} onChange={(event) => { setDepth(Number(event.target.value)); setSaved(false); }} /></label>
        <label className="rundum-editor__field"><span>Anstieg <b>{rise}°</b></span><input type="range" min="8" max="32" value={rise} onChange={(event) => { setRise(Number(event.target.value)); setSaved(false); }} /></label>
        <div className="rundum-editor__metric"><span>Simulierte Reihen</span><strong>{rows}</strong><small>visuelle Näherung</small></div>
        <div className="rundum-editor__hint">Tipp: Ziehe die 3D-Ansicht später mit der Maus, um Dach, Innenraum und Außenhülle aus jedem Winkel zu prüfen.</div>
      </aside>
    </section> : <section className="dortmund120__viewer rundum-editor__model" aria-label="Drehbares Ausbau-3D-Modell">
      <StadiumScene variant="rundum" />
      <div className="dortmund120__viewer-tag">AUSBAU · {total.toLocaleString('de-DE')} SIMULIERTE PLÄTZE</div>
      <div className="dortmund120__viewer-help">Ziehen: drehen <span>·</span> Mausrad: zoomen <span>·</span> Dachschalter: mit / ohne Dach</div>
    </section>}

    <section className="rundum-editor__simulation">
      <div><span className="dortmund120__label">Ausbau-Simulation · {selected}-Tribüne</span><h2>Wie viel soll auf diesen Rang?</h2><p>Wähle eine Konzeptstufe. Sie gilt pro Tribüne und kann anschließend im 2D-Grundriss verfeinert werden.</p></div>
      <div className="rundum-editor__preset-grid">{([1000, 5000, 10000, 20000] as Preset[]).map((value) => <button key={value} className={preset === value ? 'is-active' : ''} onClick={() => { setPreset(value); setSaved(false); }}><strong>{value.toLocaleString('de-DE')}</strong><span>pro Tribüne</span></button>)}</div>
      <div className="rundum-editor__total"><span>Vierseitiges Zielbild</span><strong>{total.toLocaleString('de-DE')}</strong><small>illustrative Plätze · nicht gemessen</small></div>
    </section>
    <aside className="dortmund120__disclaimer"><strong>Konzeptstatus</strong><p>Die editorischen Rangflächen und Simulationswerte sind visuelle Ausbauvarianten. Sie ersetzen keine Sitzplanung, Statik, Sichtlinien-, Fluchtweg- oder Genehmigungsprüfung. Originalbestand und neue neutrale Rangflächen bleiben im 3D-Modell unterscheidbar.</p></aside>
  </main>;
}