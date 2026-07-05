/* ============================================================
   STADIONUMFELD — 1:1 Vanilla-JS-Port des Replit-Design-Exports
   "Vereinsumfeld & Stadion".

   Die komplette DCLogic (Konstanten + Methoden) ist wortgetreu
   übernommen; nur die Laufzeit-Anbindung wurde ersetzt:
     - React-Lifecycle  ->  winziger setState/render-Loop
     - localStorage     ->  Server-Singleton (nur Admin schreibt)
     - url('assets/…')  ->  Django-Static-Basis

   Admin (Superuser): volle interaktive Bearbeitung (Editor-Leiste),
   Änderungen werden GLOBAL im Server-Singleton gespeichert.
   Nicht-Admin: reine Ansicht der globalen Szene, ohne Editor-Leiste.
   ============================================================ */
(function () {
  'use strict';

  var ASSET_BASE = window.__VU_ASSET_BASE__ || '/static/game/images/stadionumfeld/';
  var IS_ADMIN   = !!window.__VU_IS_ADMIN__;
  var SAVE_URL   = window.__VU_SAVE_URL__ || '';
  var CSRF       = window.__VU_CSRF__ || '';

  /* ---- tiny hyperscript ------------------------------------------- */
  function camel(k){ return k.replace(/[A-Z]/g, function(m){ return '-' + m.toLowerCase(); }); }
  function styleToCss(o){
    if (o == null) return '';
    if (typeof o === 'string') return o;
    var out = '';
    for (var k in o){
      if (!Object.prototype.hasOwnProperty.call(o, k)) continue;
      var v = o[k];
      if (v == null) continue;
      out += camel(k) + ':' + v + ';';
    }
    return out;
  }
  function h(tag, attrs, kids){
    var e = document.createElement(tag);
    attrs = attrs || {};
    for (var k in attrs){
      if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
      var v = attrs[k];
      if (v == null) continue;
      if      (k === 'style')    e.style.cssText = styleToCss(v);
      else if (k === 'onClick')  e.addEventListener('click', v);
      else if (k === 'onDown')   e.addEventListener('pointerdown', v);
      else if (k === 'onInput')  e.addEventListener('input', v);
      else if (k === 'onChange') e.addEventListener('change', v);
      else if (k === 'text')     e.textContent = v;
      else if (k === 'html')     e.innerHTML = v;
      else if (k === 'ref')      v(e);
      else if (k === 'value')    e.value = v;
      else                       e.setAttribute(k, v);
    }
    if (kids != null){
      (Array.isArray(kids) ? kids : [kids]).forEach(function (c){
        if (c == null || c === false) return;
        e.appendChild((typeof c === 'string' || typeof c === 'number') ? document.createTextNode('' + c) : c);
      });
    }
    return e;
  }

  var LBL5 = { fontSize:'10px', color:'var(--faint)', fontWeight:'800', letterSpacing:'.4px', marginBottom:'5px' };
  var LBL3 = { fontSize:'10px', color:'var(--faint)', fontWeight:'800', letterSpacing:'.4px', marginBottom:'3px' };

  /* ================================================================
     COMPONENT
     ================================================================ */
  class VU {
    constructor(mount){
      this.mount = mount;
      this.props = { buildDays: 7 };

      this.tiers = [
        {t:0,name:'Standard',short:'ST',min:0,cap:'10.000 oder weniger'},
        {t:1,name:'Stadion 1',short:'S1',min:30000,cap:'ab 30.000'},
        {t:2,name:'Stadion 2',short:'S2',min:60000,cap:'ab 60.000'},
        {t:3,name:'Stadion 3',short:'S3',min:80000,cap:'ab 80.000'},
        {t:4,name:'Stadion 4',short:'S4',min:100000,cap:'ab 100.000'}
      ];
      this.PLOTS = [
        {id:'nlz',num:2,name:'NLZ',short:'NLZ',kind:'facility',max:3,purpose:'Nachwuchs-Talente entwickeln',baufeld:'baufeld1.png',assets:{'1':'nlz1.png','1+':'nlz1plus.png','2':'nlz2.png','2+':'nlz2plus.png','3':'nlz3.png','bau':'nlz_bau.png'}},
        {id:'training',num:1,name:'Trainingsgelände',short:'Training',kind:'facility',max:3,purpose:'Trainingsqualität steigern',baufeld:'baufeld2.png',assets:{'1':'training1.png','1+':'training1plus.png','2':'training2.png','2+':'training2plus.png','3':'training3.png','bau':'training_bau.png'}},
        {id:'geschaeft',num:4,name:'Geschäftsstelle',short:'Geschäft',kind:'facility',max:3,purpose:'Sponsoren & Verwaltung',baufeld:'baufeld3.png',assets:{'1':'geschaeft1.png','1+':'geschaeft1plus.png','2':'geschaeft2.png','2+':'geschaeft2plus.png','3':'geschaeft3.png','bau':'geschaeft_bau.png'}},
        {id:'scouting',num:5,name:'Scoutingabteilung',short:'Scouting',kind:'facility',max:3,purpose:'Spieler weltweit sichten',baufeld:'baufeld4.png',assets:{'1':'scouting1.png','1+':'scouting1plus.png','2':'scouting2.png','2+':'scouting2plus.png','3':'scouting3.png','bau':'scouting_bau.png'}},
        {id:'medizin',num:3,name:'Medizinische Abteilung',short:'Medizin',kind:'facility',max:3,purpose:'Heilung & Reha',baufeld:'baufeld5.png',assets:{'1':'medizin1.png','1+':'medizin1plus.png','2':'medizin2.png','2+':'medizin2plus.png','3':'medizin3.png','bau':'medizin_bau.png'},note:'Bilder vorhanden: Stufe 1. Stufe 1+/2/2+/3 folgen.'},
        {id:'frei',num:6,name:'Freies Baufeld',short:'Frei',kind:'reserve',max:1,purpose:'Reserviert für künftigen Ausbau',baufeld:'baufeld6.png',assets:{'bau':'frei_bau.png'},note:'Noch keiner Facility zugeordnet — Bauplatz frei.'},
        {id:'stadion',num:0,name:'Stadion',short:'Stadion',kind:'stadium',max:4,purpose:'Zuschauer & Spieltags-Einnahmen',assets:{'0+':'stadion0plus.png','1':'stadion1.png','1+':'stadion1plus.png','2':'stadion2.png','2+':'stadion2plus.png','3':'stadion3.png','4':'stadion4.png'},note:'Standard ist im Umfeld-Hintergrund. Stadion 3→4: + Baubild folgt.'}
      ];
      this.defPos = {
        training:{x:70,y:21,s:26}, nlz:{x:83,y:45,s:27}, medizin:{x:76,y:80,s:26},
        geschaeft:{x:45,y:81,s:26}, scouting:{x:25,y:69,s:26}, frei:{x:30,y:37,s:24}, stadion:{x:53,y:45,s:30}
      };
      // Fest gespeicherte Kalibrierung (verbatim aus dem Design-Export):
      this.BAKED_POS = {"training":{"x":70,"y":21,"s":26},"nlz":{"x":83,"y":45,"s":27},"medizin":{"x":76,"y":80,"s":26},"geschaeft":{"x":45,"y":81,"s":26},"scouting":{"x":25,"y":69,"s":26},"frei":{"x":30,"y":37,"s":24},"stadion":{"x":53,"y":45,"s":30},"training|bau":{"x":69.80917987026771,"y":19.970229983921666,"s":20},"training|1":{"x":69.17310121672374,"y":18.678574057187873,"s":17,"rz":-3},"training|1+":{"x":69.08223481840655,"y":19.162944259825384,"s":17,"rz":-3},"training|2":{"x":69.26396761504094,"y":19.162944259825384,"s":17,"rz":-2},"training|2+":{"x":68.99136842008936,"y":19.324402020554768,"s":18,"rz":-3},"training|3":{"x":69.17310121672374,"y":19.324402020554768,"s":19,"rz":-2},"nlz|bau":{"x":79.62289647442256,"y":39.506548202512484,"s":13,"c4":[{"x":71.99000116052758,"y":30.949314599810858},{"x":86.12289647442256,"y":28.76859306499061},{"x":86.12289647442256,"y":50.244503340034356},{"x":73.12289647442256,"y":50.244503340034356}]},"nlz|1":{"x":78.44161943097544,"y":39.66800288369122,"s":18},"nlz|1+":{"x":78.71421862592702,"y":39.34508736223245,"s":17},"nlz|2":{"x":78.89595835522321,"y":39.506548202512484,"s":18},"nlz|2+":{"x":78.89595835522321,"y":39.82945756486996,"s":18},"nlz|3":{"x":79.25942394849199,"y":39.506548202512484,"s":17},"medizin|bau":{"x":73.89823018849769,"y":66.30843177886857,"s":20},"medizin|1":{"x":73.35301793327092,"y":69.69902935643243,"s":26},"medizin|1+":{"x":73.44389126424991,"y":68.7302889511574,"s":26},"medizin|2":{"x":73.44389126424991,"y":68.08445790823986,"s":26},"medizin|2+":{"x":74.07996298513207,"y":68.56883426997867,"s":26},"medizin|3":{"x":74.62516830769704,"y":65.01677585213476,"s":19,"rz":-10},"geschaeft|bau":{"x":47.72830537876113,"y":76.80315235122151,"s":24},"geschaeft|1":{"x":46.54702486898309,"y":76.80315235122151,"s":26},"geschaeft|1+":{"x":47.18309658986525,"y":75.99586662712524,"s":26},"geschaeft|2":{"x":48.00090804004361,"y":75.3500355842077,"s":26},"geschaeft|2+":{"x":48.00090804004361,"y":75.51149026538644,"s":26},"geschaeft|3":{"x":48.0917744383608,"y":75.83439962774392,"s":26},"scouting|bau":{"x":26.374374205950247,"y":60.65743171019457,"s":19},"scouting|1":{"x":26.646978600398185,"y":59.68869130491955,"s":20},"scouting|1+":{"x":26.646978600398185,"y":60.33451618873581,"s":20},"scouting|2":{"x":26.646978600398185,"y":58.71994474054324,"s":20},"scouting|2+":{"x":26.283507807633054,"y":59.04286026200201,"s":19},"scouting|3":{"x":26.737846731880833,"y":58.71994474054324,"s":20},"frei|bau":{"x":23.46660613066376,"y":29.65765867307706,"s":21},"stadion|0+":{"x":51.09041411146084,"y":40.79820412924628,"s":30},"stadion|1":{"x":51.09041411146084,"y":41.444029013062526,"s":30},"stadion|1+":{"x":51.54475303570861,"y":40.63674328896625,"s":30},"stadion|2":{"x":51.81735569699109,"y":40.95965881042502,"s":30},"stadion|2+":{"x":51.9082220953083,"y":40.475288607787505,"s":30},"stadion|3":{"x":51.36301677274332,"y":39.02217184077369,"s":30},"stadion|4":{"x":51.09041411146084,"y":39.02217184077369,"s":30}};
      this.BAKED_BADGES = {"training":{"x":58.63243956070773,"y":12.381746025146995},"nlz":{"x":88.2553360351303,"y":28.366002746343266},"medizin":{"x":86.347113939822,"y":67.92300322706112},"geschaeft":{"x":59.54111740920327,"y":87.78223080800942},"scouting":{"x":23.10313533789863,"y":75.83439962774392},"frei":{"x":12.289868420851949,"y":24.813944328499364},"stadion":{"x":63.35756159981987,"y":53.068944671869254}};

      var saved = this.load();
      this.state = Object.assign({
        screen:'overview', selected:'stadion', heimspiel:false, tod:'tag', wetter:'sommer', adjust:false,
        day:1, capacity:8000,
        levels:{nlz:2,training:2,geschaeft:1,scouting:0,medizin:1,frei:0},
        building:{nlz:null,training:null,geschaeft:null,scouting:{target:1,total:7,left:5},medizin:null,frei:null},
        positions:{}, badgePos:{}
      }, saved||{});
      this.state.positions = Object.assign(JSON.parse(JSON.stringify(this.defPos)), JSON.parse(JSON.stringify(this.BAKED_POS)), (saved&&saved.positions)||{});
      this.state.badgePos = Object.assign(JSON.parse(JSON.stringify(this.BAKED_BADGES)), (saved&&saved.badgePos)||{});
      if (!IS_ADMIN){ this.state.adjust = false; this.state.screen = 'overview'; }

      this.onMove = this.onMove.bind(this);
      this.onUp   = this.onUp.bind(this);
      this.hideImg = function(e){ if (e && e.target){ e.target.style.display = 'none'; } };
      this.ratios = {};
    }

    /* ---- lifecycle -------------------------------------------------- */
    init(){
      window.addEventListener('pointermove', this.onMove);
      window.addEventListener('pointerup', this.onUp);
      this.render();
      this.preloadRatios();
    }
    preloadRatios(){ var self=this; var seen={}; ['baustelle.png'].forEach(function(nm){ var u=self.url(nm); seen[u]=1; var im=new Image(); im.onload=function(){ self.ratios[u]=im.naturalWidth/im.naturalHeight; self.forceUpdate(); }; im.src=u; }); this.PLOTS.forEach(function(p){ var srcs=[]; if(p.baufeld) srcs.push(p.baufeld); var a=p.assets||{}; Object.keys(a).forEach(function(k){ srcs.push(a[k]); }); srcs.forEach(function(nm){ var u=self.url(nm); if(seen[u])return; seen[u]=1; var im=new Image(); im.onload=function(){ self.ratios[u]=im.naturalWidth/im.naturalHeight; if(self._rt)clearTimeout(self._rt); self._rt=setTimeout(function(){ self.forceUpdate(); },140); }; im.src=u; }); }); }

    /* ---- state ------------------------------------------------------ */
    load(){ var st = window.__VU_STATE__; return (st && typeof st === 'object' && !Array.isArray(st)) ? st : null; }
    save(){
      if (!IS_ADMIN || !SAVE_URL) return;
      var self=this;
      if (this._saveT) clearTimeout(this._saveT);
      this._saveT = setTimeout(function(){ self._doSave(); }, 400);
    }
    _doSave(){
      var s=this.state;
      var payload={ heimspiel:s.heimspiel, tod:s.tod, wetter:s.wetter, day:s.day, capacity:s.capacity, levels:s.levels, building:s.building, positions:s.positions, badgePos:s.badgePos, selected:s.selected };
      try{ fetch(SAVE_URL, { method:'POST', headers:{ 'Content-Type':'application/json', 'X-CSRFToken':CSRF }, credentials:'same-origin', body:JSON.stringify(payload) }).catch(function(){}); }catch(e){}
    }
    setState(patch, cb, mode){
      var np = (typeof patch === 'function') ? patch(this.state) : patch;
      if (np){ for (var k in np){ if (Object.prototype.hasOwnProperty.call(np, k)) this.state[k] = np[k]; } }
      if (mode === 'scene') this.refreshScene(); else this.render();
      if (cb) cb();
    }
    forceUpdate(){ this.render(); }
    set(p){ var self=this; this.setState(p, function(){ self.save(); }); }
    setFn(f){ var self=this; this.setState(f, function(){ self.save(); }); }
    commit(){ this.render(); this.save(); }

    /* ---- helpers (verbatim) ---------------------------------------- */
    bd(){ var v=parseInt(this.props.buildDays,10); return v>0?v:7; }
    enc(p){ return encodeURI(p).replace(/\+/g,'%2B'); }
    url(n){ return ASSET_BASE + n; }
    tierOf(c){ var t=0; for(var i=0;i<this.tiers.length;i++){ if(c>=this.tiers[i].min) t=this.tiers[i].t; } return t; }
    capForTier(t){ return [8000,30000,60000,80000,100000][t]; }
    toggleHeim(){ this.setFn(function(s){ return {heimspiel:!s.heimspiel}; }); }
    setTod(v){ this.set({tod:v}); }
    setWetter(v){ this.set({wetter:v}); }
    toggleAdjust(){ this.setFn(function(s){ return {adjust:!s.adjust}; }); }
    setCap(v){ this.setState({capacity:Math.max(0,Math.min(110000,parseInt(v,10)||0))}, null, 'scene'); }
    openDetail(id){ this.set({screen:'detail',selected:id}); }
    back(){ this.set({screen:'overview'}); }
    plot(id){ for(var i=0;i<this.PLOTS.length;i++){ if(this.PLOTS[i].id===id) return this.PLOTS[i]; } return this.PLOTS[0]; }
    startBuild(id){ var self=this; this.setFn(function(s){ var p=self.plot(id); var lvl=(id==='stadion')?self.tierOf(s.capacity):s.levels[id]; if(s.building[id]||lvl>=p.max) return {}; var nb=Object.assign({},s.building); nb[id]={target:lvl+1,total:self.bd(),left:self.bd()}; return {building:nb}; }); }
    finishBuild(id){ var self=this; this.setFn(function(s){ var b=s.building[id]; if(!b) return {}; var nb=Object.assign({},s.building); nb[id]=null; if(id==='stadion'){ return {building:nb,capacity:self.capForTier(b.target)}; } var nl=Object.assign({},s.levels); nl[id]=b.target; return {building:nb,levels:nl}; }); }
    cancelBuild(id){ this.setFn(function(s){ var nb=Object.assign({},s.building); nb[id]=null; return {building:nb}; }); }
    setLevel(id,lvl){ var self=this; this.setFn(function(s){ var nb=Object.assign({},s.building); nb[id]=null; if(id==='stadion'){ return {building:nb,capacity:self.capForTier(lvl)}; } var nl=Object.assign({},s.levels); nl[id]=lvl; return {building:nb,levels:nl}; }); }
    advanceDay(){ var self=this; this.setFn(function(s){ var nb=Object.assign({},s.building),nl=Object.assign({},s.levels),cap=s.capacity; Object.keys(nb).forEach(function(k){ if(nb[k]){ var left=nb[k].left-1; if(left<=0){ if(k==='stadion'){ cap=self.capForTier(nb[k].target); } else { nl[k]=nb[k].target; } nb[k]=null; } else { nb[k]=Object.assign({},nb[k],{left:left}); } } }); return {day:s.day+1,building:nb,levels:nl,capacity:cap}; }); }
    presetStart(){ this.set({capacity:8000,levels:{nlz:0,training:0,geschaeft:0,scouting:0,medizin:0,frei:0},building:{nlz:null,training:null,geschaeft:null,scouting:null,medizin:null,frei:null},heimspiel:false,day:1}); }
    presetFull(){ this.set({capacity:100000,levels:{nlz:3,training:3,geschaeft:3,scouting:3,medizin:3,frei:0},building:{nlz:null,training:null,geschaeft:null,scouting:null,medizin:null,frei:null}}); }
    resetPos(){ var base=Object.assign(JSON.parse(JSON.stringify(this.defPos)), JSON.parse(JSON.stringify(this.BAKED_POS))); this.set({positions:base, badgePos:JSON.parse(JSON.stringify(this.BAKED_BADGES))}); }
    badgePosOf(id){ var bp=(this.state&&this.state.badgePos)||{}; return bp[id]||this.defPos[id]||{x:50,y:50}; }
    onBadgeDown(e,id){ if(!this.state.adjust) return; e.preventDefault(); if(e.stopPropagation)e.stopPropagation(); this.dragBadge=id; this.setState({selected:id}); }
    resetBadge(id){ var self=this; this.setFn(function(s){ var nbp=Object.assign({},s.badgePos); if(self.BAKED_BADGES[id]){ nbp[id]=JSON.parse(JSON.stringify(self.BAKED_BADGES[id])); } else { delete nbp[id]; } return {badgePos:nbp}; }); }
    resetOne(key){ var self=this; this.setFn(function(s){ var np=Object.assign({},s.positions); if(self.BAKED_POS[key]){ np[key]=JSON.parse(JSON.stringify(self.BAKED_POS[key])); } else if(self.defPos[key]){ np[key]=JSON.parse(JSON.stringify(self.defPos[key])); } else { delete np[key]; } return {positions:np}; }); }
    selectPlot(id){ this.set({selected:id}); }
    setScale(key,v){ var b=this.basePos(key); this.setState(function(s){ var np=Object.assign({},s.positions); np[key]=Object.assign({},b,np[key],{s:Math.max(8,Math.min(80,parseFloat(v)||26))}); return {positions:np}; }, null, 'scene'); }
    setRot(key,axis,v){ var b=this.basePos(key); var lim=axis==='rz'?180:80; var val=Math.max(-lim,Math.min(lim,parseFloat(v)||0)); this.setState(function(s){ var np=Object.assign({},s.positions); var patch=Object.assign({},b,np[key]); patch[axis]=val; np[key]=patch; return {positions:np}; }, null, 'scene'); }
    setPosX(key,v){ var b=this.basePos(key); this.setState(function(s){ var np=Object.assign({},s.positions); np[key]=Object.assign({},b,np[key],{x:Math.max(2,Math.min(98,parseFloat(v)||50))}); return {positions:np}; }, null, 'scene'); }
    setPosY(key,v){ var b=this.basePos(key); this.setState(function(s){ var np=Object.assign({},s.positions); np[key]=Object.assign({},b,np[key],{y:Math.max(2,Math.min(98,parseFloat(v)||50))}); return {positions:np}; }, null, 'scene'); }
    onDown(e,key){ if(!this.state.adjust) return; e.preventDefault(); if(e.stopPropagation) e.stopPropagation(); this.drag=key; this.setState({selected:(''+key).split('|')[0]}); }
    onMove(e){
      if(this.dragBadge && this.stageEl){ var rb=this.stageEl.getBoundingClientRect(); var bx=((e.clientX-rb.left)/rb.width)*100, by=((e.clientY-rb.top)/rb.height)*100; bx=Math.max(2,Math.min(98,bx)); by=Math.max(2,Math.min(98,by)); var bid=this.dragBadge; this.setState(function(s){ var nbp=Object.assign({},s.badgePos); nbp[bid]={x:bx,y:by}; return {badgePos:nbp}; }, null, 'scene'); return; }
      if(this.dragCorner && this.stageEl){ var rr=this.stageEl.getBoundingClientRect(); var cx=((e.clientX-rr.left)/rr.width)*100, cy=((e.clientY-rr.top)/rr.height)*100; cx=Math.max(-8,Math.min(108,cx)); cy=Math.max(-8,Math.min(108,cy)); var dc=this.dragCorner; this.setState(function(s){ var np=Object.assign({},s.positions); var cur=Object.assign({},np[dc.key]); var c4=(cur.c4||[]).slice(); c4[dc.idx]={x:cx,y:cy}; cur.c4=c4; np[dc.key]=cur; return {positions:np}; }, null, 'scene'); return; }
      if(!this.drag||!this.stageEl) return; var r=this.stageEl.getBoundingClientRect(); var x=((e.clientX-r.left)/r.width)*100; var y=((e.clientY-r.top)/r.height)*100; x=Math.max(3,Math.min(97,x)); y=Math.max(4,Math.min(96,y)); var key=this.drag; var b=this.basePos(key); this.setState(function(s){ var np=Object.assign({},s.positions); np[key]=Object.assign({},b,np[key],{x:x,y:y}); return {positions:np}; }, null, 'scene'); }
    onUp(){ var did=false; if(this.drag){ this.drag=null; did=true; } if(this.dragBadge){ this.dragBadge=null; did=true; } if(this.dragCorner){ this.dragCorner=null; did=true; } if(did){ this.render(); this.save(); } }
    setStage(el){ this.stageEl=el; }
    stagePx(){ var w=this.stageEl?this.stageEl.getBoundingClientRect().width:900; return {w:w, h:w/(1672/941)}; }
    defaultCorners(pos,ratio){ var halfW=pos.s/2, hPct=pos.s/ratio*(1672/941), halfH=hPct/2; return [{x:pos.x-halfW,y:pos.y-halfH},{x:pos.x+halfW,y:pos.y-halfH},{x:pos.x+halfW,y:pos.y+halfH},{x:pos.x-halfW,y:pos.y+halfH}]; }
    warpCSS(c4,box,stage){ var wPx=box.w/100*stage.w, hPx=box.h/100*stage.h; var d=c4.map(function(p){ return {x:(p.x-box.lx)/100*stage.w, y:(p.y-box.ty)/100*stage.h}; }); var x0=d[0].x,y0=d[0].y,x1=d[1].x,y1=d[1].y,x2=d[2].x,y2=d[2].y,x3=d[3].x,y3=d[3].y; var dx1=x1-x2,dy1=y1-y2,dx2=x3-x2,dy2=y3-y2,sx=x0-x1+x2-x3,sy=y0-y1+y2-y3; var den=dx1*dy2-dx2*dy1; if(Math.abs(den)<1e-6)den=1e-6; var g=(sx*dy2-dx2*sy)/den, hh=(dx1*sy-sx*dy1)/den; var a=x1-x0+g*x1, bb=x3-x0+hh*x3, cc=x0, dd=y1-y0+g*y1, e=y3-y0+hh*y3, ff=y0; return 'matrix3d('+(a/wPx)+','+(dd/wPx)+',0,'+(g/wPx)+','+(bb/hPx)+','+(e/hPx)+',0,'+(hh/hPx)+',0,0,1,0,'+cc+','+ff+',0,1)'; }
    toggleWarp(key){ var self=this; this.setFn(function(st){ var np=Object.assign({},st.positions); var cur=Object.assign({},self.basePos(key),np[key]); if(cur.c4){ delete cur.c4; } else { var ratio=(self._ratioByKey&&self._ratioByKey[key])||1.4; cur.c4=self.defaultCorners({x:cur.x,y:cur.y,s:cur.s},ratio); } np[key]=cur; return {positions:np}; }); }
    resetWarp(key){ this.setFn(function(st){ var np=Object.assign({},st.positions); if(np[key]){ var cur=Object.assign({},np[key]); delete cur.c4; np[key]=cur; } return {positions:np}; }); }
    onCornerDown(e,key,idx){ if(!this.state.adjust) return; e.preventDefault(); if(e.stopPropagation)e.stopPropagation(); this.dragCorner={key:key,idx:idx}; }

    framed(n){ return 'framed/'+n; }
    stateKeyOf(p,level,building){
      if(p.kind==='stadium'){ if(building) return level+'+'; return level>0?(''+level):null; }
      if(p.kind==='reserve') return building?'bau':null;
      if(building) return level===0?'bau':(level+'+');
      return level>0?(''+level):null;
    }
    pk(plotId,stateKey){ return plotId+'|'+stateKey; }
    basePos(key){ var pid=(''+key).split('|')[0]; var sp=(this.state&&this.state.positions)||{}; return sp[pid]||this.defPos[pid]||{x:50,y:50,s:26}; }
    assetFor(p,level,building){
      if(p.kind==='stadium'){
        if(building){ return p.assets[level+'+'] ? this.url(p.assets[level+'+']) : this.url('stadion3.png'); }
        if(level===0) return null;
        return p.assets[level] ? this.url(p.assets[level]) : null;
      }
      if(p.kind==='reserve'){ return (building&&p.assets['bau'])?this.url(p.assets['bau']):null; }
      if(building){ var k=level+'+'; if(p.assets[k]) return this.url(p.assets[k]); if(p.assets['bau']) return this.url(p.assets['bau']); return this.url('baustelle.png'); }
      if(level===0) return null;
      if(p.assets[level]) return this.url(p.assets[level]);
      return null;
    }
    setEditorState(plotId,stateKey){
      var self=this; this.setFn(function(s){
        var p=self.plot(plotId); var nb=Object.assign({},s.building);
        if(p.kind==='stadium'){
          var plusS=/\+$/.test(stateKey); var t=parseInt(stateKey,10)||0;
          nb.stadion=plusS?{target:Math.min(t+1,4),total:self.bd(),left:self.bd()}:null;
          return {building:nb,capacity:self.capForTier(t),selected:plotId};
        }
        var nl=Object.assign({},s.levels);
        if(stateKey==='bau'){ nl[plotId]=0; nb[plotId]={target:1,total:self.bd(),left:self.bd()}; }
        else if(/\+$/.test(stateKey)){ var lv=parseInt(stateKey,10); nl[plotId]=lv; nb[plotId]={target:lv+1,total:self.bd(),left:self.bd()}; }
        else { nl[plotId]=parseInt(stateKey,10)||0; nb[plotId]=null; }
        return {levels:nl,building:nb,selected:plotId};
      });
    }

    buildNightBg(){
      if(this._nightBg) return this._nightBg;
      var s=987654321; function R(){ s=(s*1103515245+12345)&0x7fffffff; return s/0x7fffffff; }
      var P=[];
      var corners=[[45.5,36.5],[60.5,36.5],[45.5,53.5],[60.5,53.5]];
      corners.forEach(function(c){
        P.push('radial-gradient(8% 12% at '+c[0]+'% '+c[1]+'%, rgba(150,222,255,.30), transparent 72%)');
        P.push('radial-gradient(0.7% 1.2% at '+c[0]+'% '+c[1]+'%, rgba(238,255,255,.98), rgba(190,238,255,.55) 38%, transparent 72%)');
      });
      P.push('radial-gradient(13% 16% at 53% 45%, rgba(140,255,190,.30), rgba(120,250,180,.07) 55%, transparent 76%)');
      P.push('radial-gradient(21% 25% at 53% 45%, rgba(205,242,255,.16), transparent 72%)');
      var plots=[[70,21],[83,45],[76,80],[45,81],[25,69],[30,37]];
      plots.forEach(function(pc){
        var n=7+Math.floor(R()*3);
        for(var i=0;i<n;i++){
          var x=(pc[0]+(R()-.5)*13).toFixed(1), y=(pc[1]+(R()-.5)*12).toFixed(1);
          var col=R()>.22?'rgba(255,200,108,.96)':'rgba(206,234,255,.9)';
          P.push('radial-gradient(0.42% 0.75% at '+x+'% '+y+'%, '+col+', transparent 78%)');
        }
      });
      for(var a=0;a<12;a++){
        var ang=a*Math.PI/6;
        for(var k=0;k<3;k++){
          var rad=16+k*11+R()*4;
          var lx=53+Math.cos(ang)*rad*1.18, ly=45+Math.sin(ang)*rad;
          if(lx<4||lx>96||ly<5||ly>95) continue;
          P.push('radial-gradient(0.4% 0.7% at '+lx.toFixed(1)+'% '+ly.toFixed(1)+'%, rgba(255,213,138,.88), transparent 82%)');
        }
      }
      this._nightBg=P.join(',');
      return this._nightBg;
    }

    renderVals(){
      var self=this, s=this.state;
      var fmt=function(n){ return (n||0).toLocaleString('de-DE'); };
      var TONE={green:'#30f29c',cyan:'#22e6ff',yellow:'#ffd166',faint:'rgba(244,251,255,.55)'};
      var todF={tag:'',abend:'brightness(1.03) saturate(1.1) sepia(.16) hue-rotate(-12deg)',nacht:'brightness(.4) saturate(.72) contrast(1.1)'};
      var wetF={sommer:'',herbst:'saturate(1.2) sepia(.16) hue-rotate(-10deg)',winter:'saturate(.72) brightness(1.06)',schnee:'saturate(.58) brightness(1.14) contrast(.95)',weihnachten:'saturate(1.06) brightness(.97)'};
      var stageFilter=((todF[s.tod]||'')+' '+(wetF[s.wetter]||'')).trim()||'none';
      var sceneStyle={position:'absolute',inset:0,zIndex:2,filter:stageFilter,transition:'filter .4s ease'};
      var todT={tag:null,abend:'linear-gradient(0deg, rgba(255,120,30,.18), rgba(255,80,40,.05) 45%, transparent 72%)',nacht:'radial-gradient(120% 100% at 50% -8%, rgba(26,66,128,.36), transparent 56%), linear-gradient(0deg, rgba(2,7,20,.6), rgba(4,11,26,.28))'};
      var wetT={sommer:null,herbst:'linear-gradient(0deg, rgba(190,110,20,.14), transparent 60%)',winter:'linear-gradient(0deg, rgba(180,210,235,.16), rgba(210,228,245,.04) 50%, transparent)',schnee:'linear-gradient(0deg, rgba(225,240,255,.22), rgba(235,245,255,.06) 50%, transparent)',weihnachten:'radial-gradient(90% 70% at 50% 110%, rgba(255,60,60,.13), transparent 60%), linear-gradient(0deg, rgba(40,120,60,.1), transparent 55%)'};
      var tints=[todT[s.tod],wetT[s.wetter]].filter(Boolean);
      var envTintStyle={position:'absolute',inset:0,zIndex:4,pointerEvents:'none',background:tints.length?tints.join(','):'transparent',transition:'background .4s ease'};
      var snowStyle={position:'absolute',inset:0,zIndex:5,pointerEvents:'none',backgroundImage:'radial-gradient(2.4px 2.4px at 18% 24%, rgba(255,255,255,.92), transparent), radial-gradient(2px 2px at 68% 56%, rgba(255,255,255,.8), transparent), radial-gradient(1.6px 1.6px at 42% 82%, rgba(255,255,255,.7), transparent)',backgroundSize:'520px 520px,460px 460px,380px 380px',animation:'vu-snow 9s linear infinite',opacity:.85};
      var isNight=s.tod==='nacht';
      var nightLightsStyle={position:'absolute',inset:0,zIndex:6,pointerEvents:'none',backgroundImage:this.buildNightBg(),backgroundRepeat:'no-repeat',mixBlendMode:'screen'};
      var detailNightStyle={position:'absolute',inset:0,zIndex:6,pointerEvents:'none',mixBlendMode:'screen',background:'radial-gradient(58% 40% at 50% 86%, rgba(255,205,120,.24), transparent 70%), radial-gradient(70% 55% at 50% 28%, rgba(150,220,255,.16), transparent 72%)'};
      var todLabels={tag:'Tag',abend:'Abend',nacht:'Nacht'};
      var wetLabels={sommer:'Sommer',herbst:'Herbst',winter:'Winter',schnee:'Schnee',weihnachten:'Weihnachten'};
      var envLabel=todLabels[s.tod]+' · '+wetLabels[s.wetter];

      var S={
        panel:{background:'var(--panel)',border:'1px solid var(--line)',borderRadius:'8px',boxShadow:'var(--shadow)',padding:'14px'},
        title:{fontSize:'12px',fontWeight:900,letterSpacing:'.7px',textTransform:'uppercase',color:'var(--text)',marginBottom:'11px',display:'flex',alignItems:'center',justifyContent:'space-between',gap:'8px'},
        primaryBtn:{display:'inline-flex',alignItems:'center',justifyContent:'center',gap:'6px',minHeight:'38px',padding:'0 15px',borderRadius:'8px',fontWeight:800,fontSize:'13px',cursor:'pointer',background:'linear-gradient(180deg,#1bd9ee,#06879a)',border:'1px solid rgba(93,249,255,.46)',color:'#fff'},
        primaryBtnFull:{display:'flex',alignItems:'center',justifyContent:'center',gap:'6px',width:'100%',minHeight:'42px',padding:'0 15px',borderRadius:'8px',fontWeight:800,fontSize:'13px',cursor:'pointer',background:'linear-gradient(180deg,#1bd9ee,#06879a)',border:'1px solid rgba(93,249,255,.46)',color:'#fff'},
        ghostBtn:{display:'inline-flex',alignItems:'center',justifyContent:'center',gap:'6px',minHeight:'38px',padding:'0 14px',borderRadius:'8px',fontWeight:800,fontSize:'12px',cursor:'pointer',background:'rgba(255,255,255,.05)',border:'1px solid var(--line)',color:'var(--text)'},
        ghostBtnFull:{display:'flex',alignItems:'center',justifyContent:'center',gap:'6px',width:'100%',minHeight:'34px',marginTop:'8px',padding:'0 12px',borderRadius:'8px',fontWeight:800,fontSize:'12px',cursor:'pointer',background:'rgba(255,255,255,.05)',border:'1px solid var(--line)',color:'var(--text)'},
        seg:{display:'flex',gap:'4px',background:'rgba(255,255,255,.04)',border:'1px solid var(--line)',borderRadius:'8px',padding:'4px'},
        segWrap:{display:'flex',gap:'4px',flexWrap:'wrap',background:'rgba(255,255,255,.04)',border:'1px solid var(--line)',borderRadius:'8px',padding:'4px'}
      };
      var segBtn=function(active){ return {flex:'1 1 auto',padding:'7px 8px',borderRadius:'6px',border:'1px solid '+(active?'var(--line-strong)':'transparent'),background:active?'rgba(34,230,255,.16)':'transparent',color:active?'var(--text)':'var(--muted)',fontWeight:800,fontSize:'11.5px',letterSpacing:'.3px',cursor:'pointer',textTransform:'uppercase',whiteSpace:'nowrap'}; };

      var todOptions=['tag','abend','nacht'].map(function(k){ return {key:k,label:todLabels[k],onClick:function(){ self.setTod(k); },style:segBtn(s.tod===k)}; });
      var wetterOptions=['sommer','herbst','winter','schnee','weihnachten'].map(function(k){ return {key:k,label:wetLabels[k],onClick:function(){ self.setWetter(k); },style:segBtn(s.wetter===k)}; });

      var selHandles=[];
      var build=function(p){
        var ov={id:p.id,num:p.num,name:p.name,short:p.short,kind:p.kind,purpose:p.purpose};
        var isStad=p.kind==='stadium';
        var lvl=isStad?self.tierOf(s.capacity):s.levels[p.id];
        var b=s.building[p.id];
        var basePos=self.defPos[p.id];
        var stKey=self.stateKeyOf(p,lvl,b);
        var posKey=stKey?self.pk(p.id,stKey):null;
        var pos=(posKey&&s.positions[posKey])?s.positions[posKey]:(s.positions[p.id]||basePos);
        var editSel=(s.adjust&&s.selected===p.id);
        var src,hasImg,empty=false,showCard=false,tone='faint',chipText='',cardLabel=p.short,cardSub='';
        var statusText='',actionLabel='',actionFn=null,showAction=true,av='ghost';
        src=self.assetFor(p,lvl,b);
        if(isStad){
          var ti=self.tiers[lvl];
          if(b){ tone='yellow'; chipText=lvl+'+ · '+b.left+'T'; statusText='Stufe '+lvl+' → '+self.tiers[b.target].name+' · '+b.left+' T'; cardSub='Stadion-Ausbau'; actionLabel='Fertig'; actionFn=function(e){ if(e&&e.stopPropagation)e.stopPropagation(); self.finishBuild(p.id); }; av='warn'; }
          cardLabel='Stadion'; cardSub=cardSub||(ti.name+' · Standard im Hintergrund');
          empty=(lvl===0&&!b);
          showCard=(!hasImgSrc(src)&&!empty);
        } else {
          if(b){ tone='yellow'; var to=b.target; chipText=(lvl===0?'Bau':lvl+'+')+' · '+b.left+'T'; statusText=(lvl===0?'Bau · Stufe 1':'Stufe '+lvl+' → '+to)+' · '+b.left+' T'; cardSub=(lvl===0?'Baustelle · Stufe 1':'Ausbau → Stufe '+to); actionLabel='Fertig'; actionFn=function(e){ if(e&&e.stopPropagation)e.stopPropagation(); self.finishBuild(p.id); }; av='warn'; }
          else if(lvl>0){ tone='green'; chipText='Stufe '+lvl; statusText='Stufe '+lvl+' · In Betrieb'; cardSub='Stufe '+lvl+' · Bild folgt'; if(lvl<p.max){ actionLabel='Ausbauen'; actionFn=function(e){ if(e&&e.stopPropagation)e.stopPropagation(); self.startBuild(p.id); }; av='primary'; } else { showAction=false; } }
          else { empty=true; tone='faint'; chipText='frei'; statusText=(p.kind==='reserve'?'Baufeld frei · reserviert':'Baufeld frei'); actionLabel='Bauen'; actionFn=function(e){ if(e&&e.stopPropagation)e.stopPropagation(); self.startBuild(p.id); }; av='primary'; }
          showCard=(!hasImgSrc(src)&&!empty);
        }
        hasImg=hasImgSrc(src);
        ov.src=src; ov.hasImg=hasImg; ov.empty=empty; ov.showCard=showCard; ov.cardLabel=cardLabel; ov.cardSub=cardSub;
        var ratio=(src&&self.ratios[src])?self.ratios[src]:1.4;
        if(!self._ratioByKey)self._ratioByKey={};
        if(posKey) self._ratioByKey[posKey]=ratio;
        var rz=pos.rz||0;
        var warped=!!(pos.c4&&pos.c4.length===4);
        var halfW=pos.s/2, hPct=pos.s/ratio*(1672/941), halfH=hPct/2;
        ov.wrapStyle={position:'absolute',left:pos.x+'%',top:pos.y+'%',width:pos.s+'%',aspectRatio:String(ratio),transform:warped?'translate(-50%,-50%)':('translate(-50%,-50%) rotate('+rz+'deg)'),zIndex:editSel?320:(Math.round(pos.y)+5),pointerEvents:(s.adjust&&hasImg&&!warped)?'auto':'none',cursor:s.adjust?'grab':'default',outline:(editSel&&!warped)?'2px solid var(--cyan)':((s.adjust&&hasImg&&!warped)?'1px dashed rgba(34,230,255,.45)':'none'),outlineOffset:'2px',borderRadius:'8px',transition:(self.drag||self.dragCorner)?'none':'left .12s ease,top .12s ease,width .12s ease,transform .12s ease'};
        var imgBase={position:'absolute',inset:0,backgroundImage:src?("url('"+src+"')"):'none',backgroundRepeat:'no-repeat',pointerEvents:'none',filter:'drop-shadow(0 14px 20px rgba(0,0,0,.5))'};
        if(warped){ var wbox={lx:pos.x-halfW,ty:pos.y-halfH,w:pos.s,h:hPct}; imgBase.transform=self.warpCSS(pos.c4,wbox,self.stagePx()); imgBase.transformOrigin='0 0'; imgBase.backgroundSize='100% 100%'; imgBase.backgroundPosition='center'; }
        else { imgBase.backgroundSize='contain'; imgBase.backgroundPosition='center bottom'; }
        ov.imgStyle=imgBase;
        if(editSel&&warped){ selHandles=pos.c4.map(function(cpt,i){ return {idx:i,style:{position:'absolute',left:cpt.x+'%',top:cpt.y+'%',transform:'translate(-50%,-50%)',width:'20px',height:'20px',borderRadius:'4px',background:'rgba(34,230,255,.92)',border:'2px solid #052430',boxShadow:'0 2px 9px rgba(0,0,0,.65)',zIndex:420,cursor:'grab',touchAction:'none',pointerEvents:'auto'},onDown:(function(ix){ return function(e){ self.onCornerDown(e,posKey,ix); }; })(i)}; }); }
        ov.cardStyle={position:'absolute',left:basePos.x+'%',top:basePos.y+'%',transform:'translate(-50%,-50%)',width:'150px',padding:'11px 10px',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',textAlign:'center',background:'linear-gradient(180deg, rgba(12,31,45,.94), rgba(7,20,31,.94))',border:'1px dashed '+(tone==='yellow'?TONE.yellow:'var(--line-strong)'),borderRadius:'10px',boxShadow:'var(--shadow)',pointerEvents:'none',zIndex:150};
        var bpos=self.badgePosOf(p.id);
        ov.badgeStyle={position:'absolute',left:bpos.x+'%',top:bpos.y+'%',transform:'translate(-50%,-50%)',zIndex:(s.adjust&&s.selected===p.id)?330:200,cursor:s.adjust?'grab':'pointer',touchAction:s.adjust?'none':'auto',padding:s.adjust?'4px':'0',borderRadius:'12px',background:s.adjust?((s.selected===p.id)?'rgba(34,230,255,.14)':'rgba(3,8,14,.32)'):'transparent',outline:s.adjust?((s.selected===p.id)?'1.5px dashed var(--cyan)':'1px dashed rgba(34,230,255,.42)'):'none',outlineOffset:'2px',transition:(self.drag||self.dragBadge||self.dragCorner)?'none':'left .12s ease,top .12s ease'};
        ov.onBadgeDown=function(e){ self.onBadgeDown(e,p.id); };
        ov.numText=isStad?'★':(''+p.num);
        ov.numStyle=isStad
          ? {width:'30px',height:'30px',borderRadius:'999px',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:900,fontSize:'15px',color:'#1a1205',background:'linear-gradient(180deg,#ffd76a,#d89a12)',border:'1.5px solid rgba(255,228,140,.85)',boxShadow:'0 0 16px rgba(255,180,30,.5),0 4px 10px rgba(0,0,0,.5)'}
          : {width:'30px',height:'30px',borderRadius:'999px',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:900,fontSize:'15px',color:'#061018',background:'linear-gradient(180deg,#2cf0ff,#06879a)',border:'1.5px solid rgba(120,250,255,.7)',boxShadow:'0 0 14px rgba(34,230,255,.5),0 4px 10px rgba(0,0,0,.5)'};
        var tc=TONE[tone]||TONE.faint;
        ov.chipText=chipText;
        ov.chipStyle={padding:'2px 8px',borderRadius:'999px',fontSize:'10px',fontWeight:900,letterSpacing:'.3px',whiteSpace:'nowrap',background:'rgba(4,11,18,.86)',border:'1px solid '+tc,color:tc,boxShadow:'0 4px 10px rgba(0,0,0,.45)'};
        ov.onClick=function(){ if(s.adjust){ self.selectPlot(p.id); return; } self.openDetail(p.id); };
        ov.onDown=function(e){ if(posKey) self.onDown(e,posKey); };
        ov.statusText=statusText;
        ov.statusStyle={fontSize:'10.5px',fontWeight:700,color:tc,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis',marginTop:'1px'};
        ov.rowStyle={display:'flex',alignItems:'center',gap:'10px',padding:'8px 10px',borderRadius:'8px',border:'1px solid '+(s.selected===p.id?'var(--line-strong)':'var(--line)'),background:s.selected===p.id?'rgba(34,230,255,.07)':'rgba(255,255,255,.025)',cursor:'pointer'};
        ov.rowNumStyle={flex:'0 0 26px',width:'26px',height:'26px',borderRadius:'999px',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:900,fontSize:'12px',color:isStad?'#1a1205':'#061018',background:isStad?'linear-gradient(180deg,#ffd76a,#d89a12)':'linear-gradient(180deg,#2cf0ff,#06879a)'};
        ov.showAction=showAction&&!!actionFn;
        ov.actionLabel=actionLabel; ov.actionFn=actionFn;
        ov.actionStyle=av==='primary'?{padding:'6px 11px',borderRadius:'7px',fontWeight:800,fontSize:'11.5px',cursor:'pointer',background:'linear-gradient(180deg,#1bd9ee,#06879a)',border:'1px solid rgba(93,249,255,.46)',color:'#fff',whiteSpace:'nowrap'}
          : av==='warn'?{padding:'6px 11px',borderRadius:'7px',fontWeight:800,fontSize:'11.5px',cursor:'pointer',background:'rgba(255,209,102,.15)',border:'1px solid rgba(255,209,102,.5)',color:'#ffd166',whiteSpace:'nowrap'}
          : {padding:'6px 11px',borderRadius:'7px',fontWeight:800,fontSize:'11.5px',cursor:'pointer',background:'rgba(255,255,255,.05)',border:'1px solid var(--line)',color:'var(--text)',whiteSpace:'nowrap'};
        ov.onOpen=function(){ self.openDetail(p.id); };
        ov.lvl=lvl; ov.building=b; ov.tone=tone; ov.toneColor=tc;
        return ov;
      };
      function hasImgSrc(x){ return !!x; }
      var overlays=this.PLOTS.map(build);
      var railRows=overlays.map(function(o){ return {num:o.num,numText:o.kind==='stadium'?'★':(''+o.num),name:o.name,statusText:o.statusText,statusStyle:o.statusStyle,rowStyle:o.rowStyle,numStyle:o.rowNumStyle,showAction:o.showAction,actionLabel:o.actionLabel,actionFn:o.actionFn,actionStyle:o.actionStyle,onOpen:o.onOpen,kind:o.kind}; }); railRows.sort(function(a,b){return (a.kind==='stadium'?99:a.num)-(b.kind==='stadium'?99:b.num);});

      var selId=s.selected; var selOv=null; for(var i=0;i<overlays.length;i++){ if(overlays[i].id===selId){ selOv=overlays[i]; } } if(!selOv) selOv=overlays[0];
      var p=this.plot(selId);
      var sel={id:p.id,name:p.name,purpose:p.purpose,isStadium:p.kind==='stadium',num:selOv.num};
      sel.src=selOv.src; sel.hasImg=selOv.hasImg; sel.showCard=selOv.showCard; sel.cardLabel=selOv.cardLabel; sel.cardSub=selOv.cardSub; sel.fans=false; var heroSrc=sel.src?sel.src.replace('framed/','assets/'):null; sel.imgDivStyle={position:'absolute',inset:0,backgroundImage:heroSrc?("url('"+heroSrc+"')"):'none',backgroundSize:'contain',backgroundPosition:'center',backgroundRepeat:'no-repeat',filter:'drop-shadow(0 22px 30px rgba(0,0,0,.55))'};
      if(sel.isStadium&&selOv.lvl===0&&!selOv.building){ sel.showCard=true; sel.hasImg=false; sel.cardLabel='Standard-Stadion'; sel.cardSub='Im Vereinsumfeld sichtbar · Ausbau ab 30.000 Zuschauer'; }
      sel.cardStyle={position:'absolute',left:'50%',top:'50%',transform:'translate(-50%,-50%)',width:'56%',padding:'22px',display:'flex',flexDirection:'column',alignItems:'center',textAlign:'center',background:'linear-gradient(180deg, rgba(12,31,45,.95), rgba(7,20,31,.95))',border:'1px dashed var(--line-strong)',borderRadius:'14px',boxShadow:'var(--shadow)'};
      sel.numText=p.kind==='stadium'?'★':(''+p.num);
      sel.numStyle=(p.kind==='stadium'?'width:38px;height:38px;border-radius:999px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:18px;color:#1a1205;background:linear-gradient(180deg,#ffd76a,#d89a12);border:1.5px solid rgba(255,228,140,.85);box-shadow:0 0 16px rgba(255,180,30,.5);':'width:38px;height:38px;border-radius:999px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:18px;color:#061018;background:linear-gradient(180deg,#2cf0ff,#06879a);border:1.5px solid rgba(120,250,255,.7);box-shadow:0 0 16px rgba(34,230,255,.5);');
      sel.statusText=selOv.statusText;
      sel.statusBadge='display:inline-block;padding:5px 13px;border-radius:999px;font-size:12px;font-weight:900;letter-spacing:.3px;border:1px solid '+selOv.toneColor+';color:'+selOv.toneColor+';background:rgba(255,255,255,.04);white-space:nowrap;';
      var blvl=selOv.lvl, bbuild=selOv.building;
      sel.isBuilding=!!bbuild; sel.canBuild=!bbuild&&blvl<p.max; sel.isMax=!bbuild&&blvl>=p.max;
      sel.buildHeading=p.kind==='stadium'?'Stadion-Ausbau':'Ausbau';
      sel.maxName=p.kind==='stadium'?this.tiers[p.max].name:('Stufe '+p.max);
      if(bbuild){ sel.buildingText=(p.kind==='stadium'?('→ '+this.tiers[bbuild.target].name):('Ausbau → Stufe '+bbuild.target))+' · noch '+bbuild.left+' Tage'; var prog=Math.round((1-bbuild.left/bbuild.total)*100); sel.progTrack={position:'relative',height:'8px',borderRadius:'999px',background:'rgba(255,255,255,.08)',overflow:'hidden'}; sel.progFill={position:'absolute',left:0,top:0,bottom:0,width:prog+'%',borderRadius:'999px',background:'linear-gradient(90deg,var(--green),var(--cyan))'}; }
      sel.buildLabel=(p.kind==='stadium')?('Auf '+this.tiers[Math.min(blvl+1,4)].name+' ausbauen · '+this.bd()+' Tage'):('Auf Stufe '+(blvl+1)+' ausbauen · '+this.bd()+' Tage');
      sel.buildHint=(blvl===0)?('Baufeld bebauen — Bauzeit '+this.bd()+' Tage, danach Stufe 1.'):('Ausbau startet eine Bauzeit von '+this.bd()+' Tagen. Im Umfeld erscheint der „+\u201c-Bauzustand.');
      sel.buildFn=function(){ self.startBuild(p.id); };
      sel.finishFn=function(){ self.finishBuild(p.id); };
      sel.cancelFn=function(){ self.cancelBuild(p.id); };
      sel.hasNote=!!p.note; sel.note=p.note||'';
      var ladder=[];
      var addRung=function(L){ var thumb=null; if(p.kind==='stadium'){ thumb=(L===0)?null:(p.assets[L]?self.url(p.assets[L]):null); } else { thumb=(L===0)?null:(p.assets[''+L]?self.url(p.assets[''+L]):null); } var isCur=!bbuild&&blvl===L; ladder.push({lvl:L,label:(L===0?(p.kind==='stadium'?'Standard':'Leer'):(p.kind==='stadium'?self.tiers[L].name:('Stufe '+L))),thumb:thumb,hasThumb:!!thumb,empty:!thumb,onClick:function(){ self.setLevel(p.id,L); },style:{display:'flex',flexDirection:'column',alignItems:'center',gap:'5px',padding:'7px',width:p.kind==='stadium'?'88px':'82px',borderRadius:'9px',cursor:'pointer',border:'1px solid '+(isCur?'var(--cyan)':'var(--line)'),background:isCur?'rgba(34,230,255,.1)':'rgba(255,255,255,.03)'},thumbImgStyle:{width:'100%',height:'100%',backgroundImage:thumb?("url('"+thumb+"')"):'none',backgroundSize:'cover',backgroundPosition:'center'},thumbStyle:{width:p.kind==='stadium'?'74px':'66px',height:'50px',borderRadius:'6px',overflow:'hidden',background:'rgba(7,16,24,.85)',border:'1px solid var(--line)',display:'flex',alignItems:'center',justifyContent:'center'}}); };
      for(var L=0;L<=p.max;L++){ addRung(L); }
      sel.ladder=ladder;
      var tierLadder=this.tiers.map(function(x){ var active=self.tierOf(s.capacity)===x.t; return {name:x.name,cap:x.cap,short:x.short,active:active,onClick:function(){ self.setLevel('stadion',x.t); },rowStyle:{display:'flex',alignItems:'center',gap:'11px',padding:'9px 10px',borderRadius:'9px',cursor:'pointer',border:'1px solid '+(active?'var(--line-strong)':'var(--line)'),background:active?'rgba(34,230,255,.08)':'rgba(255,255,255,.025)'},iconStyle:{flex:'0 0 36px',width:'36px',height:'36px',borderRadius:'8px',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:900,fontSize:'12px',color:active?'#061018':'var(--muted)',background:active?'linear-gradient(180deg,#2cf0ff,#06879a)':'rgba(255,255,255,.05)',border:'1px solid var(--line)'}}; });
      sel.tierName=this.tiers[this.tierOf(s.capacity)].name; sel.capFmt=fmt(s.capacity); sel.capacity=s.capacity;

      var edPlot=this.plot(selId);
      var edLvl=edPlot.kind==='stadium'?this.tierOf(s.capacity):s.levels[selId];
      var edBuild=s.building[selId];
      var edStKey=this.stateKeyOf(edPlot,edLvl,edBuild);
      var edPosKey=edStKey?this.pk(selId,edStKey):null;
      var edPos=(edPosKey&&s.positions[edPosKey])?s.positions[edPosKey]:(s.positions[selId]||this.defPos[selId]);
      var edHasCustom=!!(edPosKey&&s.positions[edPosKey]);
      var edStateDefs=edPlot.kind==='stadium'?[['0+','0+'],['1','S1'],['1+','1+'],['2','S2'],['2+','2+'],['3','S3'],['4','S4']]:(edPlot.kind==='reserve'?[['bau','Baustelle']]:[['bau','Baustelle'],['1','1'],['1+','1+'],['2','2'],['2+','2+'],['3','3']]);
      var edStateButtons=edStateDefs.map(function(d){ var on=(edStKey===d[0]); return {key:d[0],label:d[1],onClick:function(){ self.setEditorState(selId,d[0]); },style:'padding:6px 10px;border-radius:7px;font-weight:900;font-size:11px;cursor:pointer;white-space:nowrap;border:1px solid '+(on?'var(--cyan)':'var(--line)')+';background:'+(on?'rgba(34,230,255,.18)':'rgba(255,255,255,.04)')+';color:'+(on?'var(--cyan)':'var(--muted)')+';'}; });

      var isOverview=s.screen==='overview', isDetail=s.screen==='detail';
      var heimOn=s.heimspiel;
      var activeBuilds=Object.keys(s.building).filter(function(k){ return s.building[k]; }).length;
      var buildSummary=activeBuilds?('Im Bau: '+activeBuilds+' · „Tag +1\u201c baut'):'Keine Baustelle aktiv';

      return {
        isOverview:isOverview, isDetail:isDetail, adjust:s.adjust, heimspiel:heimOn,
        isSnow:s.wetter==='schnee', day:s.day, envLabel:envLabel,
        titleText:isOverview?'VEREINSUMFELD':p.name.toUpperCase(),
        subText:isOverview?'Vereinsgelände · 6 Baufelder + Stadion':p.purpose,
        bgSrc:this.url('umfeld0.png'), fansSrc:this.url('stadtfans.png'), bgDivStyle:{position:'absolute',inset:0,backgroundImage:"url('"+this.url('umfeld0.png')+"')",backgroundSize:'cover',backgroundPosition:'center'}, fansDivStyle:{position:'absolute',inset:0,backgroundImage:"url('"+this.url('stadtfans.png')+"')",backgroundSize:'cover',backgroundPosition:'center',zIndex:1,pointerEvents:'none'},
        sceneStyle:sceneStyle, envTintStyle:envTintStyle, snowStyle:snowStyle, isNight:isNight, nightLightsStyle:nightLightsStyle, detailNightStyle:detailNightStyle,
        overlays:overlays, railRows:railRows, sel:sel, tierLadder:tierLadder,
        todOptions:todOptions, wetterOptions:wetterOptions, buildSummary:buildSummary,
        S:S,
        selName:edPlot.name+(edStKey?(' · '+(edStKey==='bau'?'Baustelle':('St. '+edStKey))):' · leer'), hasSel:!!edPosKey,
        setBadgeText:edHasCustom?'✓ gesetzt':'Standard',
        setBadgeStyle:edHasCustom?{padding:'2px 9px',borderRadius:'999px',fontSize:'10px',fontWeight:'900',letterSpacing:'.3px',background:'rgba(48,242,156,.16)',border:'1px solid var(--green)',color:'var(--green)'}:{padding:'2px 9px',borderRadius:'999px',fontSize:'10px',fontWeight:'900',letterSpacing:'.3px',background:'rgba(255,255,255,.05)',border:'1px solid var(--line)',color:'var(--faint)'},
        selScale:edPos.s, selScalePct:Math.round(edPos.s),
        selX:Math.round(edPos.x), selY:Math.round(edPos.y), stateButtons:edStateButtons,
        selRz:Math.round(edPos.rz||0),
        onRzInput:function(e){ if(edPosKey) self.setRot(edPosKey,'rz',e.target.value); },
        warpOn:!!(edPos&&edPos.c4), warpBtnLabel:(edPos&&edPos.c4)?'Ecken-Modus: AN':'Ecken ziehen',
        warpBtnStyle:(edPos&&edPos.c4)?{flex:'1',padding:'9px',borderRadius:'8px',border:'1px solid var(--cyan)',background:'rgba(34,230,255,.2)',color:'var(--cyan)',fontWeight:'800',fontSize:'12px',cursor:'pointer'}:S.ghostBtnFull,
        onToggleWarp:function(){ if(edPosKey) self.toggleWarp(edPosKey); }, onResetWarp:function(){ if(edPosKey) self.resetWarp(edPosKey); },
        cornerHandles:selHandles,
        onXInput:function(e){ if(edPosKey) self.setPosX(edPosKey,e.target.value); }, onYInput:function(e){ if(edPosKey) self.setPosY(edPosKey,e.target.value); }, resetOne:function(){ if(edPosKey) self.resetOne(edPosKey); }, resetBadge:function(){ self.resetBadge(selId); },
        adjustPlots:self.PLOTS.map(function(pp){ var on=(s.selected===pp.id); return {id:pp.id,label:(pp.kind==='stadium'?'\u2605':(''+pp.num)),onClick:function(){ self.selectPlot(pp.id); },style:'width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:14px;cursor:pointer;border:1px solid '+(on?'var(--cyan)':'var(--line)')+';background:'+(on?'rgba(34,230,255,.18)':'rgba(255,255,255,.04)')+';color:'+(on?'var(--cyan)':'var(--muted)')+';'}; }),
        hideImg:this.hideImg,
        setStage:function(el){ self.setStage(el); },
        back:function(){ self.back(); }, toggleHeim:function(){ self.toggleHeim(); },
        advanceDay:function(){ self.advanceDay(); }, presetStart:function(){ self.presetStart(); }, presetFull:function(){ self.presetFull(); },
        toggleAdjust:function(){ self.toggleAdjust(); }, resetPos:function(){ self.resetPos(); },
        onScaleInput:function(e){ if(edPosKey) self.setScale(edPosKey,e.target.value); },
        onCapInput:function(e){ self.setCap(e.target.value); },
        heimSwitch:'position:relative;width:46px;height:26px;border-radius:999px;border:1px solid '+(heimOn?'var(--green)':'var(--line)')+';background:'+(heimOn?'rgba(48,242,156,.25)':'rgba(255,255,255,.05)')+';cursor:pointer;flex:0 0 auto;padding:0;transition:all .2s;',
        heimKnob:'position:absolute;top:2px;left:'+(heimOn?'22px':'2px')+';width:20px;height:20px;border-radius:999px;background:'+(heimOn?'#30f29c':'#9fb0bd')+';transition:left .2s,background .2s;',
        adjustSwitch:'position:relative;width:42px;height:24px;border-radius:999px;border:1px solid '+(s.adjust?'var(--cyan)':'var(--line)')+';background:'+(s.adjust?'rgba(34,230,255,.22)':'rgba(255,255,255,.05)')+';cursor:pointer;flex:0 0 auto;padding:0;transition:all .2s;',
        adjustKnob:'position:absolute;top:2px;left:'+(s.adjust?'20px':'2px')+';width:18px;height:18px;border-radius:999px;background:'+(s.adjust?'#22e6ff':'#9fb0bd')+';transition:left .2s,background .2s;'
      };
    }

    /* ---- DOM rendering (mirrors the .dc.html markup) ---------------- */
    render(){
      var V=this.renderVals();
      this._slX=this._slY=this._slScale=this._slRz=this._slCap=null;
      this._elReadout=this._elRz=this._capNumEl=this._capTierEl=null;
      this.mount.innerHTML='';
      this.mount.appendChild(this.buildHeader(V));
      var body=h('div',{style:{flex:'1',display:'flex',minHeight:'0'}});
      if(V.isOverview){
        var cell=h('div',{style:{flex:'1',minWidth:'0',display:'flex',alignItems:'center',justifyContent:'center',padding:'6px'}});
        this._stageCell=cell;
        cell.appendChild(this.buildOverviewStage(V));
        body.appendChild(cell);
        if(IS_ADMIN) body.appendChild(this.buildOverviewRail(V));
      } else {
        var cell2=h('div',{style:{flex:'1',minWidth:'0',display:'flex',alignItems:'center',justifyContent:'center',padding:'18px'}});
        this._stageCell=cell2;
        cell2.appendChild(this.buildDetailStage(V));
        body.appendChild(cell2);
        if(IS_ADMIN) body.appendChild(this.buildDetailRail(V));
      }
      this.mount.appendChild(body);
    }
    refreshScene(){
      if(!this._stageCell){ this.render(); return; }
      var V=this.renderVals();
      this._stageCell.innerHTML='';
      this._stageCell.appendChild(V.isOverview?this.buildOverviewStage(V):this.buildDetailStage(V));
      this.syncEditorLive(V);
    }
    syncEditorLive(V){
      var ae=document.activeElement;
      if(this._elReadout) this._elReadout.textContent='X '+V.selX+' · Y '+V.selY+' · '+V.selScalePct+'%';
      if(this._elRz) this._elRz.textContent='DREHUNG (Z) — '+V.selRz+'°';
      if(this._slX && this._slX!==ae) this._slX.value=V.selX;
      if(this._slY && this._slY!==ae) this._slY.value=V.selY;
      if(this._slScale && this._slScale!==ae) this._slScale.value=V.selScale;
      if(this._slRz && this._slRz!==ae) this._slRz.value=V.selRz;
      if(this._capNumEl) this._capNumEl.textContent=V.sel.capFmt;
      if(this._capTierEl) this._capTierEl.textContent=V.sel.tierName+' aktiv · Stufe per Kapazität';
      if(this._slCap && this._slCap!==ae) this._slCap.value=V.sel.capacity;
    }

    buildHeader(V){
      var kids=[];
      if(V.isDetail){
        kids.push(h('button',{style:{width:'36px',height:'36px',borderRadius:'8px',border:'1px solid var(--line)',background:'rgba(255,255,255,.05)',color:'var(--text)',fontSize:'18px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'},onClick:V.back},'←'));
      }
      kids.push(h('div',{style:{display:'flex',alignItems:'center',gap:'11px'}},[
        h('div',{style:{width:'30px',height:'30px',borderRadius:'7px',background:'linear-gradient(180deg,#1bd9ee,#06879a)',boxShadow:'0 0 16px rgba(34,230,255,.5)',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:'900',color:'#061018',fontSize:'15px'}},'M'),
        h('div',{},[
          h('div',{style:{fontSize:'17px',fontWeight:'900',letterSpacing:'.5px',lineHeight:'1.05'},text:V.titleText}),
          h('div',{style:{fontSize:'10.5px',fontWeight:'800',letterSpacing:'.6px',color:'var(--faint)',textTransform:'uppercase'},text:V.subText})
        ])
      ]));
      kids.push(h('div',{style:{marginLeft:'auto',display:'flex',alignItems:'center',gap:'9px'}},[
        h('div',{style:{display:'flex',alignItems:'center',gap:'7px',padding:'7px 12px',borderRadius:'8px',border:'1px solid var(--line)',background:'rgba(255,255,255,.04)',fontSize:'12px',fontWeight:'800',letterSpacing:'.4px'}},[
          h('span',{style:{color:'var(--faint)',textTransform:'uppercase'}},'Spieltag'),
          h('span',{style:{color:'var(--cyan)'},text:'Tag '+V.day})
        ])
      ]));
      return h('header',{style:{display:'flex',alignItems:'center',gap:'14px',padding:'12px 20px',borderBottom:'1px solid var(--line)',background:'rgba(5,15,23,.55)',backdropFilter:'blur(8px)',flex:'0 0 auto',zIndex:'30'}},kids);
    }

    buildOverviewStage(V){
      var self=this;
      var scene=h('div',{style:V.sceneStyle});
      scene.appendChild(h('div',{style:V.bgDivStyle}));
      V.overlays.forEach(function(ov){
        var inner=[];
        if(ov.showCard){ inner.push(h('div',{style:ov.cardStyle},[
          h('div',{style:{fontSize:'12px',fontWeight:'900',letterSpacing:'.4px',textTransform:'uppercase',color:'var(--text)'},text:ov.cardLabel}),
          h('div',{style:{fontSize:'10.5px',fontWeight:'700',color:'var(--muted)',marginTop:'3px'},text:ov.cardSub})
        ])); }
        if(ov.hasImg){ inner.push(h('div',{style:ov.imgStyle})); }
        scene.appendChild(h('div',{style:ov.wrapStyle,onClick:IS_ADMIN?ov.onClick:null,onDown:IS_ADMIN?ov.onDown:null},inner));
      });
      if(V.heimspiel){ scene.appendChild(h('div',{style:V.fansDivStyle})); }
      var stageKids=[scene, h('div',{style:V.envTintStyle})];
      if(V.isNight) stageKids.push(h('div',{style:V.nightLightsStyle}));
      if(V.isSnow) stageKids.push(h('div',{style:V.snowStyle}));
      V.overlays.forEach(function(ov){
        stageKids.push(h('div',{style:ov.badgeStyle,onClick:IS_ADMIN?ov.onClick:null,onDown:IS_ADMIN?ov.onBadgeDown:null},[
          h('div',{style:{display:'flex',flexDirection:'column',alignItems:'center',gap:'3px'}},[
            h('div',{style:ov.numStyle,text:ov.numText}),
            h('div',{style:ov.chipStyle,text:ov.chipText})
          ])
        ]));
      });
      if(IS_ADMIN){ V.cornerHandles.forEach(function(hd){ stageKids.push(h('div',{style:hd.style,onDown:hd.onDown})); }); }
      return h('div',{ref:function(el){ self.setStage(el); },style:{position:'relative',width:'100%',aspectRatio:'1672 / 941',border:'1px solid var(--line)',borderRadius:'14px',overflow:'hidden',boxShadow:'var(--shadow)',background:'#0a141d'}},stageKids);
    }

    buildOverviewRail(V){
      var self=this;
      var panels=[];
      // Simulation
      panels.push(h('div',{style:V.S.panel},[
        h('div',{style:V.S.title},[ h('span',{},'Simulation'), h('span',{style:{fontSize:'10px',color:'var(--faint)'}},'7-Tage-Bauzeit') ]),
        h('div',{style:{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'11px'}},[
          h('div',{},[
            h('div',{style:{fontSize:'24px',fontWeight:'900',color:'var(--cyan)',lineHeight:'1'},text:'Tag '+V.day}),
            h('div',{style:{fontSize:'10.5px',color:'var(--faint)',fontWeight:'800',textTransform:'uppercase',letterSpacing:'.4px',marginTop:'4px'},text:V.buildSummary})
          ]),
          h('button',{style:V.S.primaryBtn,onClick:V.advanceDay},'Tag +1 ▸')
        ]),
        h('div',{style:{display:'flex',gap:'8px'}},[
          h('button',{style:V.S.ghostBtnFull,onClick:V.presetStart},'Spielstart'),
          h('button',{style:V.S.ghostBtnFull,onClick:V.presetFull},'Voll ausgebaut')
        ])
      ]));
      // Umgebung & Heimspiel
      panels.push(h('div',{style:V.S.panel},[
        h('div',{style:V.S.title},[ h('span',{},'Umgebung & Heimspiel') ]),
        h('div',{style:{fontSize:'10px',color:'var(--faint)',fontWeight:'800',textTransform:'uppercase',letterSpacing:'.5px',marginBottom:'6px'}},'Tageszeit'),
        h('div',{style:V.S.seg}, V.todOptions.map(function(o){ return h('button',{style:o.style,onClick:o.onClick,text:o.label}); })),
        h('div',{style:{fontSize:'10px',color:'var(--faint)',fontWeight:'800',textTransform:'uppercase',letterSpacing:'.5px',margin:'11px 0 6px'}},'Wetter & Saison'),
        h('div',{style:V.S.segWrap}, V.wetterOptions.map(function(o){ return h('button',{style:o.style,onClick:o.onClick,text:o.label}); })),
        h('div',{style:{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px',marginTop:'13px',paddingTop:'13px',borderTop:'1px solid var(--line)'}},[
          h('div',{style:{fontSize:'11.5px',color:'var(--muted)',fontWeight:'700',maxWidth:'228px',lineHeight:'1.35'}},'StadtFans erscheinen nur am Heimspieltag — als Layer über dem Umfeld.'),
          h('button',{style:V.heimSwitch,onClick:V.toggleHeim},[ h('span',{style:V.heimKnob}) ])
        ])
      ]));
      // Baufelder
      panels.push(h('div',{style:V.S.panel},[
        h('div',{style:V.S.title},[ h('span',{},'Baufelder 1–6 + Stadion') ]),
        h('div',{style:{display:'flex',flexDirection:'column',gap:'7px'}}, V.railRows.map(function(r){
          var rowKids=[
            h('div',{style:r.numStyle,text:r.numText}),
            h('div',{style:{flex:'1',minWidth:'0'}},[
              h('div',{style:{fontSize:'12.5px',fontWeight:'800',color:'var(--text)',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'},text:r.name}),
              h('div',{style:r.statusStyle,text:r.statusText})
            ])
          ];
          if(r.showAction){ rowKids.push(h('button',{style:r.actionStyle,onClick:r.actionFn,text:r.actionLabel})); }
          return h('div',{style:r.rowStyle,onClick:r.onOpen},rowKids);
        }))
      ]));
      // Editor-Modus
      var edKids=[
        h('div',{style:V.S.title},[ h('span',{},'Editor-Modus'), h('button',{style:V.adjustSwitch,onClick:V.toggleAdjust},[ h('span',{style:V.adjustKnob}) ]) ]),
        h('div',{style:{fontSize:'11.5px',color:'var(--muted)',fontWeight:'700',lineHeight:'1.4'}},'Editor an → Baufeld + Zustand wählen, dann Gebäude ziehen oder per Regler X / Y / Größe setzen. Auch die Nummern-Badges kannst du frei ziehen. Speichert automatisch — pro Asset.')
      ];
      if(V.adjust){ edKids.push(this.buildEditorControls(V)); }
      panels.push(h('div',{style:V.S.panel},edKids));

      return h('aside',{'class':'vu-rail',style:{flex:'0 0 318px',borderLeft:'1px solid var(--line)',background:'rgba(5,14,22,.5)',overflowY:'auto',padding:'13px',display:'flex',flexDirection:'column',gap:'13px'}},panels);
    }

    buildEditorControls(V){
      var self=this;
      var wrap=h('div',{style:{marginTop:'11px',animation:'vu-rise .2s ease'}});
      wrap.appendChild(h('div',{style:LBL5},'BAUFELD'));
      wrap.appendChild(h('div',{style:{display:'flex',gap:'6px',flexWrap:'wrap',marginBottom:'11px'}}, V.adjustPlots.map(function(ap){ return h('button',{style:ap.style,onClick:ap.onClick,text:ap.label}); })));
      wrap.appendChild(h('div',{style:LBL5},'ZUSTAND / STUFE — jeder einzeln'));
      wrap.appendChild(h('div',{style:{display:'flex',gap:'5px',flexWrap:'wrap',marginBottom:'12px'}}, V.stateButtons.map(function(sb){ return h('button',{style:sb.style,onClick:sb.onClick,text:sb.label}); })));
      wrap.appendChild(h('div',{style:{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'9px'}},[
        h('span',{style:{fontSize:'11px',color:'var(--cyan)',textTransform:'uppercase',fontWeight:'900',letterSpacing:'.4px'},text:V.selName}),
        h('span',{style:V.setBadgeStyle,text:V.setBadgeText})
      ]));
      var readout=h('span',{text:'X '+V.selX+' · Y '+V.selY+' · '+V.selScalePct+'%'});
      this._elReadout=readout;
      wrap.appendChild(h('div',{style:{display:'flex',justifyContent:'flex-end',fontSize:'10.5px',color:'var(--muted)',fontWeight:'800',letterSpacing:'.4px',marginBottom:'9px'}},[readout]));
      wrap.appendChild(h('div',{style:LBL3},'X-POSITION (LINKS ↔ RECHTS)'));
      this._slX=h('input',{type:'range',min:'2',max:'98',step:'1',value:V.selX,style:{width:'100%',marginBottom:'10px'},onInput:V.onXInput,onChange:function(){ self.commit(); }});
      wrap.appendChild(this._slX);
      wrap.appendChild(h('div',{style:LBL3},'Y-POSITION (OBEN ↕ UNTEN)'));
      this._slY=h('input',{type:'range',min:'2',max:'98',step:'1',value:V.selY,style:{width:'100%',marginBottom:'10px'},onInput:V.onYInput,onChange:function(){ self.commit(); }});
      wrap.appendChild(this._slY);
      wrap.appendChild(h('div',{style:LBL3},'GRÖSSE'));
      this._slScale=h('input',{type:'range',min:'8',max:'80',step:'1',value:V.selScale,style:{width:'100%',marginBottom:'10px'},onInput:V.onScaleInput,onChange:function(){ self.commit(); }});
      wrap.appendChild(this._slScale);
      var rzLbl=h('div',{style:LBL3,text:'DREHUNG (Z) — '+V.selRz+'°'});
      this._elRz=rzLbl;
      wrap.appendChild(rzLbl);
      this._slRz=h('input',{type:'range',min:'-180',max:'180',step:'1',value:V.selRz,style:{width:'100%',marginBottom:'12px'},onInput:V.onRzInput,onChange:function(){ self.commit(); }});
      wrap.appendChild(this._slRz);
      var warpRow=h('div',{style:{display:'flex',gap:'7px',marginBottom:'9px'}},[ h('button',{style:V.warpBtnStyle,onClick:V.onToggleWarp,text:V.warpBtnLabel}) ]);
      if(V.warpOn){ warpRow.appendChild(h('button',{style:V.S.ghostBtnFull,onClick:V.onResetWarp},'Ecken zurück')); }
      wrap.appendChild(warpRow);
      if(V.warpOn){ wrap.appendChild(h('div',{style:{fontSize:'10.5px',color:'var(--cyan)',fontWeight:'700',lineHeight:'1.45',marginBottom:'10px'}},'Ecken-Modus aktiv — zieh die 4 cyan-Griffe auf der Karte, um die Kanten genau abzudecken.')); }
      wrap.appendChild(h('div',{style:LBL3},'ZURÜCKSETZEN'));
      wrap.appendChild(h('div',{style:{display:'flex',gap:'7px'}},[
        h('button',{style:V.S.ghostBtnFull,onClick:V.resetOne},'Gebäude'),
        h('button',{style:V.S.ghostBtnFull,onClick:V.resetBadge},'Badge'),
        h('button',{style:V.S.ghostBtnFull,onClick:V.resetPos},'Alle')
      ]));
      return wrap;
    }

    buildDetailStage(V){
      var sel=V.sel;
      var scene=h('div',{style:V.sceneStyle});
      if(sel.showCard){ scene.appendChild(h('div',{style:sel.cardStyle},[
        h('div',{style:{fontSize:'16px',fontWeight:'900',letterSpacing:'.4px',textTransform:'uppercase',color:'var(--text)'},text:sel.cardLabel}),
        h('div',{style:{fontSize:'12px',fontWeight:'700',color:'var(--muted)',marginTop:'6px'},text:sel.cardSub})
      ])); }
      if(sel.hasImg){ scene.appendChild(h('div',{style:sel.imgDivStyle})); }
      var stageKids=[
        h('div',{style:{position:'absolute',inset:'0',backgroundImage:'linear-gradient(rgba(34,230,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(34,230,255,.05) 1px,transparent 1px)',backgroundSize:'46px 46px'}}),
        scene,
        h('div',{style:V.envTintStyle})
      ];
      if(V.isNight) stageKids.push(h('div',{style:V.detailNightStyle}));
      if(V.isSnow) stageKids.push(h('div',{style:V.snowStyle}));
      stageKids.push(h('div',{style:'position:absolute;left:16px;top:16px;z-index:8;'+sel.numStyle,text:sel.numText}));
      return h('div',{style:{position:'relative',width:'100%',maxWidth:'1160px',aspectRatio:'1448 / 1086',maxHeight:'100%',border:'1px solid var(--line)',borderRadius:'14px',overflow:'hidden',boxShadow:'var(--shadow)',background:'radial-gradient(80% 60% at 50% 0%,rgba(34,230,255,.08),transparent 60%),radial-gradient(70% 60% at 30% 110%,rgba(48,242,156,.08),transparent 55%),linear-gradient(160deg,#0a1622,#070f18)'}},stageKids);
    }

    buildDetailRail(V){
      var self=this, sel=V.sel;
      var panels=[];
      panels.push(h('div',{style:V.S.panel},[
        h('div',{style:{fontSize:'21px',fontWeight:'900',letterSpacing:'.3px'},text:sel.name}),
        h('div',{style:{fontSize:'12px',color:'var(--muted)',fontWeight:'700',marginTop:'3px'},text:sel.purpose}),
        h('div',{style:{marginTop:'11px'}},[ h('span',{style:sel.statusBadge,text:sel.statusText}) ])
      ]));
      if(sel.isStadium){
        var capNum=h('div',{style:{fontSize:'28px',fontWeight:'900',color:'var(--cyan)',lineHeight:'1'},text:sel.capFmt});
        this._capNumEl=capNum;
        var capTier=h('div',{style:{fontSize:'11.5px',color:'var(--muted)',fontWeight:'700',margin:'4px 0 12px'},text:sel.tierName+' aktiv · Stufe per Kapazität'});
        this._capTierEl=capTier;
        var capSlider=h('input',{type:'range',min:'0',max:'110000',step:'1000',value:sel.capacity,style:{width:'100%'},onInput:V.onCapInput,onChange:function(){ self.commit(); }});
        this._slCap=capSlider;
        var ladder=h('div',{style:{display:'flex',flexDirection:'column',gap:'7px',marginTop:'13px'}}, V.tierLadder.map(function(t){
          var rowKids=[ h('div',{style:t.iconStyle,text:t.short}),
            h('div',{style:{flex:'1'}},[ h('div',{style:{fontWeight:'800',fontSize:'12.5px'},text:t.name}), h('div',{style:{fontSize:'10.5px',color:'var(--muted)',fontWeight:'700'},text:t.cap+' Zuschauer'}) ]) ];
          if(t.active){ rowKids.push(h('div',{style:{width:'9px',height:'9px',borderRadius:'999px',background:'var(--cyan)',boxShadow:'0 0 10px var(--cyan)'}})); }
          return h('div',{style:t.rowStyle,onClick:t.onClick},rowKids);
        }));
        panels.push(h('div',{style:V.S.panel},[ h('div',{style:V.S.title},[ h('span',{},'Zuschauer-Kapazität') ]), capNum, capTier, capSlider, ladder ]));
      }
      var buildKids=[ h('div',{style:V.S.title},[ h('span',{},sel.buildHeading) ]) ];
      if(sel.isBuilding){
        buildKids.push(h('div',{style:{fontSize:'12px',color:'var(--yellow)',fontWeight:'800',marginBottom:'9px'},text:sel.buildingText}));
        buildKids.push(h('div',{style:sel.progTrack},[ h('div',{style:sel.progFill}) ]));
        buildKids.push(h('div',{style:{display:'flex',gap:'8px',marginTop:'13px'}},[
          h('button',{style:V.S.primaryBtn,onClick:sel.finishFn},'Bau abschließen'),
          h('button',{style:V.S.ghostBtn,onClick:sel.cancelFn},'Abbrechen')
        ]));
      }
      if(sel.canBuild){
        buildKids.push(h('div',{style:{fontSize:'12px',color:'var(--muted)',fontWeight:'700',marginBottom:'11px',lineHeight:'1.4'},text:sel.buildHint}));
        buildKids.push(h('button',{style:V.S.primaryBtnFull,onClick:sel.buildFn,text:sel.buildLabel}));
      }
      if(sel.isMax){ buildKids.push(h('div',{style:{fontSize:'12.5px',color:'var(--green)',fontWeight:'800'},text:'Maximalstufe erreicht · '+sel.maxName})); }
      panels.push(h('div',{style:V.S.panel},buildKids));

      var verKids=[ h('div',{style:V.S.title},[ h('span',{},'Versionen testen'), h('span',{style:{fontSize:'10px',color:'var(--faint)'}},'Stufe direkt wählen') ]) ];
      verKids.push(h('div',{style:{display:'flex',gap:'7px',flexWrap:'wrap'}}, sel.ladder.map(function(L){
        var thumbInner=[];
        if(L.hasThumb){ thumbInner.push(h('div',{style:L.thumbImgStyle})); }
        if(L.empty){ thumbInner.push(h('span',{style:{fontSize:'9px',color:'var(--faint)',fontWeight:'800'}},'leer')); }
        return h('button',{style:L.style,onClick:L.onClick},[
          h('div',{style:L.thumbStyle},thumbInner),
          h('span',{style:{fontSize:'10.5px',fontWeight:'900',letterSpacing:'.2px'},text:L.label})
        ]);
      })));
      if(sel.hasNote){ verKids.push(h('div',{style:{marginTop:'11px',fontSize:'10.5px',color:'var(--faint)',fontWeight:'700',lineHeight:'1.4'},text:sel.note})); }
      panels.push(h('div',{style:V.S.panel},verKids));

      return h('aside',{'class':'vu-rail',style:{flex:'0 0 408px',borderLeft:'1px solid var(--line)',background:'rgba(5,14,22,.5)',overflowY:'auto',padding:'18px',display:'flex',flexDirection:'column',gap:'13px'}},panels);
    }
  }

  /* ---- boot ------------------------------------------------------- */
  function boot(){
    var mount=document.getElementById('vu-app');
    if(!mount) return;
    var app=new VU(mount);
    app.init();
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', boot); }
  else { boot(); }
})();
