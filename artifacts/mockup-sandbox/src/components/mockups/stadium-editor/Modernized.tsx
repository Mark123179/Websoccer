import { useEffect, useState } from 'react';
import './Modernized.css';

type PreviewState =
  | { status: 'loading' }
  | { status: 'ready'; document: string }
  | { status: 'error' };

const BASELINE_URL = '/__mockup/stadium-editor/current.html';
const MODERN_STYLE_URL = '/__mockup/stadium-editor/modernized.css';

function transformBaseline(markup: string, styles: string) {
  const parsed = new DOMParser().parseFromString(markup, 'text/html');
  const style = parsed.createElement('style');
  style.id = 'stadium-editor-modernized';
  style.textContent = styles;
  parsed.head.append(style);

  const toolbar = parsed.querySelector('.editor-toolbar');
  const backLink = parsed.querySelector('.editor-back');
  if (toolbar && backLink) {
    const identity = parsed.createElement('div');
    identity.className = 'modern-identity';
    identity.innerHTML = '<span class="modern-identity__eyebrow">STADIONVERWALTUNG</span><strong>Sitzplatz-Design</strong>';
    backLink.after(identity);

    const previewState = parsed.createElement('span');
    previewState.className = 'modern-preview-state';
    previewState.innerHTML = '<i aria-hidden="true"></i> Vorschau · nur lokal';
    toolbar.append(previewState);
  }

  const unavailableView3d = parsed.getElementById('btn3d');
  unavailableView3d?.setAttribute('disabled', '');
  unavailableView3d?.setAttribute('aria-describedby', 'modern-3d-unavailable');
  unavailableView3d?.setAttribute('title', '3D ist in dieser Vorschau nicht verfügbar.');

  const stage = parsed.querySelector('#stage');
  if (stage) {
    const stageNote = parsed.createElement('div');
    stageNote.className = 'modern-stage-note';
    stageNote.id = 'modern-3d-unavailable';
    stageNote.setAttribute('aria-label', '3D-Vorschau nicht verfügbar');
    stageNote.innerHTML = '<span class="modern-stage-note__mark" aria-hidden="true">2D</span><span>3D-Prüfung nur im Spiel verfügbar</span>';
    stage.append(stageNote);
  }

  const grassState = parsed.querySelector('#grassPreviewState');
  if (grassState) grassState.textContent = 'Rasenauswahl ist in dieser Vorschau nicht aktiv.';

  return `<!doctype html>${parsed.documentElement.outerHTML}`;
}

export function Modernized() {
  const [attempt, setAttempt] = useState(0);
  const [preview, setPreview] = useState<PreviewState>({ status: 'loading' });

  useEffect(() => {
    let active = true;
    setPreview({ status: 'loading' });

    Promise.all([
      fetch(BASELINE_URL).then((response) => {
        if (!response.ok) throw new Error('Baseline could not be loaded');
        return response.text();
      }),
      fetch(MODERN_STYLE_URL).then((response) => {
        if (!response.ok) throw new Error('Editor styles could not be loaded');
        return response.text();
      }),
    ])
      .then(([markup, styles]) => {
        if (active) setPreview({ status: 'ready', document: transformBaseline(markup, styles) });
      })
      .catch(() => {
        if (active) setPreview({ status: 'error' });
      });

    return () => {
      active = false;
    };
  }, [attempt]);

  if (preview.status === 'loading') {
    return (
      <main className="stadium-modern-shell" aria-label="Stadion-Editor wird geladen">
        <div className="stadium-modern-loading">
          <div className="stadium-modern-loading__top" />
          <div className="stadium-modern-loading__side" />
          <div className="stadium-modern-loading__field" />
        </div>
      </main>
    );
  }

  if (preview.status === 'error') {
    return (
      <main className="stadium-modern-shell">
        <div className="stadium-modern-error" role="alert">
          <span className="stadium-modern-error__eyebrow">STADION-EDITOR</span>
          <strong>Vorschau konnte nicht geladen werden.</strong>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>Erneut versuchen</button>
        </div>
      </main>
    );
  }

  return (
    <main className="stadium-modern-shell">
      <iframe
        title="Modernisierte Stadion-Sitzplatzgestaltung"
        srcDoc={preview.document}
        loading="eager"
      />
    </main>
  );
}
