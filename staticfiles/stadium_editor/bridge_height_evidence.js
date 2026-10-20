// Only explicitly bound provenance is accepted. No guessed deck offsets.
export const BRIDGE_HEIGHT_LABEL = 'Brücken: ungeklärte Geländeableitung – keine gemessene Fahrbahn.';

export function bridgeHeightEvidence(data = {}) {
  const records = Object.hasOwn(data.heightEvidence || {}, 'bridges') ? data.heightEvidence.bridges : [];
  if (!Array.isArray(records)) throw new Error('Ungültige Brücken-Höhenbelege.');
  const seen = new Set();
  for (const record of records) {
    if (!Number.isInteger(record.index) || seen.has(record.index) ||
        !/^way\/\d+$/.test(record.osm) ||
        !record.sourceTags?.bridge ||
        ['', 'no', 'false', '0'].includes(String(record.sourceTags.bridge).trim().toLowerCase()) ||
        record.status !== 'unresolved_terrain_derivation' || record.deckSource !== null ||
        !data.roads?.[record.index] ||
        JSON.stringify(record.editorPoints) !== JSON.stringify(data.roads[record.index].p)) {
      throw new Error('Brücken-Höhenbeleg passt nicht zum Ortsplan oder behauptet eine unbelegte Deckhöhe.');
    }
    seen.add(record.index);
  }
  return records;
}

export function bridgeHeightLabel(data, records = bridgeHeightEvidence(data)) {
  if (records.length) return BRIDGE_HEIGHT_LABEL;
  // Old DGM catalogs lack individual bridge identities. Do not silently call
  // their draped roads surveyed carriageways, or invent an identity mapping.
  if (!Object.hasOwn(data.heightEvidence || {}, 'bridges') && data.roads?.length &&
      /\bDGM/i.test(data.groundElevation?.source || '')) {
    return 'Wege/Brücken: ungeklärte Geländeableitung – keine gemessene Fahrbahn. Brückenbestand ohne Einzelzuordnung.';
  }
  return '';
}

// Visible in both source viewers; textContent prevents source-tag HTML injection.
export function mountBridgeHeightNotice(element, records, label = records.length ? BRIDGE_HEIGHT_LABEL : '') {
  if (!label) return () => {};
  const note = element.ownerDocument.createElement('div');
  note.dataset.bridgeHeightNotice = '';
  note.setAttribute('role', 'note');
  note.textContent = label;
  note.title = records.map(row => `${row.osm}${row.name ? ` · ${row.name}` : ''}`).join('\n');
  note.style.cssText = 'position:absolute;left:12px;right:12px;bottom:12px;z-index:2;padding:6px 9px;background:#071316e6;color:#f2cc85;font:12px/1.4 sans-serif;pointer-events:none;';
  element.append(note);
  return () => note.remove();
}
