import { useEffect, useRef, useState } from 'react';

type SceneStatus = 'loading' | 'webgl' | 'fallback';

interface MeshPart {
  indexOffset: number;
  indexCount: number;
  texture?: string;
  material: string;
}

interface MeshEntry {
  name: string;
  positionOffset: number;
  uvOffset: number;
  vertexCount: number;
  parts: MeshPart[];
}

interface OriginalManifest {
  format: string;
  textures: string[];
  meshes: MeshEntry[];
}

const ASSET_BASE = '/__mockup/images/dortmund-120/';
const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

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

export function OriginalScene() {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<SceneStatus>('loading');
  const [message, setMessage] = useState('Originalmeshes werden geladen …');

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const hostElement = host;

    let disposed = false;
    let renderer: any;
    let frame = 0;
    const resources: Array<{ dispose: () => void }> = [];
    const sceneUrl = `${ASSET_BASE}original-2d.webp`;

    async function mountOriginal() {
      try {
        const THREE_URL = new URL('/__mockup/vendor/three.module.js', window.location.origin).href;
        const THREE = await import(/* @vite-ignore */ THREE_URL);
        if (disposed) return;

        const scene = new THREE.Scene();
        scene.background = new THREE.Color('#162225');
        scene.fog = new THREE.Fog('#162225', 440, 760);
        const camera = new THREE.PerspectiveCamera(42, 1, 1, 1000);
        const target = new THREE.Vector3(0, 24, 0);
        let azimuth = 0.58;
        let elevation = 0.62;
        let distance = 375;
        let dragging = false;
        let lastX = 0;
        let lastY = 0;

        const positionCamera = () => {
          camera.position.set(
            target.x + distance * Math.sin(azimuth) * Math.cos(elevation),
            target.y + distance * Math.sin(elevation),
            target.z + distance * Math.cos(azimuth) * Math.cos(elevation),
          );
          camera.lookAt(target);
        };
        positionCamera();

        const world = new THREE.Group();
        scene.add(world);
        scene.add(new THREE.HemisphereLight(0xe7f1f2, 0x344045, 1.35));
        const sun = new THREE.DirectionalLight(0xfff3d4, 1.5);
        sun.position.set(-135, 210, 100);
        scene.add(sun);

        renderer = new THREE.WebGLRenderer({
          antialias: true,
          powerPreference: 'high-performance',
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.2;
        renderer.domElement.setAttribute('aria-label', 'Drehbares 3D-Modell des Signal Iduna Parks');
        hostElement.appendChild(renderer.domElement);

        const response = await fetch(`${ASSET_BASE}manifest.json`);
        if (!response.ok) throw new Error('Manifest der Originalmeshes konnte nicht geladen werden.');
        const manifest = (await response.json()) as OriginalManifest;
        if (manifest.format !== 'unity-mesh-binary-v1') {
          throw new Error('Das Format der Originalgeometrie ist unbekannt.');
        }
        const binaryResponse = await fetch(`${ASSET_BASE}geometry.bin`);
        if (!binaryResponse.ok) throw new Error('Binärdaten der Originalmeshes konnten nicht geladen werden.');
        const binary = await binaryResponse.arrayBuffer();

        const textureLoader = new THREE.TextureLoader();
        const textures: Record<string, any> = {};
        await Promise.all(manifest.textures.map((name) => new Promise<void>((resolve, reject) => {
          textureLoader.load(
            `${ASSET_BASE}${name}.webp`,
            (texture: any) => {
              texture.colorSpace = THREE.SRGBColorSpace;
              textures[name] = texture;
              resources.push(texture);
              resolve();
            },
            undefined,
            () => reject(new Error(`Originaltextur ${name} konnte nicht geladen werden.`)),
          );
        })));
        if (disposed) return;

        const materialCache = new Map<string, any>();
        for (const entry of manifest.meshes) {
          const geometry = new THREE.BufferGeometry();
          const originalPositions = new Float32Array(
            binary,
            entry.positionOffset,
            entry.vertexCount * 3,
          );
          geometry.setAttribute('position', new THREE.BufferAttribute(
            new Float32Array(originalPositions), 3,
          ));
          geometry.setAttribute('uv', new THREE.BufferAttribute(
            new Float32Array(binary, entry.uvOffset, entry.vertexCount * 2), 2,
          ));

          const indices: number[] = [];
          const materials: any[] = [];
          for (const part of entry.parts) {
            const start = indices.length;
            indices.push(...new Uint32Array(binary, part.indexOffset, part.indexCount));
            geometry.addGroup(start, part.indexCount, materials.length);
            const key = part.texture || part.material;
            if (!materialCache.has(key)) {
              materialCache.set(key, new THREE.MeshStandardMaterial({
                color: part.texture ? '#ffffff' : materialColor(part.material),
                roughness: 0.83,
                metalness: 0.08,
                side: THREE.DoubleSide,
                ...(part.texture ? { map: textures[part.texture] } : {}),
              }));
            }
            materials.push(materialCache.get(key));
          }
          if (!indices.length) {
            geometry.dispose();
            continue;
          }
          geometry.setIndex(indices);
          geometry.computeVertexNormals();
          const mesh = new THREE.Mesh(geometry, materials);
          mesh.frustumCulled = true;
          world.add(mesh);
          resources.push(geometry);
        }
        if (disposed) return;

        const resize = () => {
          if (!hostElement.clientWidth || !hostElement.clientHeight) return;
          renderer.setSize(hostElement.clientWidth, hostElement.clientHeight, false);
          camera.aspect = hostElement.clientWidth / hostElement.clientHeight;
          camera.updateProjectionMatrix();
          if (camera.aspect < 1 && distance < 375 / camera.aspect) {
            distance = 375 / camera.aspect;
            positionCamera();
          }
        };
        const observer = new ResizeObserver(resize);
        observer.observe(hostElement);
        resources.push({ dispose: () => observer.disconnect() });
        resize();

        const onPointerDown = (event: PointerEvent) => {
          dragging = true;
          lastX = event.clientX;
          lastY = event.clientY;
          renderer.domElement.setPointerCapture(event.pointerId);
        };
        const onPointerUp = () => { dragging = false; };
        const onPointerMove = (event: PointerEvent) => {
          if (!dragging) return;
          azimuth += (event.clientX - lastX) * 0.006;
          elevation = clamp(elevation + (event.clientY - lastY) * 0.004, 0.15, 1.35);
          lastX = event.clientX;
          lastY = event.clientY;
          positionCamera();
        };
        const onWheel = (event: WheelEvent) => {
          event.preventDefault();
          distance = clamp(distance * Math.exp(event.deltaY * 0.0008), 240, 850);
          positionCamera();
        };
        const onDoubleClick = () => {
          azimuth = 0.58;
          elevation = 0.62;
          distance = 375;
          positionCamera();
        };
        renderer.domElement.addEventListener('pointerdown', onPointerDown);
        renderer.domElement.addEventListener('pointerup', onPointerUp);
        renderer.domElement.addEventListener('pointercancel', onPointerUp);
        renderer.domElement.addEventListener('pointermove', onPointerMove);
        renderer.domElement.addEventListener('wheel', onWheel, { passive: false });
        renderer.domElement.addEventListener('dblclick', onDoubleClick);
        resources.push({
          dispose: () => {
            renderer?.domElement.removeEventListener('pointerdown', onPointerDown);
            renderer?.domElement.removeEventListener('pointerup', onPointerUp);
            renderer?.domElement.removeEventListener('pointercancel', onPointerUp);
            renderer?.domElement.removeEventListener('pointermove', onPointerMove);
            renderer?.domElement.removeEventListener('wheel', onWheel);
            renderer?.domElement.removeEventListener('dblclick', onDoubleClick);
          },
        });

        setStatus('webgl');
        setMessage('Originalmeshes · Ziehen zum Drehen');
        const animate = () => {
          if (disposed) return;
          renderer.render(scene, camera);
          frame = window.requestAnimationFrame(animate);
        };
        animate();
      } catch (error) {
        if (disposed) return;
        setStatus('fallback');
        setMessage(error instanceof Error ? error.message : '3D nicht verfügbar · CPU-2D-Ansicht');
      }
    }

    void mountOriginal();
    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      for (const resource of resources.reverse()) resource.dispose();
      renderer?.dispose();
      if (renderer?.domElement.parentNode === hostElement) hostElement.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div className="dortmund120__scene-wrap">
      <div className="dortmund120__scene" ref={hostRef} />
      {status !== 'webgl' && (
        <div className="dortmund120__fallback">
          <img
            src="/__mockup/images/dortmund-120/original-2d.webp"
            alt="CPU-gerenderte 2D-Projektion der extrahierten Dortmunder Originalmeshes"
          />
          <p>{message}</p>
          {status === 'fallback' && <small>Originale 2D-Projektion · WebGL-Drehung nicht verfügbar</small>}
        </div>
      )}
    </div>
  );
}