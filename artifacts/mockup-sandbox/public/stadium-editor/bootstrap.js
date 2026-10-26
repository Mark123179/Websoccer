(function bootstrapStadiumEditorMockup() {
  'use strict';

  const editor = window.STADIUM_EDITOR = {
    geometryUrl: './geometry.json',
    designUrl: './design.json',
    liveSceneUrl: './live-scene.json',
    saveUrl: './save-design',
    maxPreviewCapacity: 150000,
    isAdmin: false,
    dortmundScene: false,
    unityScene: false,
    sourceSeats: false,
    seatModes: true,
  };
  const fixtureFiles = new Map([
    [editor.geometryUrl, './geometry.json'],
    [editor.designUrl, './design.json'],
    [editor.liveSceneUrl, './live-scene.json'],
  ]);
  const nativeFetch = window.fetch.bind(window);
  const pathFor = (input) => new URL(
    typeof input === 'string' ? input : input.url,
    document.baseURI,
  ).pathname;

  window.fetch = async (input, init = {}) => {
    const path = pathFor(input);
    const method = (init.method || (typeof input !== 'string' && input.method) || 'GET')
      .toUpperCase();
    const savePath = new URL(editor.saveUrl, document.baseURI).pathname;
    if (path === savePath && method === 'POST') {
      window.__stadiumEditorLastDraft = init.body || null;
      return new Response(JSON.stringify({ ok: true, updated_at: 'mockup-local' }), {
        headers: { 'Content-Type': 'application/json' },
      });
    }

    for (const [url, fixture] of fixtureFiles) {
      if (path === new URL(url, document.baseURI).pathname && method === 'GET') {
        return nativeFetch(new URL(fixture, document.baseURI).href);
      }
    }

    if (path.startsWith('/management/') || path.includes('/live-scene/')) {
      throw new Error('Live stadium endpoints are disabled in this mockup.');
    }
    return nativeFetch(input, init);
  };
})();
