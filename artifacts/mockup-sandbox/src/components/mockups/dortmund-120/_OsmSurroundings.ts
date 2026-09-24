type Point = [number, number];
type Variant = 'original' | 'rundum' | 'sued';

// Local OSM extract around way 17235929, Signal Iduna Park. Coordinates are
// metres east/north of 51.49258, 7.45184. Simplified outlines, not survey data.
// © OpenStreetMap contributors, data retrieved 2026-09-24 (ODbL).
const buildings: [string, number, Point[]][] = [
  ['Helmut-Körnig-Halle', 15, [[239,174],[232,159],[240,110],[306,104],[366,128],[366,153],[353,184],[321,186],[274,176]]],
  ['Messehalle 3', 14, [[216,273],[176,264],[149,265],[126,265],[121,317],[206,400]]],
  ['Messehalle 7', 15, [[-139,322],[-28,331],[-33,390],[-126,382],[-143,380]]],
  ['Messehalle 4', 15, [[96,336],[97,326],[14,319],[5,430],[23,432],[88,436]]],
  ['Messehalle 8', 15, [[-196,318],[-139,322],[-143,380],[-159,405],[-203,401],[-235,386],[-201,328]]],
  ['Messehalle 2', 15, [[206,400],[115,394],[107,428],[88,436],[202,447]]],
  ['Messehalle 5', 15, [[23,432],[16,514],[-59,507],[-52,425],[-34,427]]],
  ['Messehalle 6', 15, [[-144,393],[-32,402],[-52,425],[-84,488],[-139,483],[-147,429]]],
  ['Messehalle 1', 15, [[269,413],[271,381],[212,377],[202,447],[266,452]]],
  ['Westfalenhalle', 21, [[398,424],[423,441],[400,460],[364,487],[328,484],[291,463],[281,431],[295,402],[326,387],[370,393]]],
  ['Eissportzentrum', 13, [[415,328],[421,266],[422,247],[472,251],[478,260],[471,333]]],
  ['Hotel', 16, [[319,333],[305,319],[296,308],[283,320],[287,331],[271,336],[222,343],[277,348]]],
  ['Willi-Daume-Haus', 10, [[-264,1],[-270,-1],[-269,-31],[-257,-33],[-252,-31],[-251,-1]]],
  ['Vereinsheim', 6, [[-134,-278],[-143,-283],[-127,-289],[-117,-262],[-126,-258]]],
  ['TU-Institut', 11, [[383,-281],[382,-303],[397,-304],[406,-282]]],
  // Smaller OSM building footprints, primarily service and sports buildings.
  // Their heights are illustrative wherever the source has no height tag.
  ['OSM 54179650', 5, [[113,157],[114,144],[121,144],[119,157]]],
  ['OSM 501412526', 5, [[119,156],[140,159],[159,162],[160,159],[140,156],[120,153]]],
  ['OSM 501412525', 5, [[159,164],[160,159],[161,151],[167,151],[165,165]]],
  ['OSM 1024885319', 7, [[221,40],[232,41],[233,30],[223,28]]],
  ['OSM 993083939', 6, [[326,53],[332,54],[334,36],[328,35]]],
  ['OSM 993083942', 7, [[328,92],[343,94],[345,82],[346,74],[342,74],[331,72]]],
  ['OSM 469727605', 5, [[370,9],[373,20],[377,20],[375,7]]],
  ['OSM 55782252', 8, [[-331,34],[-334,31],[-332,21],[-320,19],[-303,25],[-287,33],[-302,35]]],
  ['OSM 55782244', 5, [[-453,48],[-454,40],[-441,39],[-441,47]]],
  ['OSM 63124532', 6, [[-381,257],[-373,250],[-362,265],[-358,270],[-366,276]]],
  ['OSM 55782264', 6, [[-461,61],[-462,52],[-451,51],[-440,50],[-438,59]]],
  ['OSM 480632882', 5, [[-397,282],[-392,278],[-386,285],[-391,289]]],
  ['OSM 40674521', 9, [[-362,341],[-365,363],[-349,377],[-354,395],[-385,378],[-397,356],[-395,343]]],
  ['OSM 972704259', 5, [[244,-109],[229,-111],[229,-115],[245,-113]]],
  ['OSM 972704258', 5, [[246,-123],[253,-122],[252,-113],[244,-109]]],
  ['OSM 53098842', 6, [[267,-120],[261,-121],[253,-122],[252,-113],[266,-111]]],
  ['OSM 128618781', 7, [[266,-111],[278,-159],[273,-162],[258,-161],[251,-155],[271,-148],[270,-135]]],
  ['OSM 53098851', 6, [[255,-169],[267,-167],[269,-179],[271,-184],[254,-186],[251,-170]]],
  ['OSM 494669513', 5, [[301,-203],[303,-195],[304,-191],[314,-193],[311,-205]]],
  ['OSM 53062917', 9, [[301,-262],[300,-280],[329,-281],[330,-264],[316,-265],[316,-262]]],
  ['OSM 53062920', 9, [[399,-253],[398,-275],[406,-275],[420,-276],[421,-254]]],
  ['OSM 480632844', 5, [[-282,-41],[-290,-41],[-290,-47],[-286,-51],[-276,-51],[-276,-39]]],
  ['OSM 55782254', 7, [[-289,-7],[-295,-25],[-290,-39],[-282,-39],[-277,-26],[-281,-9]]],
  ['OSM 55782255', 6, [[-321,-30],[-323,-40],[-321,-45],[-308,-45],[-308,-29]]],
  ['OSM 436155591', 7, [[-333,-27],[-345,-24],[-346,-39],[-323,-41],[-323,-30]]],
  ['OSM 60309046', 5, [[-314,-322],[-323,-320],[-329,-311],[-315,-314]]],
];

