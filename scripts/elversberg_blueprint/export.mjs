#!/usr/bin/env node
// Offline Elversberg surroundings comparison. No application or source files are modified.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { chromium } from 'playwright-core';

const outputArg = process.argv.find((arg) => arg.startsWith('--out='));
const outputDir = path.resolve(outputArg?.slice('--out='.length) ||
  'generated-artifacts/elversberg-blueprint-comparison');
const width = 1880, height = 940;
const approved = JSON.parse(fs.readFileSync('docs/stadium/surroundings-camera.json', 'utf8'));
const expectedCamera = approved.states[0];
const stadiumSource = JSON.parse(fs.readFileSync('stadium_editor/blueprints/v2/elversberg_v2.json', 'utf8'));
const heightEvidence = JSON.parse(fs.readFileSync(
  'generated-artifacts/elversberg-height-visibility/height_inputs.json', 'utf8'));
if (!process.env.REPLIT_DEV_DOMAIN) {
  throw new Error('REPLIT_DEV_DOMAIN is required for proxied static study modules.');
}
fs.mkdirSync(outputDir, { recursive: true });
const prepareScript = path.resolve('scripts/elversberg_blueprint/prepare_layers.py');
const layerReport = JSON.parse(execFileSync('python', [prepareScript, outputDir], { encoding: 'utf8' }));
const layers = JSON.parse(fs.readFileSync(path.join(outputDir, 'source_layers.json'), 'utf8'));
const base = `https://${process.env.REPLIT_DEV_DOMAIN}`;
const browser = await chromium.launch({
  executablePath: '/repl/tools/bin/chromium',
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});

try {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  await page.route('**/favicon.ico', (route) => route.fulfill({ status: 204 }));
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  const response = await page.goto(`${base}/static/stadium_editor/study_models.js?v=blueprint-export-check`);
  if (!response?.ok()) {
    throw new Error(`Study module origin returned ${response?.status() ?? 'no response'}`);
  }
  await page.setContent(`<script type="importmap">{"imports":{"three":"${base}/static/stadium_editor/stage/vendor/three.module.js","three/addons/":"${base}/static/stadium_editor/stage/vendor/addons/"}}</script><div id="host" style="width:${width}px;height:${height}px"></div>`);
  const rendererSource = fs.readFileSync('scripts/elversberg_blueprint/render_page.js', 'utf8');
  await page.addScriptTag({ content: rendererSource });
  const captures = await page.evaluate(async ({ input }) =>
    window.renderElversbergBlueprint(input), {
    input: {
      base, source: stadiumSource, layers, evidence: heightEvidence,
      camera: expectedCamera, width, height,
    },
  });
  if (errors.length) throw new Error(`Browser console/page errors:\n${errors.join('\n')}`);
  if (captures.states.length !== 4) throw new Error(`Expected four fresh views, got ${captures.states.length}.`);

  const writeDataUrl = (filename, url) => fs.writeFileSync(path.join(outputDir, filename),
    Buffer.from(url.replace(/^data:image\/png;base64,/, ''), 'base64'));
  const states = [];
  for (const state of captures.states) {
    const stem = `${state.style}_${state.roof ? 'roof_on' : 'roof_off'}`;
    const image = `${stem}.png`;
    const baseline = `baseline_${state.roof ? 'roof_on' : 'roof_off'}.png`;
    const fieldMask = `field_mask_${state.roof ? 'roof_on' : 'roof_off'}.png`;
    const stadiumMask = `stadium_mask_${state.roof ? 'roof_on' : 'roof_off'}.png`;
    writeDataUrl(image, state.image);
    writeDataUrl(baseline, state.baseline);
    writeDataUrl(fieldMask, state.fieldMask);
    writeDataUrl(stadiumMask, state.stadiumMask);
    states.push({
      style: state.style, roof: state.roof, image, baseline, fieldMask, stadiumMask,
      projection: state.projection, pose: state.pose, corners: state.corners,
      mappedBuildings: layers.counts.buildings, mappedRoads: layers.counts.roads,
      mappedGreenAreas: layers.counts.greenAreas,
    });
  }

  const manifest = {
    format: [width, height],
    camera: {
      projection: captures.actualCamera.projection,
      pose: captures.actualCamera.pose,
      corners: captures.actualCamera.corners,
      approval: approved.approval,
      fieldScale: approved.field_scale,
      poseMeaning: 'matrixWorldInverse; world pose is its inverse',
    },
    sourceEvidence: {
      osm: 'stadium_editor/blueprints/v2/elversberg_v2.json surroundings; © OpenStreetMap contributors, ODbL 1.0',
      osmTimestamp: JSON.parse(fs.readFileSync('stadium_editor/blueprints/v2/elversberg.json', 'utf8'))
        .osm3s?.timestamp_osm_base,
      heightEvidence: 'generated-artifacts/elversberg-height-visibility/height_inputs.json; ©LVGL 2022, dl-de/by-2-0',
      heightClassification: heightEvidence.classification,
      canonicalGeoFrame: heightEvidence.frame,
      v2Alignment: layers.alignment,
      counts: layers.counts,
      pitchCornersMaxErrorPx: captures.actualCamera.cornersMaxErrorPx,
      actualMatrixMaxError: captures.actualCamera.matrixMaxError,
      daylightToneMapping: captures.daylightToneMapping,
    },
    limitations: [
      'Mapped Elversberg V2 source surroundings are used: 345 building footprints, 132 road lines and 18 green areas. The 132 road ribbons use schematic display widths (3/5/7 m by source class); source path locations are unchanged.',
      'Footprint overlap against canonical height-input OSM geometry validates V2 alignment. V2 source h fields are randomly generated and ignored; only matched conditional measured-height envelopes are used. All other spatial volumes are explicitly schematic low masses.',
      'No tree crowns, forest borders, or unmapped terrain are fabricated. Canopy and terrain remain unknown.',
      'Height envelopes are conditional evidence, not surveyed facade or roof geometry. Lidl height remains unknown.',
      'Fresh controls use the existing Elversberg study model, original ACESFilmic daylight, approved camera matrices and both roof states. Stadium and field source pixels are explicitly restored after environment compositing.',
      'Offline study only; no app/runtime integration, route changes, AI imagery, external data fetch, or database writes.',
    ],
    states,
  };
  fs.writeFileSync(path.join(outputDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`Rendered four fresh ${width}×${height} views to ${outputDir}`);
  console.log(`Mapped layers: ${JSON.stringify(layerReport.counts)}; overlap alignment: ${JSON.stringify(layerReport.alignment)}`);
} finally {
  await browser.close();
}

const composer = path.resolve('scripts/elversberg_blueprint/compose.py');
const result = execFileSync('python', [composer, outputDir], { encoding: 'utf8' });
console.log(result.trim());
