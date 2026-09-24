import { useEffect, useRef, useState } from 'react';

type SceneStatus = 'loading' | 'webgl' | 'fallback';
type SceneVariant = 'original' | 'rundum' | 'sued';
type Preset = 'exterior' | 'interior' | 'roof-corner';

const ASSET_BASE = '/__mockup/images/dortmund-120/';
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

interface Part { indexOffset: number; indexCount: number; texture?: string; material: string }
interface Entry { name: string; positionOffset: number; uvOffset: number; vertexCount: number; parts: Part[] }
interface Manifest { format: string; textures: string[]; meshes: Entry[] }

function materialColor(name: string) {
  const lower = name.toLowerCase();
  if (lower.includes('pitch') || lower.includes('dtmnd')) return '#31734a';
  if (lower.includes('seat')) return '#b3a04c';
  if (lower.includes('pllr') || lower.includes('iron') || lower.includes('trus')) return '#c6ac42';
  if (lower.includes('roof') || lower.includes('irpl')) return '#a3a9a7';
  if (lower.includes('glas')) return '#667d81';
  if (lower.includes('sgbd') || lower.includes('coat_band')) return '#d9bd49';
  if (lower.includes('wall') || lower.includes('cncr')) return '#777f7e';
  return '#8a9290';
}

const presets: Record<Preset, [number, number, number]> = {
  exterior: [0.88, 0.56, 490],
  interior: [-1.2, 0.63, 210],
  'roof-corner': [0.34, 1.03, 430],
};