const roads: [number, Point[]][] = [
  [7, [[-569,240],[-487,174],[-423,139],[-365,127],[-293,124],[-210,128]]],
  [8, [[-210,128],[-169,134],[-136,139],[-55,149],[13,170],[58,176],[130,184],[261,205],[360,218],[524,242]]],
  [6, [[-60,169],[-94,184],[-131,208],[-171,229],[-208,277],[-238,326]]],
  [5, [[-174,198],[-196,156],[-210,128],[-229,94],[-252,50],[-279,14],[-325,-9],[-355,-12]]],
  [5, [[-247,59],[-242,41],[-239,8],[-238,-22],[-244,-82],[-265,-129],[-298,-172],[-338,-225],[-359,-271],[-343,-318]]],
  [5, [[256,-97],[177,-107],[137,-112]]],
  [4, [[256,-97],[245,-14],[240,20],[231,88],[221,158],[217,188]]],
  [3, [[58,176],[63,140],[65,122]]],
  [3, [[342,-44],[358,-9],[375,36],[409,140],[418,170]]],
  [3, [[25,-277],[114,-301],[160,-314],[232,-333]]],
  [3, [[-42,-436],[28,-433],[86,-458],[142,-452],[212,-441],[258,-428]]],
  [3, [[202,-361],[104,-348],[1,-339]]],
];

const greenery: Point[][] = [
  [[247,-193],[270,-204],[172,-214],[85,-209],[12,-196],[6,-148],[69,-139],[109,-144]],
  [[329,-14],[326,-40],[315,-69],[296,-78],[278,-74],[266,-51],[278,-29]],
  [[395,296],[411,280],[413,250],[355,229],[295,221],[267,220],[278,291],[341,322]],
  [[134,248],[136,217],[142,200],[221,211],[219,256],[177,247]],
];

