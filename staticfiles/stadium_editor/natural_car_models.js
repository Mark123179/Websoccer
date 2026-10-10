function eachMaterial(value, callback) {
  if (Array.isArray(value)) value.forEach(callback);
  else if (value) callback(value);
}

export function createCarResourceDisposer({
  gltf, getGltf, destination, records = [], clonedGeometries = new Set(),
  clonedMaterials = new Set(), textureRegistry = new Set(),
}) {
  let disposed = false;
  return () => {
    if (disposed) return;
    disposed = true;
    const geometries = new Set(clonedGeometries);
    const materials = new Set(clonedMaterials);
    const textures = new Set(textureRegistry);
    const collectMaterial = material => {
      if (!material) return;
      materials.add(material);
      Object.values(material).forEach(value => {
        if (value?.isTexture) textures.add(value);
      });
    };
    (getGltf?.() || gltf)?.scene?.traverse(object => {
      if (object.geometry) geometries.add(object.geometry);
      eachMaterial(object.material, collectMaterial);
    });
    records.forEach(({mesh}) => {
      destination?.remove(mesh);
      if (mesh.geometry) geometries.add(mesh.geometry);
      eachMaterial(mesh.material, collectMaterial);
    });
    textures.forEach(texture => texture.dispose?.());
    materials.forEach(material => material.dispose?.());
    geometries.forEach(geometry => geometry.dispose?.());
    textureRegistry.clear();
    clonedGeometries.clear();
    clonedMaterials.clear();
    records.length = 0;
  };
}

export function createCarShadowProxyGeometry(THREE, sourceSize) {
  return new THREE.BoxGeometry(
    Math.max(.25, sourceSize.x),
    .42,
    Math.max(.25, sourceSize.z),
  );
}

export async function loadInstancedCars(THREE, root, placements, source, destination) {
  if (!source?.gltf || !source?.credit) throw new Error('Car model provenance is missing.');
  const {GLTFLoader} = await import('./natural_assets/vendor/GLTFLoader.js?v=3');
  const manager = new THREE.LoadingManager();
  const textureRegistry = manager.naturalTextureRegistry = new Set();
  const loader = new GLTFLoader(manager);
  const variants = new Map();
  const records = [];
  const clonedGeometries = new Set();
  const clonedMaterials = new Set();
  let gltf = null;
  const disposeResources = createCarResourceDisposer({
    getGltf: () => gltf, destination, records, clonedGeometries, clonedMaterials, textureRegistry,
  });
  try {
    gltf = await loader.loadAsync(new URL(source.gltf, root).href);
    gltf.scene.updateMatrixWorld(true);
    const vehicleNames = (source.models || []).map(name =>
      String(name).replace(/[^A-Za-z0-9]+/g,'_').replace(/^_|_$/g,''));
    const wheelMeshes=[];
    gltf.scene.traverse(object=>{
      if(!object.isMesh||!/^Wheel[_ ]/.test(object.name||''))return;
      const box=new THREE.Box3().setFromObject(object);
      wheelMeshes.push({object,center:box.getCenter(new THREE.Vector3())});
    });
    for (const name of vehicleNames) {
      const group = gltf.scene.getObjectByName(name);
      if (!group) continue;
      const carBounds=new THREE.Box3().setFromObject(group);
      const origin=carBounds.getCenter(new THREE.Vector3());
      const carLength=Math.max(carBounds.max.x-carBounds.min.x,carBounds.max.z-carBounds.min.z);
      const scale=4.45/Math.max(carLength,.01);
      const sourceSize=carBounds.getSize(new THREE.Vector3()).multiplyScalar(scale);
      const meshes = [];
      const include = new Set();
      group.traverse(object=>{if(object.isMesh)include.add(object);});
      wheelMeshes.map(item=>({...item,distance:item.center.distanceTo(origin)}))
        .sort((a,b)=>a.distance-b.distance).slice(0,4).forEach(item=>include.add(item.object));
      gltf.scene.traverse(object => {
        if(!include.has(object))return;
        if (object.isMesh && object.geometry?.attributes?.position) {
          const geometry = object.geometry.clone();
          clonedGeometries.add(geometry);
          geometry.applyMatrix4(object.matrixWorld);
          const transform=new THREE.Matrix4().makeScale(scale,scale,scale)
            .multiply(new THREE.Matrix4().makeTranslation(-origin.x,-origin.y,-origin.z));
          geometry.applyMatrix4(transform);
          meshes.push({geometry,material:object.material});
        }
      });
      if (meshes.length) {
        const lowest=Math.min(...meshes.map(({geometry})=>{
          geometry.computeBoundingBox();
          return geometry.boundingBox.min.y;
        }));
        const shadowGeometry=createCarShadowProxyGeometry(THREE,sourceSize);
        clonedGeometries.add(shadowGeometry);
        variants.set(name,{meshes,bottom:lowest,shadowGeometry});
      }
    }
    if (!variants.size) throw new Error('The local passenger-car source model has no usable vehicle nodes.');
    const variantNames = [...variants.keys()];
    const shadowMaterial=new THREE.MeshBasicMaterial({color:'#000000',colorWrite:false,
      depthWrite:false,depthTest:false,toneMapped:false});
    clonedMaterials.add(shadowMaterial);
    placements.forEach(placement => {
      const name = variantNames[placement.type % variantNames.length];
      const variant=variants.get(name);
      const shadowKey=`shadow:${name}`;
      let shadowRecord=records.find(item=>item.key===shadowKey);
      if(!shadowRecord){
        const mesh=new THREE.InstancedMesh(variant.shadowGeometry,shadowMaterial,placements.length);
        mesh.name=`NATURAL_PARKED_CAR_SHADOWS_${name}`;
        mesh.castShadow=true;mesh.receiveShadow=false;
        shadowRecord={key:shadowKey,mesh,count:0};records.push(shadowRecord);
        destination.add(mesh);
      }
      const shadowMatrix=new THREE.Matrix4();
      const shadowRotation=new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(0,1,0),placement.yaw);
      const shadowPosition=new THREE.Vector3(placement.x,-.24+.21,placement.z);
      shadowMatrix.compose(shadowPosition,shadowRotation,new THREE.Vector3(1,1,1));
      shadowRecord.mesh.setMatrixAt(shadowRecord.count++,shadowMatrix);
      for (const [partIndex, part] of variant.meshes.entries()) {
        const key = `${name}:${partIndex}`;
        let record = records.find(item => item.key === key);
        if (!record) {
          const mesh = new THREE.InstancedMesh(part.geometry, part.material, placements.length);
          mesh.name = `NATURAL_PARKED_CARS_${key}`;
          mesh.castShadow = false; mesh.receiveShadow = true;
          record = {key, mesh, count:0}; records.push(record);
          destination.add(mesh);
        }
        const matrix = new THREE.Matrix4();
        const quaternion = new THREE.Quaternion().setFromAxisAngle(
          new THREE.Vector3(0,1,0),placement.yaw);
        const position = new THREE.Vector3(placement.x,-.24-variant.bottom,placement.z);
        const scale = new THREE.Vector3(.92,.92,.92);
        matrix.compose(position,quaternion,scale);
        record.mesh.setMatrixAt(record.count++,matrix);
      }
    });
    records.forEach(record => {record.mesh.count=record.count;record.mesh.instanceMatrix.needsUpdate=true;});
    return {dispose: disposeResources};
  } catch (error) {
    disposeResources();
    throw error;
  }
}