function addConnectedExpansion(THREE: any, world: any, variant: SceneVariant) {
  if (variant === 'original') return null;
  const group = new THREE.Group();
  group.name = variant === 'rundum' ? 'DERIVED_RUNDUM_CONNECTED_RING' : 'HYPOTHESIZED_SOUTH_MAXIMUM';
  const seatMat = new THREE.MeshStandardMaterial({ color: '#c6a53d', roughness: .78, side: THREE.DoubleSide });
  const riserMat = new THREE.MeshStandardMaterial({ color: '#66572d', roughness: .86, side: THREE.DoubleSide });
  const steelMat = new THREE.MeshStandardMaterial({ color: '#c8aa49', roughness: .62, metalness: .5 });
  const roofMat = new THREE.MeshStandardMaterial({ color: '#b2bdb7', roughness: .58, metalness: .25, transparent: true, opacity: .36, depthWrite: false, side: THREE.DoubleSide });
  const mesh = (name: string, positions: number[], indices: number[], material: any) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    const object = new THREE.Mesh(geometry, material);
    object.name = name;
    group.add(object);
  };
  // Unity dimensions: original upper seats end at x=±93,z=±115,y≈37.
  // +x is called South only as a diagram label; it is not georeferenced.
  const band = (name: string, a: [number, number], b: [number, number], c: [number, number], d: [number, number], y0: number, y1: number) => {
    const t = 2.5;
    const p = [a[0], y0, a[1], b[0], y0, b[1], c[0], y1, c[1], d[0], y1, d[1], a[0], y0 - t, a[1], b[0], y0 - t, b[1], c[0], y1 - t, c[1], d[0], y1 - t, d[1]];
    mesh(name, p, [0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1, 3, 2, 6, 3, 6, 7], seatMat);
    mesh(`${name}_RISER`, p, [0, 4, 6, 0, 6, 3, 1, 2, 7, 1, 7, 5], riserMat);
  };
  const roof = (name: string, points: [number, number][], y: number) => mesh(name, points.flatMap(([x, z]) => [x, y, z]), [0, 1, 2, 0, 2, 3], roofMat);
  const support = (name: string, x: number, z: number, height: number, lean = 0) => {
    const object = new THREE.Mesh(new THREE.BoxGeometry(3.2, height, 3.2), steelMat);
    object.name = name; object.position.set(x, height / 2, z); object.rotation.z = lean; group.add(object);
  };
  if (variant === 'rundum') {
    for (let row = 0; row < 6; row += 1) {
      const a = row / 6; const b = (row + 1) / 6; const y0 = 38 + a * 31; const y1 = 38 + b * 31;
      band(`DERIVED_PLUS_X_ROW_${row + 1}`, [91 + 37 * a, -115 - 36 * a], [91 + 37 * a, 115 + 36 * a], [91 + 37 * b, 115 + 36 * b], [91 + 37 * b, -115 - 36 * b], y0, y1);
      band(`DERIVED_MINUS_X_ROW_${row + 1}`, [-91 - 37 * a, 115 + 36 * a], [-91 - 37 * a, -115 - 36 * a], [-91 - 37 * b, -115 - 36 * b], [-91 - 37 * b, 115 + 36 * b], y0, y1);
      band(`DERIVED_PLUS_Z_ROW_${row + 1}`, [-91 - 37 * a, 115 + 36 * a], [91 + 37 * a, 115 + 36 * a], [91 + 37 * b, 115 + 36 * b], [-91 - 37 * b, 115 + 36 * b], y0, y1);
      band(`DERIVED_MINUS_Z_ROW_${row + 1}`, [91 + 37 * a, -115 - 36 * a], [-91 - 37 * a, -115 - 36 * a], [-91 - 37 * b, -115 - 36 * b], [91 + 37 * b, -115 - 36 * b], y0, y1);
    }
    for (let row = 0; row < 6; row += 1) {
      const a = row / 6; const b = (row + 1) / 6; const y0 = 38 + a * 31; const y1 = 38 + b * 31;
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) band(`DERIVED_CORNER_ROW_${sx}_${sz}_${row + 1}`, [sx * (91 + 37 * a), sz * (115 + 36 * a)], [sx * (115 + 36 * a), sz * (91 + 37 * a)], [sx * (115 + 36 * b), sz * (91 + 37 * b)], [sx * (91 + 37 * b), sz * (115 + 36 * b)], y0, y1);
    }
    roof('DERIVED_ROOF_PLUS_X', [[65, -93], [65, 93], [145, 162], [145, -162]], 93);
    roof('DERIVED_ROOF_MINUS_X', [[-65, 93], [-65, -93], [-145, -162], [-145, 162]], 93);
    roof('DERIVED_ROOF_PLUS_Z', [[-65, 93], [65, 93], [145, 162], [-145, 162]], 93);
    roof('DERIVED_ROOF_MINUS_Z', [[65, -93], [-65, -93], [-145, -162], [145, -162]], 93);
    for (const [x, z] of [[132, -130], [132, 130], [-132, -130], [-132, 130], [0, -151], [0, 151], [151, 0], [-151, 0]]) support('DERIVED_EXTERIOR_SUPPORT', x, z, 104, x ? x / 150 * .08 : 0);
  } else {
    for (let row = 0; row < 12; row += 1) {
      const a = row / 12; const b = (row + 1) / 12;
      band(`HYPOTHESIZED_SOUTH_ROW_${row + 1}`, [91 + 76 * a, -104 - 21 * a], [91 + 76 * a, 104 + 21 * a], [91 + 76 * b, 104 + 21 * b], [91 + 76 * b, -104 - 21 * b], 38 + 63 * a, 38 + 63 * b);
    }
    band('HYPOTHESIZED_SOUTH_LEFT_ENDCAP', [91, -104], [91, -92], [167, -105], [167, -125], 38, 101);
    band('HYPOTHESIZED_SOUTH_RIGHT_ENDCAP', [91, 92], [91, 104], [167, 125], [167, 105], 38, 101);
    roof('HYPOTHESIZED_SOUTH_ROOF', [[154, -137], [154, 137], [184, 137], [184, -137]], 130);
    mesh('HYPOTHESIZED_SOUTH_RISING_ROOF', [
      59, 48, -109, 59, 48, 109, 154, 130, 137, 154, 130, -137,
    ], [0, 1, 2, 0, 2, 3], roofMat);
    roof('DERIVED_EXISTING_HEIGHT_WEST_ROOF', [[-96, -118], [-96, 118], [-55, 97], [-55, -97]], 47);
    roof('DERIVED_EXISTING_HEIGHT_NORTH_ROOF', [[-96, 118], [59, 118], [59, 85], [-55, 85]], 47);
    roof('DERIVED_EXISTING_HEIGHT_SOUTH_ROOF', [[59, -118], [-96, -118], [-55, -85], [59, -85]], 47);
    for (const z of [-122, -61, 0, 61, 122]) { support('HYPOTHESIZED_SOUTH_BRACED_SUPPORT', 172, z, 130, .12); support('HYPOTHESIZED_SOUTH_BRACE', 145, z, 101, -.16); }
  }
  world.add(group);
  // These are the original roof skin and pylons. The concept replaces them
  // visually, without changing the source asset or the occupied seating meshes.
  const retired = ['center3_0.001', 'center3_1.001', 'center3_12.001',
    'center3_13.001', 'center3_14.001', 'center3_25.001', 'center3_26.001',
    'center3_29.001', 'center3_21.001', 'center3_6.001'];
  world.children.forEach((child: any) => {
    if (retired.some(name => child.name === `ORIGINAL_${name}`)) child.visible = false;
  });
  return group;
}