// One representative per ~16 m OSM tree cell; individual tree locations are
// mapped, while crown dimensions, species and unmapped trees remain unknown.
const trees: Point[] = [
  [147,550],[167,554],[-116,175],[-216,48],[-224,47],[-144,103],[-152,103],[-191,97],[-211,64],[-197,81],[-168,100],[-177,53],
  [-169,54],[-193,51],[-199,35],[-165,85],[-181,83],[-163,70],[-187,67],[-142,88],[-157,86],[-199,96],[-148,72],[-167,39],
  [-203,65],[-160,40],[-191,36],[-154,56],[-226,62],[-206,-89],[-191,-87],[-175,-84],[-159,-82],[-143,-80],[-208,-74],[-185,-71],
  [-169,-68],[-153,-66],[-210,-59],[-202,-58],[-187,-55],[-171,-53],[-155,-51],[-212,-44],[-204,-43],[-189,-40],[-173,-38],[-157,-36],
  [-214,-29],[-206,-28],[-191,-25],[-175,-23],[-159,-21],[-216,-14],[-208,-13],[-185,-9],[-169,-7],[-218,1],[-203,4],[-187,6],
  [-171,8],[-220,16],[-205,19],[-189,21],[-173,23],[-114,506],[237,519],[238,511],[247,511],[-352,455],[-233,435],[-217,449],
  [-203,463],[-127,189],[-135,181],[99,296],[-83,-139],[-275,47],[-257,69],[-242,93],[139,232],[140,220],[154,224],[155,241],
  [165,230],[192,243],[215,242],[216,232],[205,231],[217,219],[170,198],[159,196],[191,200],[201,202],[210,203],[237,207],
  [41,159],[31,158],[62,162],[71,164],[81,165],[99,167],[119,170],[130,172],[151,175],[162,176],[184,179],[204,182],
  [246,93],[242,38],[240,49],[239,60],[237,73],[243,27],[208,133],[206,124],[195,131],[216,123],[215,162],[217,151],
  [225,153],[227,142],[224,162],[220,184],[230,186],[258,190],[249,188],[277,192],[296,195],[305,196],[324,199],[343,202],
  [140,182],[150,184],[474,-89],[493,-87],[490,-99],[488,-114],[472,-104],[470,-119],[482,-145],[465,-149],[463,-130],[452,-124],
  [454,-109],[448,-153],[429,-157],[432,-143],[434,-128],[441,-84],[439,-99],[456,-94],[458,-80],[425,-74],[423,-89],[421,-103],
  [418,-119],[407,-78],[403,-108],[400,-123],[416,-133],[398,-137],[414,-147],[396,-152],[411,-162],[394,-166],[378,-157],[380,-143],
  [364,-132],[362,-148],[367,-117],[385,-113],[387,-98],[389,-83],[369,-103],[374,-73],[371,-88],[356,-78],[353,-93],[351,-107],
  [349,-122],[346,-137],[344,-152],[342,-164],[360,-161],[358,-63],[309,-93],[293,-95],[284,-96],[276,-97],[269,-99],[245,-102],
  [236,-95],[220,-97],[291,232],[284,231],[271,229],[271,223],[276,222],[171,478],[174,484],[158,490],[114,540],[394,333],
  [397,298],[396,308],[400,322],[401,318],[402,303],[387,336],[381,335],[367,334],[263,246],[261,284],[275,286],[288,287],
  [301,294],[310,290],[307,308],[304,238],[406,247],[408,285],[-257,381],[-251,372],[-246,364],[-275,371],[-266,353],[-261,345],
  [-256,336],[-221,282],[-226,290],[-211,268],[-205,260],[-199,251],[-187,235],[-169,237],[-175,243],[-181,250],[-189,259],[-200,275],
  [-212,294],[-325,9],[-296,17],[1,-186],[48,-192],[83,-199],[107,-201],[164,-204],
];

// Open-Meteo Elevation API, 90 m DEM interpolation, sampled on a 225 m
// spacing (2026-09-24); rows run south to north, columns west to east.
// The local site grade is blended to the stadium model's y=0 datum.
const elevations = [
  [105,111,105,121,122,114,97,100,105],
  [103,104,96,104,116,101,98,96,101],
  [96,97,89,87,90,91,96,92,94],
  [89,85,80,90,98,96,95,97,94],
  [79,96,98,103,90,105,111,108,109],
  [79,101,104,104,109,116,114,115,118],
  [98,103,103,108,116,120,126,122,120],
  [106,110,122,118,122,119,120,120,125],
  [102,108,114,121,113,113,120,120,121],
];

function heightAt(x: number, z: number) {
  const u = Math.max(0, Math.min(7.9999, x / 225 + 4));
  const v = Math.max(0, Math.min(7.9999, z / 225 + 4));
  const ix = Math.floor(u), iz = Math.floor(v), fx = u - ix, fz = v - iz;
  const a = elevations[iz][ix] * (1 - fx) + elevations[iz][ix + 1] * fx;
  const b = elevations[iz + 1][ix] * (1 - fx) + elevations[iz + 1][ix + 1] * fx;
  // We know the stadium is built into the site, not on untouched 90 m DEM.
  const edge = Math.max(Math.abs(x) / 180, Math.abs(z) / 200);
  const t = Math.max(0, Math.min(1, (edge - 1) / .55));
  return -3 + (a * (1 - fz) + b * fz - 90) * t * t * (3 - 2 * t);
}

