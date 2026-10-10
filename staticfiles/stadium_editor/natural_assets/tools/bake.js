import * as THREE from '../../stage/vendor/three.module.js';
import {GLTFLoader} from '../vendor/GLTFLoader.js';

const side=256,atlasSide=side*8;
const recipes=[
  {directory:'realistic_trees_collection',root:'Tree_EZTree0Large',file:'realistic_oak_large_2048.webp',height:20,frame:21.6},
  {directory:'realistic_trees_collection',root:'Tree_EZTree0Medium010',file:'realistic_maple_medium_2048.webp',height:17,frame:18.4},
  {directory:'oak_trees',root:'treelarge',file:'oak_tree_large_2048.webp',height:19,frame:20.6},
  {directory:'various_forest_assets_pack',root:'Birch2_21',file:'forest_birch_2048.webp',height:19,frame:20.6},
  {directory:'various_forest_assets_pack',root:'Maple_24',file:'forest_maple_2048.webp',height:19,frame:20.6},
  {directory:'various_forest_assets_pack',root:'DeciduousShrub_27',file:'forest_deciduous_shrub_2048.webp',height:4.2,frame:5.2},
];
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,preserveDrawingBuffer:true,
  powerPreference:'high-performance'});
renderer.setSize(side,side,false);
renderer.setPixelRatio(1);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.05;
renderer.setClearColor(0x000000,0);
document.body.append(renderer.domElement);
const scene=new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xe8eee5,0x4d493c,1.25));
const sun=new THREE.DirectionalLight(0xfff3dc,2.15);
sun.position.set(-10,22,15);scene.add(sun);
const camera=new THREE.OrthographicCamera(-10.8,10.8,10.8,-10.8,.1,100);
const loader=new GLTFLoader();
const response=async(name,body,type='application/octet-stream')=>{
  const result=await fetch(`/__save/${encodeURIComponent(name)}`,{method:'POST',headers:{'Content-Type':type},body});
  if(!result.ok)throw new Error(`Asset output request failed: ${result.status} ${name}`);
};
const hemiDirection=(column,row)=>{
  let x=-1+(column+.5)*.25,z=-1+(row+.5)*.25,y=1-Math.abs(x)-Math.abs(z);
  if(y<0){const oldX=x;x=(1-Math.abs(z))*Math.sign(oldX||1);z=(1-Math.abs(oldX))*Math.sign(z||1);}
  return new THREE.Vector3(x,Math.abs(y),z).normalize();
};
const prepareTree=(root,heightMeters=19)=>{
  root.updateMatrixWorld(true);
  const bounds=new THREE.Box3().setFromObject(root);
  const dimensions=bounds.getSize(new THREE.Vector3());
  if(!Number.isFinite(dimensions.y)||dimensions.y<.01)throw new Error('Tree object has invalid dimensions.');
  const center=bounds.getCenter(new THREE.Vector3());
  const scale=heightMeters/dimensions.y;
  const normalization=new THREE.Matrix4().makeScale(scale,scale,scale)
    .multiply(new THREE.Matrix4().makeTranslation(-center.x,-bounds.min.y,-center.z));
  const prepared=new THREE.Group();
  root.traverse(object=>{
    if(!object.isMesh||!object.geometry?.attributes?.position)return;
    const geometry=object.geometry.clone();
    geometry.applyMatrix4(object.matrixWorld);
    geometry.applyMatrix4(normalization);
    const material=Array.isArray(object.material)
      ? object.material.map(source=>{const clone=source.clone();clone.side=THREE.DoubleSide;return clone;})
      : object.material.clone();
    if(Array.isArray(material))material.forEach(item=>{item.side=THREE.DoubleSide;});
    else material.side=THREE.DoubleSide;
    const mesh=new THREE.Mesh(geometry,material);
    prepared.add(mesh);
  });
  return prepared;
};
async function run(){
  const results=[];
  for(const recipe of recipes){
    const {directory,root:rootName,file:filename,height,frame}=recipe;
    const url=`/natural_assets/models/${directory}/scene.gltf`;
    const gltf=await loader.loadAsync(url);
    const source=gltf.scene.getObjectByName(rootName);
    if(!source) {
      const names=[];gltf.scene.traverse(object=>{if(object.name)names.push(object.name);});
      throw new Error(`Source model node unavailable: ${directory}/${rootName}; scene objects: ${names.slice(0,45).join(', ')}`);
    }
    const tree=prepareTree(source,height);
    scene.add(tree);
    const atlas=document.createElement('canvas');atlas.width=atlas.height=atlasSide;
    const context=atlas.getContext('2d',{willReadFrequently:false});
    for(let row=0;row<8;row++)for(let column=0;column<8;column++){
      const direction=hemiDirection(column,row);
      camera.position.copy(direction).multiplyScalar(frame*2);
      camera.up.set(Math.abs(direction.y)>.985?0:0,Math.abs(direction.y)>.985?0:1,
        Math.abs(direction.y)>.985?1:0);
      camera.lookAt(0,height*.5,0);
      camera.updateMatrixWorld(true);
      renderer.render(scene,camera);
      context.drawImage(renderer.domElement,column*side,(7-row)*side,side,side);
    }
    const blob=await new Promise(resolve=>atlas.toBlob(resolve,'image/webp',.91));
    if(!blob)throw new Error(`Atlas encoding failed for ${filename}`);
    await response(filename,blob,'image/webp');
    results.push({file:filename,width:atlasSide,height:atlasSide,bytes:blob.size,
      source:`${directory}/${rootName}`,views:64,format:'RGBA WebP alpha'});
    tree.traverse(object=>{
      object.geometry?.dispose();
      if(Array.isArray(object.material))object.material.forEach(material=>material.dispose());
      else object.material?.dispose();
    });
    scene.remove(tree);
    gltf.scene.traverse(object=>object.geometry?.dispose?.());
  }
  await response('bake-manifest.json',JSON.stringify({generator:'local Three.js r170 + GLTFLoader',
    createdAt:new Date().toISOString(),atlasSize:2048,viewLayout:'8x8 hemi-octahedron',results},null,2),
    'application/json');
  window.atlasBakeDone=true;
  document.body.dataset.state='complete';
}
run().catch(error=>{
  console.error(error);
  window.atlasBakeError=error.stack||error.message;
  document.body.dataset.state='error';
});
