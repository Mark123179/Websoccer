import * as THREE from 'three';

export function addStudyGoals(root) {
  const goals = new THREE.Group();
  const material = new THREE.MeshLambertMaterial({color:'#eeeeee'});
  function pole(from, to) {
    const a=new THREE.Vector3(...from),b=new THREE.Vector3(...to),length=a.distanceTo(b);
    const mesh=new THREE.Mesh(new THREE.CylinderGeometry(.06,.06,length,6),material);
    mesh.position.copy(a).lerp(b,.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.clone().sub(a).normalize());
    mesh.userData.studyPitch=true;goals.add(mesh);
  }
  for(const sign of [-1,1]) {
    const line=sign*52.5,back=sign*54.1;
    for(const z of [-3.66,3.66]) {
      pole([line,0,z],[line,2.44,z]);
      pole([line,2.44,z],[back,.05,z]);
      pole([line,.05,z],[back,.05,z]);
    }
    pole([line,2.44,-3.66],[line,2.44,3.66]);
    pole([back,.05,-3.66],[back,.05,3.66]);
  }
  root.add(goals);
  return goals;
}