export function addOsmSurroundings(THREE: any, scene: any, variant: Variant) {
  const group = new THREE.Group();
  group.name = 'OSM_NEIGHBOURHOOD_3D';
  // OSM outline of Signal Iduna Park is ~16° off model north; the long axis
  // of the exported mesh is z. Centre and footprint dimensions match to ~8%.
  group.rotation.y = .16;
  group.scale.set(1.08, 1, 1.08);
  const terrainMaterial = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, side: THREE.DoubleSide });
  const roadMaterial = new THREE.MeshStandardMaterial({ color: '#556260', roughness: 1, side: THREE.DoubleSide });
  const pavingMaterial = new THREE.MeshStandardMaterial({ color: '#89918a', roughness: 1, side: THREE.DoubleSide });
  const markingMaterial = new THREE.MeshBasicMaterial({ color: '#c2c5ad', side: THREE.DoubleSide });
  const parkMaterial = new THREE.MeshStandardMaterial({ color: '#536752', roughness: 1, side: THREE.DoubleSide });
  const buildingMaterial = new THREE.MeshStandardMaterial({ color: '#a3aaa2', roughness: .95, side: THREE.DoubleSide });
  const roofMaterial = new THREE.MeshStandardMaterial({ color: '#737f7c', roughness: 1, side: THREE.DoubleSide });
  const windowMaterial = new THREE.MeshStandardMaterial({ color: '#4a6264', roughness: .35, metalness: .2 });
  const trackMaterial = new THREE.MeshStandardMaterial({ color: '#725a51', roughness: 1, side: THREE.DoubleSide });
  const pitchMaterial = new THREE.MeshStandardMaterial({ color: '#476449', roughness: 1, side: THREE.DoubleSide });
  const trunkMaterial = new THREE.MeshStandardMaterial({ color: '#59605b', roughness: 1 });
  const canopyMaterial = new THREE.MeshStandardMaterial({ color: '#71886c', roughness: 1 });
  const contourMaterial = new THREE.LineBasicMaterial({ color: '#a5b3a4', transparent: true, opacity: .2, depthWrite: false });
  const materials = [terrainMaterial, roadMaterial, pavingMaterial, markingMaterial, parkMaterial,
    buildingMaterial, roofMaterial, windowMaterial, trackMaterial, pitchMaterial, trunkMaterial, canopyMaterial, contourMaterial];

  const terrain = new THREE.PlaneGeometry(1800, 1800, 48, 48);
  terrain.rotateX(-Math.PI / 2);
  const positions = terrain.attributes.position;
  const shades: number[] = [];
  const low = new THREE.Color('#374841'), high = new THREE.Color('#647064');
  for (let i = 0; i < positions.count; i++) {
    const y = heightAt(positions.getX(i), positions.getZ(i));
    positions.setY(i, y);
    const shade = low.clone().lerp(high, Math.max(0, Math.min(1, (y + 12) / 42)));
    shades.push(shade.r, shade.g, shade.b);
  }
  positions.needsUpdate = true;
  terrain.setAttribute('color', new THREE.Float32BufferAttribute(shades, 3));
  terrain.computeVertexNormals();
  const land = new THREE.Mesh(terrain, terrainMaterial);
  land.name = 'DEM_TERRAIN';
  group.add(land);

  // Contours follow the interpolated DEM itself; they clarify real relief,
  // rather than exaggerating hills or adding fictional terrain features.
  const contours: number[] = [];
  const interval = 37.5;
  for (let x = -900; x < 900; x += interval) {
    for (let z = -900; z < 900; z += interval) {
      const corners: Point[] = [[x,z],[x+interval,z],[x+interval,z+interval],[x,z+interval]];
      const heights = corners.map(([cx,cz]) => heightAt(cx,cz));
      const low = Math.min(...heights), high = Math.max(...heights);
      for (let level = Math.ceil(low / 5) * 5; level < high; level += 5) {
        const crosses: Point[] = [];
        for (let side = 0; side < 4; side++) {
          const next = (side + 1) % 4, a = heights[side], b = heights[next];
          if ((a <= level && b > level) || (b <= level && a > level)) {
            const t = (level - a) / (b - a);
            crosses.push([
              corners[side][0] + (corners[next][0] - corners[side][0]) * t,
              corners[side][1] + (corners[next][1] - corners[side][1]) * t,
            ]);
          }
        }
        if (crosses.length === 2) contours.push(crosses[0][0],level+.15,crosses[0][1],crosses[1][0],level+.15,crosses[1][1]);
      }
    }
  }
  const contourGeometry = new THREE.BufferGeometry();
  contourGeometry.setAttribute('position', new THREE.Float32BufferAttribute(contours, 3));
  const contourLines = new THREE.LineSegments(contourGeometry, contourMaterial);
  contourLines.name = 'DEM_FIVE_METRE_CONTOURS';
  group.add(contourLines);

  const polygon = (points: Point[], material: any, name: string, height = 0) => {
    const outline = new THREE.Shape();
    points.forEach(([x,z], i) => i ? outline.lineTo(x, -z) : outline.moveTo(x, -z));
    outline.closePath();
    const geometry = new THREE.ExtrudeGeometry(outline, { depth: height || .12, bevelEnabled: false, curveSegments: 1 });
    geometry.rotateX(-Math.PI / 2);
    const mesh = new THREE.Mesh(geometry, material);
    const [cx, cz] = points.reduce(([x,z], p) => [x + p[0] / points.length, z + p[1] / points.length], [0,0]);
    mesh.position.y = heightAt(cx, cz) + (height ? .2 : .3);
    mesh.name = name;
    group.add(mesh);
  };
  for (const [index, points] of greenery.entries()) polygon(points, parkMaterial, `OSM_GREEN_${index}`);
  const windowSamples: [number, number, number, number][] = [];
  for (const [name, height, points] of buildings) {
    // An enlarged stand displaces site uses; do not draw existing buildings
    // through the hypothetical new construction.
    if (variant === 'sued' && points.some(([x,z]) => x > 90 && x < 175 && Math.abs(z) < 175)) continue;
    polygon(points, [roofMaterial, buildingMaterial], `OSM_BUILDING_${name}`, height);
    const [cx,cz] = points.reduce(([x,z], p) => [x+p[0]/points.length,z+p[1]/points.length], [0,0]);
    for (let i = 0; i < points.length; i++) {
      const [ax,az] = points[i], [bx,bz] = points[(i+1)%points.length];
      const dx = bx-ax, dz = bz-az, length = Math.hypot(dx,dz);
      if (length < 9) continue;
      const yaw = Math.atan2(dz, -dx);
      for (let p = 5; p < length-3; p += 7) {
        for (let y = 4; y < height-1; y += 4) {
          windowSamples.push([ax+dx*p/length, heightAt(cx,cz)+y, az+dz*p/length, yaw]);
        }
      }
    }
  }
  const windowGeometry = new THREE.BoxGeometry(2.5, 1.6, .18);
  const windows = new THREE.InstancedMesh(windowGeometry, windowMaterial, windowSamples.length);
  windows.name = 'OSM_BUILDING_FACADE_RHYTHM';
  const windowObject = new THREE.Object3D();
  windowSamples.forEach(([x,y,z,yaw], i) => {
    windowObject.position.set(x,y,z);
    windowObject.rotation.y = yaw;
    windowObject.updateMatrix();
    windows.setMatrixAt(i, windowObject.matrix);
  });
  windows.instanceMatrix.needsUpdate = true;
  windows.computeBoundingSphere();
  group.add(windows);

  // The mapped footprint of the neighboring Stadion Rote Erde is important
  // context for understanding the enlargement's physical constraints.
  const roteErde: Point[] = [[231,-20],[226,17],[221,49],[216,86],[206,115],[183,135],
    [159,144],[110,129],[92,107],[87,67],[105,-50],[121,-76],[161,-93],
    [189,-89],[220,-63],[232,-32]];
  const center: Point = [162,24];
  const ground = heightAt(...center) + .52;
  const track = new THREE.Shape();
  roteErde.forEach(([x,z],i) => i ? track.lineTo(x,-z) : track.moveTo(x,-z));
  track.closePath();
  const inner = roteErde.map(([x,z]): Point => [center[0]+(x-center[0])*.72,center[1]+(z-center[1])*.72]);
  const hole = new THREE.Path();
  inner.slice().reverse().forEach(([x,z],i) => i ? hole.lineTo(x,-z) : hole.moveTo(x,-z));
  hole.closePath();
  track.holes.push(hole);
  const trackGeometry = new THREE.ShapeGeometry(track);
  trackGeometry.rotateX(-Math.PI/2);
  const trackMesh = new THREE.Mesh(trackGeometry,trackMaterial);
  trackMesh.position.y = ground;
  trackMesh.name = 'OSM_STADION_ROTE_ERDE_TRACK_SCHEMATIC';
  group.add(trackMesh);
  polygon(inner, pitchMaterial, 'OSM_STADION_ROTE_ERDE_INFIELD');
  const roadVertices: number[] = [];
  const pavedEdges: number[] = [];
  const markings: number[] = [];
  const ribbon = (vertices: number[], ax: number, az: number, bx: number, bz: number, width: number, lift: number) => {
    const dx = bx-ax, dz = bz-az, length = Math.hypot(dx,dz);
    if (length < .01) return;
    const ox = dz/length*width/2, oz = -dx/length*width/2;
    const a: [number,number,number] = [ax+ox,heightAt(ax+ox,az+oz)+lift,az+oz];
    const b: [number,number,number] = [ax-ox,heightAt(ax-ox,az-oz)+lift,az-oz];
    const c: [number,number,number] = [bx+ox,heightAt(bx+ox,bz+oz)+lift,bz+oz];
    const d: [number,number,number] = [bx-ox,heightAt(bx-ox,bz-oz)+lift,bz-oz];
    vertices.push(...a,...b,...c,...b,...d,...c);
  };
  for (const [width, points] of roads) {
    for (let i = 1; i < points.length; i++) {
      const [ax, az] = points[i-1], [bx,bz] = points[i];
      const dx = bx - ax, dz = bz - az, length = Math.hypot(dx,dz);
      if (length < .01) continue;
      // Subdivide long OSM way segments to drape over the DEM instead of
      // cutting straight through rising terrain.
      const steps = Math.ceil(length/12);
      for (let j = 0; j < steps; j++) {
        const u = j/steps, v = (j+1)/steps;
        const from: Point = [ax+dx*u,az+dz*u], to: Point = [ax+dx*v,az+dz*v];
        ribbon(pavedEdges,...from,...to,width+2.6,.42);
        ribbon(roadVertices,...from,...to,width,.48);
      }
      if (width >= 6) {
        for (let d = 5; d+6 < length; d += 16) {
          ribbon(markings,ax+dx*d/length,az+dz*d/length,
            ax+dx*(d+6)/length,az+dz*(d+6)/length,.28,.53);
        }
      }
    }
  }
  for (const [name,vertices,material] of [
    ['OSM_ROAD_SHOULDERS',pavedEdges,pavingMaterial],
    ['OSM_ROAD_SURFACES',roadVertices,roadMaterial],
    ['OSM_ROAD_DASHES',markings,markingMaterial],
  ] as const) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry,material);
    mesh.name = name;
    group.add(mesh);
  }

  const visibleTrees = trees.filter(([x,z]) =>
    variant !== 'sued' || !(x > 90 && x < 175 && Math.abs(z) < 175));
  const trunkGeometry = new THREE.CylinderGeometry(.75, 1.2, 9, 6);
  const crownGeometry = new THREE.IcosahedronGeometry(4.8, 1);
  const stems = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, visibleTrees.length);
  const crowns = new THREE.InstancedMesh(crownGeometry, canopyMaterial, visibleTrees.length*3);
  stems.name = 'OSM_MAPPED_TREE_TRUNKS';
  crowns.name = 'OSM_MAPPED_TREE_CANOPIES';
  const object = new THREE.Object3D();
  visibleTrees.forEach(([x,z], index) => {
    const y = heightAt(x,z);
    object.position.set(x, y+4.5, z);
    object.rotation.set(0,0,0);
    object.scale.setScalar(1);
    object.updateMatrix();
    stems.setMatrixAt(index, object.matrix);
    const variation = 1 + ((Math.abs(x*13+z*7)%11)-5)*.035;
    for (let lobe = 0; lobe < 3; lobe++) {
      const a = (index*2.4+lobe*2.1), spread = lobe===0 ? 0 : 2.1;
      object.position.set(x+Math.cos(a)*spread, y+11.5+(lobe===0 ? 2.7 : 0), z+Math.sin(a)*spread);
      object.scale.setScalar(variation*(lobe===0 ? 1.2 : .95));
      object.updateMatrix();
      crowns.setMatrixAt(index*3+lobe, object.matrix);
    }
  });
  stems.instanceMatrix.needsUpdate = true;
  crowns.instanceMatrix.needsUpdate = true;
  stems.computeBoundingSphere();
  crowns.computeBoundingSphere();
  group.add(stems, crowns);
  scene.add(group);
  return { dispose: () => {
    scene.remove(group);
    group.traverse((part: any) => part.geometry?.dispose());
    materials.forEach(material => material.dispose());
  }};
}