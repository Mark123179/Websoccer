import { useEffect, useRef, useState } from 'react';
import { addExpansionArchitecture, roofSurfaceNames } from './_ExpansionArchitecture';
import { addOsmSurroundings } from './_OsmSurroundings';
import { addExistingFacade } from './_ExistingFacade';

type SceneStatus = 'loading' | 'webgl' | 'fallback';
type SceneVariant = 'original' | 'rundum' | 'sued';
type Preset = 'exterior' | 'interior' | 'roof-corner' | 'opposite' | 'surroundings';

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
  opposite: [-2.28, 0.53, 490],
  surroundings: [0.6, 0.57, 810],
};

export function StadiumScene({ variant = 'original' }: { variant?: SceneVariant }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<SceneStatus>('loading');
  const [message, setMessage] = useState('Originalmeshes und Ausbaugeometrie werden geladen …');
  const [fallbackMissing, setFallbackMissing] = useState(false);
  const [mobile3D, setMobile3D] = useState(() => window.innerWidth >= 700);
  const [roofVisible, setRoofVisible] = useState(() =>
    new URLSearchParams(window.location.search).get('roof') !== 'off' &&
    window.localStorage.getItem('dortmund-120-roof') !== 'hidden');
  const roofVisibleRef = useRef(roofVisible);
  roofVisibleRef.current = roofVisible;
  const applyRoofRef = useRef<(show: boolean) => void>(() => {});
  const [preset, setPreset] = useState<Preset>(() => {
    const requested = new URLSearchParams(window.location.search).get('view');
    if (requested === 'interior' || requested === 'roof-corner' || requested === 'opposite' || requested === 'surroundings') return requested;
    const saved = window.localStorage.getItem('dortmund-120-camera');
    return saved === 'interior' || saved === 'roof-corner' || saved === 'opposite' || saved === 'surroundings' ? saved : 'exterior';
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
    const own = <T extends { dispose: () => void }>(resource: T) => {
      if (disposed) resource.dispose();
      else resources.push(resource);
      return resource;
    };
    async function mount() {
      try {
        const THREE = await import(/* @vite-ignore */ new URL('/__mockup/vendor/three.module.js', window.location.origin).href);
        if (disposed) return;
        const scene = new THREE.Scene();
        scene.background = new THREE.Color('#162225');
        scene.fog = new THREE.Fog('#162225', 850, 1800);
        const camera = new THREE.PerspectiveCamera(42, 1, 1, 2400);
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
        if (disposed) return;
        if (!response.ok) throw new Error('Manifest der Originalmeshes konnte nicht geladen werden.');
        const manifest = (await response.json()) as Manifest;
        if (disposed) return;
        const binaryResponse = await fetch(`${ASSET_BASE}geometry.bin`);
        if (disposed) return;
        if (!binaryResponse.ok) throw new Error('Binärdaten der Originalmeshes konnten nicht geladen werden.');
        const binary = await binaryResponse.arrayBuffer();
        if (disposed) return;
        const textureLoader = new THREE.TextureLoader();
        const textures: Record<string, any> = {};
        await Promise.all(manifest.textures.map((name) => new Promise<void>((resolve, reject) => textureLoader.load(`${ASSET_BASE}${name}.webp`, (texture: any) => { texture.colorSpace = THREE.SRGBColorSpace; textures[name] = texture; own(texture); resolve(); }, undefined, () => reject(new Error(`Originaltextur ${name} konnte nicht geladen werden.`))))));
        if (disposed) return;
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
          own(geometry);
        }
        own({ dispose: () => materialCache.forEach(material => material.dispose()) });
        own(addExistingFacade(THREE, world));
        const expansion = addExpansionArchitecture(THREE, world, variant);
        if (expansion) own(expansion);
        own(addOsmSurroundings(THREE, scene, variant));
        const roofParts: any[] = [];
        world.traverse((part: any) => {
          const name = part.name?.replace(/^(ORIGINAL_|DERIVED_)/, '');
          if (roofSurfaceNames.has(name) ||
              (part.name?.startsWith('NEW_') && /_ROOF_JUNCTION|_EAVE/.test(part.name))) roofParts.push(part);
        });
        const applyRoof = (show: boolean) => roofParts.forEach(part => { part.visible = show; });
        applyRoofRef.current = applyRoof;
        applyRoof(roofVisibleRef.current);
        resources.push({ dispose: () => { applyRoofRef.current = () => {}; } });
        const resize = () => { if (!hostElement.clientWidth || !hostElement.clientHeight) return; renderer.setSize(hostElement.clientWidth, hostElement.clientHeight, false); camera.aspect = hostElement.clientWidth / hostElement.clientHeight; camera.updateProjectionMatrix(); };
        const observer = new ResizeObserver(resize); observer.observe(hostElement); resources.push({ dispose: () => observer.disconnect() }); resize();
        let dragging = false; let lastX = 0; let lastY = 0;
        const down = (event: PointerEvent) => { dragging = true; lastX = event.clientX; lastY = event.clientY; renderer.domElement.setPointerCapture(event.pointerId); };
        const up = () => { dragging = false; };
        const move = (event: PointerEvent) => { if (!dragging) return; azimuth += (event.clientX - lastX) * .006; elevation = clamp(elevation + (event.clientY - lastY) * .004, .15, 1.35); lastX = event.clientX; lastY = event.clientY; positionCamera(); };
        const wheel = (event: WheelEvent) => { event.preventDefault(); distance = clamp(distance * Math.exp(event.deltaY * .0008), 190, 1300); positionCamera(); };
        const cameraPreset = (event: Event) => {
          const key = (event as CustomEvent<Preset>).detail;
          if (!presets[key]) return;
          [azimuth, elevation, distance] = presets[key];
          positionCamera();
        };
        renderer.domElement.addEventListener('pointerdown', down); renderer.domElement.addEventListener('pointerup', up); renderer.domElement.addEventListener('pointercancel', up); renderer.domElement.addEventListener('pointermove', move); renderer.domElement.addEventListener('wheel', wheel, { passive: false });
        const presetHandlers = (['exterior', 'interior', 'roof-corner', 'opposite', 'surroundings'] as Preset[]).map((key) => {
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
        const syncRoof = (event: StorageEvent) => {
          if (event.key !== 'dortmund-120-roof') return;
          const show = event.newValue !== 'hidden';
          setRoofVisible(show);
          applyRoof(show);
        };
        window.addEventListener('storage', syncRoof);
        resources.push({ dispose: () => { renderer.domElement.removeEventListener('pointerdown', down); renderer.domElement.removeEventListener('pointerup', up); renderer.domElement.removeEventListener('pointercancel', up); renderer.domElement.removeEventListener('pointermove', move); presetHandlers.forEach(([key, handler]) => window.removeEventListener(`dortmund-camera-${key}`, handler)); window.removeEventListener('storage', syncCamera); window.removeEventListener('storage', syncRoof); } });
        setStatus('webgl'); setMessage(variant === 'original'
          ? 'Originalmeshes + rekonstruierte Bestands-Außenfassaden · Ziehen zum Drehen'
          : 'Originalmeshes + rekonstruierte Bestandsfassaden + abgeleitete Ausbaugeometrie · Ziehen zum Drehen');
        const animate = () => { if (disposed) return; renderer.render(scene, camera); frame = window.requestAnimationFrame(animate); }; animate();
      } catch (error) { if (!disposed) { setStatus('fallback'); setMessage(error instanceof Error ? error.message : '3D nicht verfügbar · Ersatzansicht'); } }
    }
    void mount();
    return () => { disposed = true; window.cancelAnimationFrame(frame); for (const resource of resources.reverse()) resource.dispose(); renderer?.dispose(); if (renderer?.domElement?.parentNode === hostElement) hostElement.removeChild(renderer.domElement); };
  }, [variant, mobile3D]);

  const toggleRoof = () => {
    const next = !roofVisible;
    setRoofVisible(next);
    window.localStorage.setItem('dortmund-120-roof', next ? 'visible' : 'hidden');
    applyRoofRef.current(next);
  };

  const fallback = variant === 'original' ? 'bestand-3d.webp' : variant === 'rundum' ? 'rundum-3d.webp' : 'sued-3d.webp';
  const capture = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('capture') === '1';
  return <div className={`dortmund120__scene-wrap ${capture ? 'dortmund120__scene-wrap--capture' : ''}`}>
    <div className="dortmund120__scene" ref={hostRef} />
    {!capture && <div className="dortmund120__scene-controls" aria-label="Kamera-Voreinstellungen">
      {(['exterior', 'interior', 'roof-corner', 'opposite', 'surroundings'] as Preset[]).map((key) => <button key={key} type="button" aria-pressed={preset === key} className={preset === key ? 'is-active' : ''} onClick={() => { setPreset(key); window.localStorage.setItem('dortmund-120-camera', key); window.dispatchEvent(new CustomEvent(`dortmund-camera-${key}`, { detail: key })); }}>{({exterior: 'Außen', interior: 'Innen', 'roof-corner': 'Dach / Ecke', opposite: 'Gegenseite', surroundings: 'Umgebung'} as const)[key]}</button>)}
    </div>}
    {!capture && <button type="button" className="dortmund120__roof-toggle" aria-pressed={!roofVisible}
      disabled={status !== 'webgl'} onClick={toggleRoof} title={status !== 'webgl' ? 'Dachansicht benötigt 3D' : undefined}>
      {roofVisible ? 'Dach ausblenden' : 'Dach einblenden'}
    </button>}
    {!capture && <div className="dortmund120__osm-credit">
      3D-Umgebung: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap-Mitwirkende</a>
      <span> · Höhen: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> (90-m-Raster)</span>
      <span> · Gebäudehöhen und Baumkronen schematisch</span>
    </div>}
    {!capture && variant !== 'original' && <div className="dortmund120__neighbor-note">
      Stadion Rote Erde: bestehende Nachbaranlage · Überschneidung des Konzepts ungeprüft
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