function addExpansion(THREE: any, world: any, variant: SceneVariant) {
  return addConnectedExpansion(THREE, world, variant);
}

export function StadiumScene({ variant = 'original' }: { variant?: SceneVariant }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<SceneStatus>('loading');
  const [message, setMessage] = useState('Originalmeshes und Ausbaugeometrie werden geladen …');
  const [fallbackMissing, setFallbackMissing] = useState(false);
  const [mobile3D, setMobile3D] = useState(() => window.innerWidth >= 700);
  const [preset, setPreset] = useState<Preset>(() => {
    const requested = new URLSearchParams(window.location.search).get('view');
    if (requested === 'interior' || requested === 'roof-corner') return requested;
    const saved = window.localStorage.getItem('dortmund-120-camera');
    return saved === 'interior' || saved === 'roof-corner' ? saved : 'exterior';
  });
  const presetRef = useRef<Preset>(preset);
  presetRef.current = preset;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const hostElement = host;
    if (!mobile3D) {
      setStatus('fallback');
      setMessage('Mobile Vergleichsansicht · 3D bei Bedarf starten');
      return;
    }
    let disposed = false;
    let renderer: any;
    let frame = 0;
    const resources: Array<{ dispose: () => void }> = [];
    async function mount() {
      try {
        const THREE = await import(/* @vite-ignore */ new URL('/__mockup/vendor/three.module.js', window.location.origin).href);
        const scene = new THREE.Scene();
        scene.background = new THREE.Color('#162225');
        scene.fog = new THREE.Fog('#162225', 440, 780);
        const camera = new THREE.PerspectiveCamera(42, 1, 1, 1100);
        const target = new THREE.Vector3(0, 25, 0);
        let azimuth = presets[presetRef.current][0];
        let elevation = presets[presetRef.current][1];
        let distance = presets[presetRef.current][2];
        const positionCamera = () => {
          camera.position.set(target.x + distance * Math.sin(azimuth) * Math.cos(elevation), target.y + distance * Math.sin(elevation), target.z + distance * Math.cos(azimuth) * Math.cos(elevation));
          camera.lookAt(target);
        };
        positionCamera();
        const world = new THREE.Group();
        scene.add(world);
        scene.add(new THREE.HemisphereLight(0xe7f1f2, 0x344045, 1.35));
        const sun = new THREE.DirectionalLight(0xfff3d4, 1.5);
        sun.position.set(-135, 210, 100);
        scene.add(sun);
        renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.2;
        renderer.domElement.setAttribute('aria-label', 'Drehbares 3D-Modell des Signal Iduna Parks');
        hostElement.appendChild(renderer.domElement);
        const response = await fetch(`${ASSET_BASE}manifest.json`);
        if (!response.ok) throw new Error('Manifest der Originalmeshes konnte nicht geladen werden.');
        const manifest = (await response.json()) as Manifest;
        const binaryResponse = await fetch(`${ASSET_BASE}geometry.bin`);
        if (!binaryResponse.ok) throw new Error('Binärdaten der Originalmeshes konnten nicht geladen werden.');
        const binary = await binaryResponse.arrayBuffer();
        const textureLoader = new THREE.TextureLoader();
        const textures: Record<string, any> = {};
        await Promise.all(manifest.textures.map((name) => new Promise<void>((resolve, reject) => textureLoader.load(`${ASSET_BASE}${name}.webp`, (texture: any) => { texture.colorSpace = THREE.SRGBColorSpace; textures[name] = texture; resources.push(texture); resolve(); }, undefined, () => reject(new Error(`Originaltextur ${name} konnte nicht geladen werden.`))))));
        const materialCache = new Map<string, any>();
        for (const entry of manifest.meshes) {
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(new Float32Array(binary, entry.positionOffset, entry.vertexCount * 3)), 3));
          geometry.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(binary, entry.uvOffset, entry.vertexCount * 2), 2));
          const indices: number[] = [];
          const materials: any[] = [];
          for (const part of entry.parts) {
            const start = indices.length;
            indices.push(...new Uint32Array(binary, part.indexOffset, part.indexCount));
            geometry.addGroup(start, part.indexCount, materials.length);
            const key = part.texture || part.material;
            if (!materialCache.has(key)) materialCache.set(key, new THREE.MeshStandardMaterial({ color: part.texture ? '#ffffff' : materialColor(part.material), roughness: .83, metalness: .08, side: THREE.DoubleSide, ...(part.texture ? { map: textures[part.texture] } : {}) }));
            materials.push(materialCache.get(key));
          }
          if (!indices.length) { geometry.dispose(); continue; }
          geometry.setIndex(indices);
          geometry.computeVertexNormals();
          const mesh = new THREE.Mesh(geometry, materials);
          mesh.name = `ORIGINAL_${entry.name}`;
          world.add(mesh);
          resources.push(geometry);
        }
        const expansion = addConnectedExpansion(THREE, world, variant);
        if (expansion) resources.push({ dispose: () => expansion.traverse((object: any) => { if (object.geometry) object.geometry.dispose(); if (object.material) { const materials = Array.isArray(object.material) ? object.material : [object.material]; materials.forEach((material: any) => material.dispose()); } }) });
        const resize = () => { if (!hostElement.clientWidth || !hostElement.clientHeight) return; renderer.setSize(hostElement.clientWidth, hostElement.clientHeight, false); camera.aspect = hostElement.clientWidth / hostElement.clientHeight; camera.updateProjectionMatrix(); };
        const observer = new ResizeObserver(resize); observer.observe(hostElement); resources.push({ dispose: () => observer.disconnect() }); resize();
        let dragging = false; let lastX = 0; let lastY = 0;
        const down = (event: PointerEvent) => { dragging = true; lastX = event.clientX; lastY = event.clientY; renderer.domElement.setPointerCapture(event.pointerId); };
        const up = () => { dragging = false; };
        const move = (event: PointerEvent) => { if (!dragging) return; azimuth += (event.clientX - lastX) * .006; elevation = clamp(elevation + (event.clientY - lastY) * .004, .15, 1.35); lastX = event.clientX; lastY = event.clientY; positionCamera(); };
        const wheel = (event: WheelEvent) => { event.preventDefault(); distance = clamp(distance * Math.exp(event.deltaY * .0008), 190, 850); positionCamera(); };
        const cameraPreset = (event: Event) => {
          const key = (event as CustomEvent<Preset>).detail;
          if (!presets[key]) return;
          [azimuth, elevation, distance] = presets[key];
          positionCamera();
        };
        renderer.domElement.addEventListener('pointerdown', down); renderer.domElement.addEventListener('pointerup', up); renderer.domElement.addEventListener('pointercancel', up); renderer.domElement.addEventListener('pointermove', move); renderer.domElement.addEventListener('wheel', wheel, { passive: false });
        const presetHandlers = (['exterior', 'interior', 'roof-corner'] as Preset[]).map((key) => {
          const handler = () => cameraPreset(new CustomEvent('camera', { detail: key }));
          window.addEventListener(`dortmund-camera-${key}`, handler);
          return [key, handler] as const;
        });
        const syncCamera = (event: StorageEvent) => {
          if (event.key !== 'dortmund-120-camera') return;
          const key = event.newValue as Preset;
          if (!presets[key]) return;
          setPreset(key);
          cameraPreset(new CustomEvent('camera', { detail: key }));
        };
        window.addEventListener('storage', syncCamera);
        resources.push({ dispose: () => { renderer.domElement.removeEventListener('pointerdown', down); renderer.domElement.removeEventListener('pointerup', up); renderer.domElement.removeEventListener('pointercancel', up); renderer.domElement.removeEventListener('pointermove', move); presetHandlers.forEach(([key, handler]) => window.removeEventListener(`dortmund-camera-${key}`, handler)); window.removeEventListener('storage', syncCamera); } });
        setStatus('webgl'); setMessage(variant === 'original' ? 'Originalmeshes · Ziehen zum Drehen' : 'Originalmeshes + abgeleitete Ausbaugeometrie · Ziehen zum Drehen');
        const animate = () => { if (disposed) return; renderer.render(scene, camera); frame = window.requestAnimationFrame(animate); }; animate();
      } catch (error) { if (!disposed) { setStatus('fallback'); setMessage(error instanceof Error ? error.message : '3D nicht verfügbar · Ersatzansicht'); } }
    }
    void mount();
    return () => { disposed = true; window.cancelAnimationFrame(frame); for (const resource of resources.reverse()) resource.dispose(); renderer?.dispose(); if (renderer?.domElement?.parentNode === hostElement) hostElement.removeChild(renderer.domElement); };
  }, [variant, mobile3D]);

  const fallback = variant === 'original' ? 'bestand-3d.webp' : variant === 'rundum' ? 'rundum-3d.webp' : 'sued-3d.webp';
  const capture = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('capture') === '1';
  return <div className={`dortmund120__scene-wrap ${capture ? 'dortmund120__scene-wrap--capture' : ''}`}>
    <div className="dortmund120__scene" ref={hostRef} />
    {!capture && <div className="dortmund120__scene-controls" aria-label="Kamera-Voreinstellungen">
      {(['exterior', 'interior', 'roof-corner'] as Preset[]).map((key) => <button key={key} type="button" aria-pressed={preset === key} className={preset === key ? 'is-active' : ''} onClick={() => { setPreset(key); window.localStorage.setItem('dortmund-120-camera', key); window.dispatchEvent(new CustomEvent(`dortmund-camera-${key}`, { detail: key })); }}>{({exterior: 'Außen', interior: 'Innen', 'roof-corner': 'Dach / Ecke'} as const)[key]}</button>)}
    </div>}
    {status !== 'webgl' && !capture && <div className="dortmund120__fallback">
      {!fallbackMissing && <img src={`${ASSET_BASE}${fallback}`} alt={`3D-Vergleichsbild: ${variant}`} onError={() => setFallbackMissing(true)} />}
      <p>{message}</p>
      <small>{fallbackMissing ? 'Auch das Ersatzbild konnte nicht geladen werden.' : 'Standbild aus dem entsprechenden 3D-Zustand · Drehen erfordert WebGL.'}</small>
      {!mobile3D && <button className="dortmund120__start-3d" type="button" onClick={() => { setStatus('loading'); setMobile3D(true); }}>3D starten</button>}
    </div>}
  </div>;
}

export function OriginalScene() { return <StadiumScene variant="original" />; }