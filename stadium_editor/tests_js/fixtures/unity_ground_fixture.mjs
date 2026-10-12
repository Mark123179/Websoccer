// Generated in memory: no arena assets, database, network CDN or binary fixtures.
export function groundFixture(legacy = false) {
  const chunks = [];
  let offset = 0;
  const append = values => {
    const start = offset;
    const bytes = Buffer.from(values.buffer);
    chunks.push(bytes);
    offset += bytes.length;
    return start;
  };
  const quad = (name, positions, part, uv = [0, 0, 1, 0, 1, 1, 0, 1]) => ({
    name, pathId: name, vertexCount: 4,
    positionOffset: append(new Float32Array(positions)),
    uvOffset: append(new Float32Array(uv)),
    parts: [{
      material: name, color: [1, 1, 1], ...part,
      indexOffset: append(new Uint32Array([0, 2, 1, 0, 3, 2])), indexCount: 6,
    }],
  });
  const flat = y => [-4, y, -2, 4, y, -2, 4, y, 2, -4, y, 2];
  const meshes = [
    quad('pitch_base', flat(0), {color: [.04, .4, .06]}),
    quad('pitch_markers', flat(.2), {
      texture: 'markers.svg',
      ...(!legacy && {transparent: true, alphaTest: .03}),
    }),
    quad('pitch_projected', [-4, 0, -2, 4, .8, -2, 4, 1.6, 2, -4, .8, 2], {
      texture: 'grass.svg',
      ...(!legacy && {uvProjection: [.08, .03, .015, .5, -.02, .04, .16, .5]}),
    }, [1, 0, 0, 0, 0, 1, 1, 1]), // Mirrored source UVs must not leak into world projection.
    // Satisfy the real roof loader; this tiny quad stays outside the camera.
    quad('roof_fixture', [50, 30, 50, 51, 30, 50, 51, 30, 51, 50, 30, 51], {}),
  ];
  return {
    geometry: Buffer.concat(chunks),
    manifest: {
      clubFmiId: 999999, sourceSha256: 'synthetic-ground',
      meshes, textures: ['markers.svg', 'grass.svg'], fixtures: [],
      calibration: {
        roofMinHeight: 20, roofMeshPrefixes: ['roof_'], skipMeshPrefixes: [],
        pitchPrefix: 'pitch_', crowdPrefix: 'crowd_', tickerRotationY: 0,
        tickerFrontCut: {normal: [0, 0, 1], constant: 100},
        standAxes: {'+x': 'OST', '-x': 'WEST', '+z': 'NORD', '-z': 'SUED'},
        orbitDefault: {azimuth: 0, elevation: 1, distance: 30},
      },
    },
  };
}

// Four wide bands avoid sampling antialiased boundaries. The first carries
// black RGB under zero alpha; the second is below alphaTest; the third blends.
export const markers = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="8">
<rect width="8" height="8" fill="black" fill-opacity="0"/>
<rect x="8" width="8" height="8" fill="white" fill-opacity=".02"/>
<rect x="16" width="8" height="8" fill="white" fill-opacity=".5"/>
<rect x="24" width="8" height="8" fill="white"/>
</svg>`;

export const grass = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">
<rect width="16" height="16" fill="red"/>
<rect x="16" width="16" height="16" fill="blue"/>
<rect y="16" width="16" height="16" fill="lime"/>
<rect x="16" y="16" width="16" height="16" fill="yellow"/>
</svg>`;
