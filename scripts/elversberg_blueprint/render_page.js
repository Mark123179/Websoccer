window.renderElversbergBlueprint = async function renderElversbergBlueprint({
  base, source, layers, evidence, camera: contractCamera, width, height,
}) {
  const THREE = await import('three');
  const { mountStudyModel } = await import(`${base}/static/stadium_editor/study_models.js?v=blueprint-export-check`);
  const { projectStudy } = await import(`${base}/static/stadium_editor/study_camera.js?v=1`);
  const { createStudyLighting } = await import(`${base}/static/stadium_editor/study_lighting.js?v=blueprint-export`);

  const turn = (point) => [-point[0], -point[1], ...point.slice(2)];
  const modelSource = structuredClone(source);
  // Cancel the study module's default Elversberg half-turn on a private source copy.
  modelSource.blocks.forEach((block) => { block.quad = block.quad.map(turn); });
  modelSource.outline = modelSource.outline.map(turn);
  modelSource.roof.segments.forEach((segment) => { segment.quad = segment.quad.map(turn); });
  modelSource.mainStand = 'NORD';
  modelSource.farStand = 'SUED';

  const handle = await mountStudyModel({
    host: document.getElementById('host'), club: 'elversberg', source: modelSource, concept: 'cutaway',
  });
  const { stage } = handle;
  const { renderer, camera: viewCamera, sceneRoot } = stage;
  renderer.setSize(width, height, false);
  renderer.setPixelRatio(1);
  if (renderer.toneMapping !== THREE.ACESFilmicToneMapping) {
    throw new Error(`Expected original ACESFilmic daylight; got toneMapping=${renderer.toneMapping}.`);
  }
  const contractView = new THREE.Matrix4().fromArray(contractCamera.pose);
  viewCamera.matrixWorldInverse.copy(contractView);
  viewCamera.matrixWorld.copy(contractView).invert();
  viewCamera.matrixWorld.decompose(viewCamera.position, viewCamera.quaternion, viewCamera.scale);
  viewCamera.projectionMatrix.fromArray(contractCamera.projection);
  viewCamera.projectionMatrixInverse.copy(viewCamera.projectionMatrix).invert();
  // Freeze exact approved matrices so later Three.js updates cannot recompose them.
  viewCamera.matrixAutoUpdate = false;
  viewCamera.matrixWorldAutoUpdate = false;
  const actualView = viewCamera.matrixWorldInverse.elements.slice();
  const actualWorld = viewCamera.matrixWorld.elements.slice();
  const actualProjection = viewCamera.projectionMatrix.elements.slice();
  const worldFromContract = contractView.clone().invert().elements;
  const matrixMaxError = Math.max(
    ...actualView.map((value, i) => Math.abs(value - contractCamera.pose[i])),
    ...actualWorld.map((value, i) => Math.abs(value - worldFromContract[i])),
    ...actualProjection.map((value, i) => Math.abs(value - contractCamera.projection[i])),
  );
  const actualCorners = [[-52.5, -34], [52.5, -34], [52.5, 34], [-52.5, 34]]
    .map(([x, z]) => projectStudy(viewCamera, width, height, x, z));
  const cornersMaxErrorPx = Math.max(...actualCorners.flatMap((point, i) =>
    ['x', 'y'].map((axis) => Math.abs(point[axis] - contractCamera.corners[i][axis]))));
  if (matrixMaxError > 1e-12) throw new Error(`Rendered camera matrices differ from contract (${matrixMaxError}).`);
  if (cornersMaxErrorPx > 1e-7) throw new Error(`Rendered field corners differ from contract (${cornersMaxErrorPx}px).`);

  const lighting = createStudyLighting(handle, null);
  lighting.setState(false, false, false);
  sceneRoot.background = new THREE.Color('#071b1d');
  renderer.setClearColor('#071b1d', 1);

  function makeShape(points) {
    const shape = new THREE.Shape();
    points.forEach(([x, z], index) => index ? shape.lineTo(x, -z) : shape.moveTo(x, -z));
    shape.closePath();
    return shape;
  }
  function polygon(points, color, y, opacity = 1) {
    const geometry = new THREE.ShapeGeometry(makeShape(points));
    geometry.rotateX(-Math.PI / 2);
    return positioned(new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color, transparent: opacity < 1, opacity, depthWrite: opacity >= 1,
      side: THREE.DoubleSide, toneMapped: false,
    })), y);
  }
  function positioned(object, y) { object.position.y = y; return object; }
  function groundPlane() {
    const ground = positioned(new THREE.Mesh(new THREE.PlaneGeometry(2200, 2200),
      new THREE.MeshBasicMaterial({ color: '#081b1d', toneMapped: false })), -1.2);
    ground.rotation.x = -Math.PI / 2;
    return ground;
  }
  function groundPolygon(points, color, y) { return polygon(points, color, y); }
  function outline(points, color, opacity, y) {
    const geometry = new THREE.BufferGeometry().setFromPoints(
      [...points, points[0]].map(([x, z]) => new THREE.Vector3(x, y, z)));
    return new THREE.LineLoop(geometry, new THREE.LineBasicMaterial({
      color, transparent: opacity < 1, opacity, toneMapped: false,
    }));
  }
  function extrudedBuilding(building) {
    const geometry = new THREE.ExtrudeGeometry(makeShape(building.poly), {
      depth: building.height, bevelEnabled: false, steps: 1,
    });
    geometry.rotateX(-Math.PI / 2);
    const mesh = positioned(new THREE.Mesh(geometry, [
      // Blueprint fills carry deliberate top/side contrast, not photographic
      // lighting. This avoids black facades without changing stadium daylight.
      new THREE.MeshBasicMaterial({ color: '#1b4249', side: THREE.DoubleSide, toneMapped: false }),
      new THREE.MeshBasicMaterial({ color: '#102d35', side: THREE.DoubleSide, toneMapped: false }),
    ]), -0.84);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 24),
      new THREE.LineBasicMaterial({ color: '#22e6ff', transparent: true, opacity: 0.20, toneMapped: false }));
    edges.position.copy(mesh.position);
    edges.position.y += 0.012;
    edges.renderOrder = 2;
    return [mesh, edges];
  }
  function addMapLayers(style) {
    const group = new THREE.Group();
    group.add(groundPlane());
    for (const area of layers.green) {
      group.add(groundPolygon(area.poly, style === 'spatial' ? '#12372c' : '#123a2d', -0.96));
    }
    for (const road of layers.roads) {
      group.add(groundPolygon(road.poly, style === 'spatial' ? '#102b2e' : '#123438', -0.91));
      if (style === 'flat') group.add(outline(road.poly, '#28535a', 0.32, -0.88));
    }
    for (const building of layers.buildings) {
      if (style === 'spatial') {
        extrudedBuilding(building).forEach((object) => group.add(object));
      } else {
        group.add(polygon(building.poly, '#102b2c', -0.87, 0.84));
        group.add(outline(building.poly, '#28616a', 0.62, -0.82));
      }
    }
    return group;
  }
  function pngData() { return handle.canvas.toDataURL('image/png'); }
  function renderPng() {
    renderer.render(sceneRoot, viewCamera);
    const glError = renderer.getContext().getError();
    if (glError !== renderer.getContext().NO_ERROR) throw new Error(`WebGL render error ${glError}.`);
    return pngData();
  }
  function captureMask(selectedMeshes = null) {
    const saved = [];
    const priorBackground = sceneRoot.background;
    const priorClearColor = renderer.getClearColor(new THREE.Color());
    const priorClearAlpha = renderer.getClearAlpha();
    const priorToneMapping = renderer.toneMapping;
    const priorExposure = renderer.toneMappingExposure;
    sceneRoot.traverse((object) => {
      if (!object.isMesh) return;
      const materialSet = Array.isArray(object.material) ? object.material : [object.material];
      saved.push([object, object.material, object.visible]);
      const maskMaterial = (material) => new THREE.MeshBasicMaterial({
        color: 0xffffff, side: material.side, visible: material.visible,
        clippingPlanes: material.clippingPlanes, clipIntersection: material.clipIntersection,
        toneMapped: false,
      });
      object.material = Array.isArray(object.material) ?
        object.material.map(maskMaterial) : maskMaterial(object.material);
      object.visible = saved[saved.length - 1][2] &&
        (!selectedMeshes || selectedMeshes.has(object));
    });
    sceneRoot.background = new THREE.Color('#000000');
    renderer.setClearColor('#000000', 1);
    // Diagnostic masks are unlit white; the real baseline keeps original ACESFilmic.
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.toneMappingExposure = 1;
    renderer.render(sceneRoot, viewCamera);
    const data = pngData();
    for (const [object, originalMaterial, originalVisible] of saved) {
      const current = Array.isArray(object.material) ? object.material : [object.material];
      current.forEach((material) => material.dispose());
      object.material = originalMaterial;
      object.visible = originalVisible;
    }
    sceneRoot.background = priorBackground;
    renderer.setClearColor(priorClearColor, priorClearAlpha);
    renderer.toneMapping = priorToneMapping;
    renderer.toneMappingExposure = priorExposure;
    return data;
  }
  const pitchMeshes = new Set();
  sceneRoot.traverse((object) => {
    if (object.isMesh && object.userData.studyPitch) pitchMeshes.add(object);
  });
  if (!pitchMeshes.size) throw new Error('Fresh study pitch mask is empty.');

  const states = [];
  for (const roof of [true, false]) {
    handle.setRoof(roof);
    const baseline = renderPng();
    const stadiumMask = captureMask();
    const fieldMask = captureMask(pitchMeshes);
    for (const style of ['spatial', 'flat']) {
      const environment = addMapLayers(style);
      sceneRoot.add(environment);
      const image = renderPng();
      sceneRoot.remove(environment);
      environment.traverse((object) => {
        object.geometry?.dispose();
        (Array.isArray(object.material) ? object.material : [object.material])
          .forEach((material) => material?.dispose());
      });
      states.push({
        style, roof, baseline, image, stadiumMask, fieldMask,
        projection: actualProjection, pose: actualView, corners: actualCorners,
      });
    }
  }
  lighting.dispose();
  handle.dispose();
  return {
    states,
    actualCamera: {
      projection: actualProjection, pose: actualView, worldPose: actualWorld,
      corners: actualCorners, cornersMaxErrorPx, matrixMaxError,
    },
    daylightToneMapping: 'ACESFilmicToneMapping',
    sourceEvidenceFrame: evidence.frame,
  };
};
