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

// One representative per ~32 m OSM tree cell; tree positions are mapped,
// but species, dimensions and missing trees are not known.
const trees: Point[] = [
  [147,550],[167,554],[-116,175],[-216,48],[-191,97],[-211,64],[-199,96],[-189,82],
  [-226,62],[-206,-89],[-191,-87],[-210,-59],[-214,-29],[-218,1],[-114,506],
  [237,519],[414,499],[404,516],[-385,447],[-375,449],[-352,455],[-233,435],
  [-217,449],[-359,489],[-340,483],[-395,507],[-390,470],[-135,181],[99,296],
  [-275,47],[-257,69],[-242,93],[139,232],[165,230],[192,243],[217,219],
  [170,198],[237,207],[109,169],[130,172],[162,176],[204,182],[246,93],
  [242,38],[208,133],[225,153],[258,190],[277,192],[296,195],[324,199],
  [425,-74],[421,-103],[407,-78],[403,-108],[416,-133],[398,-137],[411,-162],
  [378,-157],[367,-117],[374,-73],[351,-107],[346,-137],[342,-164],[358,-63],
  [309,-93],[284,-96],[276,-97],[245,-102],[220,-97],[291,232],[171,478],
  [158,490],[114,540],[394,333],[381,335],[261,284],[288,287],[301,294],
  [406,247],[408,285],[-257,381],[-251,372],[-261,345],[-221,282],[-199,251],
  [-187,235],[-212,294],[-325,9],[-296,17],[83,-199],[107,-201],[164,-204],
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
  const roadMaterial = new THREE.MeshStandardMaterial({ color: '#65706c', roughness: 1, side: THREE.DoubleSide });
  const parkMaterial = new THREE.MeshStandardMaterial({ color: '#536752', roughness: 1, side: THREE.DoubleSide });
  const buildingMaterial = new THREE.MeshStandardMaterial({ color: '#84908b', roughness: .95, side: THREE.DoubleSide });
  const trunkMaterial = new THREE.MeshStandardMaterial({ color: '#59605b', roughness: 1 });
  const canopyMaterial = new THREE.MeshStandardMaterial({ color: '#71886c', roughness: 1 });
  const materials = [terrainMaterial, roadMaterial, parkMaterial, buildingMaterial, trunkMaterial, canopyMaterial];

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
  for (const [name, height, points] of buildings) {
    // An enlarged stand displaces site uses; do not draw existing buildings
    // through the hypothetical new construction.
    if (variant === 'sued' && points.some(([x,z]) => x > 90 && x < 175 && Math.abs(z) < 175)) continue;
    polygon(points, buildingMaterial, `OSM_BUILDING_${name}`, height);
  }
  const roadVertices: number[] = [];
  for (const [width, points] of roads) {
    for (let i = 1; i < points.length; i++) {
      const [ax, az] = points[i-1], [bx,bz] = points[i];
      const dx = bx - ax, dz = bz - az, length = Math.hypot(dx,dz);
      if (length < .01) continue;
      const ox = dz / length * width / 2, oz = -dx / length * width / 2;
      const a: [number,number,number] = [ax+ox,heightAt(ax,az)+.45,az+oz];
      const b: [number,number,number] = [ax-ox,heightAt(ax,az)+.45,az-oz];
      const c: [number,number,number] = [bx+ox,heightAt(bx,bz)+.45,bz+oz];
      const d: [number,number,number] = [bx-ox,heightAt(bx,bz)+.45,bz-oz];
      roadVertices.push(...a,...b,...c,...b,...d,...c);
    }
  }
  const roadGeometry = new THREE.BufferGeometry();
  roadGeometry.setAttribute('position', new THREE.Float32BufferAttribute(roadVertices, 3));
  roadGeometry.computeVertexNormals();
  const roadMesh = new THREE.Mesh(roadGeometry, roadMaterial);
  roadMesh.name = 'OSM_ROADS';
  group.add(roadMesh);

  const visibleTrees = trees.filter(([x,z]) =>
    variant !== 'sued' || !(x > 90 && x < 175 && Math.abs(z) < 175));
  const trunkGeometry = new THREE.CylinderGeometry(.9, 1.2, 8, 5);
  const crownGeometry = new THREE.ConeGeometry(5.5, 16, 7);
  const stems = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, visibleTrees.length);
  const crowns = new THREE.InstancedMesh(crownGeometry, canopyMaterial, visibleTrees.length);
  stems.name = 'OSM_MAPPED_TREE_TRUNKS';
  crowns.name = 'OSM_MAPPED_TREE_CANOPIES';
  const object = new THREE.Object3D();
  visibleTrees.forEach(([x,z], index) => {
    const y = heightAt(x,z);
    object.position.set(x, y+4, z);
    object.updateMatrix();
    stems.setMatrixAt(index, object.matrix);
    object.position.set(x, y+14, z);
    object.updateMatrix();
    crowns.setMatrixAt(index, object.matrix);
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