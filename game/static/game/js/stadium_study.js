import * as THREE from 'three';
import {mountStudyModel, disposeStudySourceCache} from '../../stadium_editor/study_models.js?v=3';
import {createStudyLighting} from '../../stadium_editor/study_lighting.js?v=3';
import {applyStudyCamera, projectStudy, STUDY_FRAME} from '../../stadium_editor/study_camera.js?v=1';

const config = JSON.parse(document.getElementById('stadium-study-config').textContent);
const control = id => document.getElementById(`study-${id}`);
const entries = [], concept = control('concept');
let disposed = false, animation = 0, paused = false, elapsed = 0, previous = null;
const pitchPoints = [[-52.5,-34],[52.5,-34],[52.5,34],[-52.5,34]];
const basePlayers = [[-47,0],[-31,-23],[-31,-8],[-31,8],[-31,23],
  [-13,-22],[-13,-7],[-13,9],[-13,22],[10,-10],[10,10]];
function actors() {
  const phase = Math.sin(elapsed * .5);
  return {
    players: [0,1].flatMap(team => basePlayers.map(([x,y], index) => ({
      x: (team ? -x : x) + (index ? phase * 2 : 0), y,
      team, number: index + 1,
    }))),
    ball: {x: Math.sin(elapsed * .65) * 20, y: Math.sin(elapsed * .4) * 14},
  };
}
function updateProjection(entry) {
  const width = entry.host.clientWidth, height = entry.host.clientHeight;
  if (!width || !height) return;
  entry.width = width; entry.height = height;
  entry.handle.stage.renderer.setSize(width, height, false);
  entry.overlay.width = width; entry.overlay.height = height;
  applyStudyCamera(entry.handle.stage.camera, concept.value, width, height);
  entry.project = (x,y,z=0) => projectStudy(entry.handle.stage.camera,width,height,x,y,z);
  entry.host.dataset.fieldCorners = JSON.stringify(pitchPoints.map(([x,y]) => entry.project(x,y)));
  entry.handle.stage.render();
  drawActors(entry);
}
function drawActors(entry) {
  const ctx = entry.overlay.getContext('2d');
  ctx.clearRect(0,0,entry.width,entry.height);
  if (!control('demo').checked || !entry.project) return;
  const data = actors();
  for (const player of data.players) {
    const p = entry.project(player.x,player.y,.75);
    const radius = Math.max(3,entry.width / STUDY_FRAME[0] * 10);
    ctx.fillStyle = player.team ? '#e9f2f6' : '#efc438';
    ctx.strokeStyle = '#07131c'; ctx.lineWidth = 1.2;
    ctx.beginPath();ctx.arc(p.x,p.y,radius,0,Math.PI*2);ctx.fill();ctx.stroke();
    if (entry.width > 700) {
      ctx.font = 'bold 8px sans-serif';ctx.textAlign='center';
      ctx.fillStyle = '#0a141d';ctx.fillText(player.number,p.x,p.y+2.5);
    }
  }
  const point = entry.project(data.ball.x,data.ball.y,.3);
  ctx.fillStyle = '#ffffff';ctx.strokeStyle='#07131c';ctx.lineWidth=1;
  ctx.beginPath();ctx.arc(point.x,point.y,Math.max(2,entry.width/600),0,Math.PI*2);ctx.fill();ctx.stroke();
  entry.host.dataset.ball = JSON.stringify({world:data.ball,screen:point});
}
function status(entry) {
  const night = control('night').checked, count = entry.lighting.verifiedCount;
  const light = count ? `${count} belegte Modellleuchten · ${entry.lighting.sources.length} repräsentative Quellen` :
    'Flutlicht unbelegt — kein Ersatzlicht';
  entry.status.textContent = `${night ? 'Nacht' : 'Tag'} · 105×68 m · Flutlicht ${control('floodlight').checked?'an':'aus'} · ${light}`;
  entry.host.dataset.night = String(night);
  entry.host.dataset.fixtureCount = String(count);
  entry.host.dataset.lightSources = JSON.stringify(entry.lighting.selected.map(source => ({
    id:source.id,position:source.position,direction:source.direction,representedIds:source.representedIds,
  })));
}
function refresh() {
  entries.forEach(entry => {
    entry.handle.setRoof(control('roof').checked);
    entry.lighting.setState(control('night').checked,control('lights').checked,
      control('floodlight')?.checked ?? true);
    status(entry);updateProjection(entry);
  });
  if (entries.length === 2) {
    const a = JSON.parse(entries[0].host.dataset.fieldCorners);
    const b = JSON.parse(entries[1].host.dataset.fieldCorners);
    const residual = Math.max(...a.map((p,i) => Math.hypot(p.x / entries[0].width - b[i].x / entries[1].width,
      p.y / entries[0].height - b[i].y / entries[1].height)));
    document.body.dataset.fieldParity = String(residual);
    if (residual > 1e-9) throw new Error('Die Feldprojektionen der Vereine unterscheiden sich.');
  }
}
function tick(time) {
  if (disposed) return;
  if (previous !== null && !paused) elapsed += Math.min((time-previous)/1000,.1);
  previous = time;
  if (!paused) entries.forEach(drawActors);
  animation = requestAnimationFrame(tick);
}
async function init() {
  let fixtureData;
  try {
    const response = await fetch(config.lightsUrl);
    if (!response.ok) throw new Error('Leuchtendeklaration fehlt.');
    fixtureData = await response.json();
    if (!Array.isArray(fixtureData.verifiedFixtures)) throw new Error('Leuchtendeklaration ungültig.');
  } catch (error) {
    // Explicit incomplete evidence, never anonymous floodlights.
    fixtureData = {verifiedFixtures: [], unavailable: error.message};
  }
  for (const club of ['dortmund','elversberg']) {
    const host = control(club), label = control(`${club}-status`);
    try {
      const handle = await mountStudyModel({host,club,source:config.elversberg,concept:concept.value});
      if (disposed) { handle.dispose(); return; }
      const overlay = document.createElement('canvas');
      overlay.className = 'ss-demo-overlay';overlay.setAttribute('aria-hidden','true');
      Object.assign(overlay.style,{position:'absolute',inset:'0',width:'100%',height:'100%',pointerEvents:'none'});
      host.append(overlay);
      const entry = {host,status:label,handle,overlay,
        lighting:createStudyLighting(handle,club==='dortmund'?fixtureData:null)};
      if(club==='dortmund'&&fixtureData.verifiedFixtures.length) {
        const details=document.createElement('details'),summary=document.createElement('summary');
        summary.textContent=`Quellnachweise: ${fixtureData.verifiedFixtures.length} Leuchten · ${entry.lighting.sources.length} Laufzeitquellen`;
        details.append(summary);
        const list=document.createElement('div');
        Object.assign(list.style,{maxHeight:'240px',overflow:'auto',fontSize:'11px',lineHeight:'1.6'});
        const legend=document.createElement('p');
        legend.textContent='Cyan = deklarierte Modellleuchte, Gelb = Gruppenrepräsentant. Lichtkegel gehören zu den Laufzeitquellen. Die kameraseitige Tribüne ist nur ausgeblendet: Ihre Leuchten bleiben aktiv und können sich vor das Feld projizieren, obwohl ihre Montagepunkte oberhalb der Tribüne liegen.';
        list.append(legend);
        for(const fixture of fixtureData.verifiedFixtures) {
          const group=entry.lighting.selected.find(source=>source.representedIds.includes(fixture.id));
          const line=document.createElement('p');
          line.textContent=`${fixture.name} · Light-ID ${fixture.id} · ${fixture.nearestLampMesh.mesh} · Modellpunkt ${fixture.position.map(v=>v.toFixed(2)).join(' / ')} m · Achse ${fixture.direction.map(v=>v.toFixed(2)).join(' / ')} · Kegel ${fixture.angle.toFixed(1)}° · Gruppe ${group?.id}`;
          list.append(line);
        }
        details.append(list);
        Object.assign(details.style,{padding:'12px 16px',color:'#a7bdc8',fontSize:'12px'});
        label.after(details);
      }
      if (fixtureData.unavailable && club==='dortmund') label.dataset.evidenceError=fixtureData.unavailable;
      entries.push(entry);refresh();
    } catch (error) {
      label.textContent=`Vorschau nicht verfügbar: ${error.message}`;
      host.dataset.error=error.message;
    }
  }
  const observer = new ResizeObserver(() => {if(!disposed)refresh();});
  entries.forEach(entry => observer.observe(entry.host));
  for (const id of ['concept','roof','night','lights','demo','floodlight']) control(id)?.addEventListener('change',refresh);
  control('pause').addEventListener('click',() => {
    paused=!paused;control('pause').textContent=paused?'Fortsetzen':'Pause';
    control('pause').setAttribute('aria-pressed',String(paused));
  });
  control('export-reference').addEventListener('click',() => exportImage(false));
  control('export-mask').addEventListener('click',() => exportImage(true));
  document.body.dataset.studyReady = String(entries.length);
  animation=requestAnimationFrame(tick);
  window.addEventListener('pagehide',() => {
    disposed=true;cancelAnimationFrame(animation);observer.disconnect();
    entries.forEach(entry => {entry.lighting.dispose();entry.handle.dispose();entry.overlay.remove();});
    disposeStudySourceCache();
  },{once:true});
}
function exportImage(mask) {
  const entry=entries[0];
  if(!entry) return;
  const {stage}=entry.handle, saved=[], replacements=new Set();
  const background=stage.sceneRoot.background;
  stage.renderer.setSize(...STUDY_FRAME,false);
  applyStudyCamera(stage.camera,concept.value,...STUDY_FRAME);
  const diagnostics=stage.sceneRoot.children.filter(o=>o.isGroup&&o!==entry.handle.model);
  const diagnosticState=diagnostics.map(o=>[o,o.visible]);
  if(mask) {
    stage.sceneRoot.background=new THREE.Color('#000000');
    diagnostics.forEach(o=>{o.visible=false;});
    stage.sceneRoot.traverse(object=>{
      if(!object.isMesh)return;
      const list=Array.isArray(object.material)?object.material:[object.material];
      saved.push({object,material:object.material,visible:object.visible});
      if(object.userData.studyPitch) {object.visible=false;return;}
      object.material=list.map(original=>{
        const material=new THREE.MeshBasicMaterial({color:'#ffffff',side:THREE.DoubleSide,
          clippingPlanes:original.clippingPlanes,depthTest:true});
        replacements.add(material);return material;
      });
    });
  }
  try {
    stage.render();
    const link=document.createElement('a');
    link.download=`dortmund-${concept.value}-${mask?'stadionmaske':'kamerareferenz'}.png`;
    link.href=entry.handle.canvas.toDataURL('image/png');link.click();
  } finally {
    saved.forEach(({object,material,visible})=>{object.material=material;object.visible=visible;});
    diagnosticState.forEach(([object,visible])=>{object.visible=visible;});
    stage.sceneRoot.background=background;
    replacements.forEach(material=>material.dispose());
    updateProjection(entry);
  }
}
init().catch(error=>{
  entries.forEach(entry=>{entry.status.textContent=error.message;});
  console.error(error);
});
