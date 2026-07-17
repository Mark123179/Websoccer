/* ============================================================
   VEREINSNEWS — Netflix-Stil · Vanilla JS (kein Framework)
   Views: home (Übersicht) · article (Detail) · editor (Regie-Modus)
   Daten kommen aus window.VN_DATA (Django-Context), kein Demo-Modus.
   ============================================================ */
'use strict';

var _d = window.VN_DATA || {};
var SEASON   = _d.season  || 1;
var ART      = _d.art     || [];
var SOCIAL   = _d.social  || [];
var P        = _d.players || {};
var VN_CLUB_ID     = _d.club_id     || 0;
var VN_PUBLISH_URL = _d.publish_url || '';
var VN_CSRF        = _d.csrf        || '';
var VN_TODAY       = _d.today       || '01.01.2026';

var MOM = [0.6,0.3,-0.2,0.8,1,0.4,-0.5,-0.3,0.7,0.9,0.2,-0.6,0.5,1,0.8,0.3,-0.2,0.6];

var KATS = [
  {n:'Transfer-News',c:'#22e6ff'},{n:'Spielbericht',c:'#30f29c'},{n:'Interview',c:'#ffd166'},
  {n:'Vereinsstatement',c:'#e50914'},{n:'Pressemitteilung',c:'#9fb6c4'},{n:'Jugend/Akademie',c:'#7ef0c2'},
  {n:'Fans',c:'#ff5570'},{n:'Finanzen',c:'#ff9f1c'},{n:'Rekorde',c:'#f6c945'},{n:'Sonstiges',c:'#8fa8b8'}
];
var MEDIA_BASE='https://playwebsoccer.de/assets/media/';
var OUTLETS_DEFAULT=[
  {n:'Vereinsredaktion',slug:null,     d:'#e50914'},
  {n:'Kicker',          slug:'kicker',          d:'#d31419'},
  {n:'Sky Sports',      slug:'skysports',        d:'#0072c9'},
  {n:'90min',           slug:'90min',            d:'#14d95c'},
  {n:'OneFootball',     slug:'onefootball',      d:'#8fd0ff'},
  {n:'Eurosport',       slug:'eurosport',        d:'#ff6600'},
  {n:'BBC Sport',       slug:'bbcsport',         d:'#e8e2d6'},
  {n:'beIN Sports',     slug:'beinsports',       d:'#9f2fff'},
  {n:'Fox Sports',      slug:'foxsports',        d:'#c41230'},
  {n:'Goal.com',        slug:'goal',             d:'#22e6ff'},
  {n:"L'Équipe",        slug:'lequipe',          d:'#1e90ff'},
  {n:'Marca',           slug:'marca',            d:'#0075c2'},
  {n:'SportBild',       slug:'sportbild',        d:'#e50914'},
  {n:'talkSPORT',       slug:'talksport',        d:'#1a73e8'},
  {n:'The Guardian',    slug:'theguardian',      d:'#00789c'},
  {n:'Planet Football', slug:'planetfootball',   d:'#ffd166'},
  {n:'World Soccer',    slug:'worldsoccer',      d:'#22c55e'},
  {n:'Eleven Sports',   slug:'eleven',           d:'#f97316'},
  {n:'442',             slug:'442ch',            d:'#e50914'},
  {n:'Sport.fr',        slug:'sportfr',          d:'#0f5bb5'},
  {n:'Sport TV',        slug:'sporttv',          d:'#c00'},
  {n:'CNN Sport',       slug:'cnn',              d:'#e50914'},
  {n:'Toronto Sun',     slug:'torontosun',       d:'#e50914'},
  {n:'CNN Indonesia',   slug:'cnnindonesia',     d:'#cc0000'}
];
var OUTLETS=(_d.outlets&&_d.outlets.length)?_d.outlets:OUTLETS_DEFAULT;

function T(t){return{k:'text',text:t};}
function H(t){return{k:'head',text:t};}
function Q(t,a){return{k:'quote',text:t,autor:a};}
function PL(pid,f){return{k:'player',pid:pid,f:Object.assign({portrait:true,mw:true,tore:true,note:false,fit:false},f||{})};}
function M(f){return{k:'match',f:Object.assign({crests:true,score:true,scorers:true,momentum:false,zuschauer:false},f||{})};}
function IMG(src,cap){return{k:'image',src:src,cap:cap};}

var state={
  view:'home',art:null,edPrev:'artikel',published:[],
  ed:{
    titel:'',sub:'',kat:'Transfer-News',outlet:'Vereinsredaktion',
    card:{motiv:'wappen',pid:Object.keys(P)[0]||'',accent:'#22e6ff',customSrc:null},
    blocks:[T('')]
  }
};

/* ── Helpers ── */
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function katC(n){var k=KATS.find(function(k){return k.n===n;});return k?k.c:'#22e6ff';}
function outletOf(n){return OUTLETS.find(function(o){return o.n===n;})||OUTLETS[0];}
function ha(h,a){var x=parseInt(h.slice(1),16);return'rgba('+(x>>16&255)+','+(x>>8&255)+','+(x&255)+','+a+')';}
function markTc(hex){var x=parseInt(hex.slice(1),16);var l=.299*(x>>16&255)+.587*(x>>8&255)+.114*(x&255);return l>150?'#03141b':'#fff';}
function fmtViews(v){if(!v)return'Neu';return v>=1000?(v/1000).toFixed(1).replace('.',',')+' Aufrufe':v+' Aufrufe';}
function ALL(){return state.published.concat(ART);}
function findArt(id){return ALL().concat(SOCIAL).find(function(a){return a.id===id;});}
function bgFor(a){
  var hue=(a.card&&a.card.accent)||katC(a.kat);
  return'linear-gradient(178deg,rgba(3,7,12,.05) 28%,rgba(3,7,12,.92) 82%),radial-gradient(circle at 74% 10%,'+ha(hue,.38)+',transparent 62%),linear-gradient(140deg,#0e2130,#050b12)';
}
function cardArt(a){
  var cd=a.card;
  if(cd&&cd.motiv==='eigenes')return{custom:cd.customSrc,img:null,imgH:0};
  if(cd&&cd.motiv==='wappen')return{custom:null,img:_d.crest_url||null,imgH:100};
  if(cd&&cd.motiv==='spieler'){var p=P[cd.pid]||P[Object.keys(P)[0]];return{custom:null,img:p?p.img:null,imgH:124};}
  return{custom:null,img:a.img||null,imgH:a.imgH||120};
}
function mediaLogoURL(slug){return slug?MEDIA_BASE+slug+'_media.png':'';}
function markChip(name,big){
  var o=outletOf(name);
  if(o.slug){
    var h=big?'18px':'14px';
    return'<img class="outlet-logo-xs" src="'+mediaLogoURL(o.slug)+'" alt="'+esc(name)+'" style="height:'+h+';vertical-align:middle;margin-right:3px">';
  }
  var s=big?'min-width:17px;height:16px;font-size:8px;padding:0 4px':'';
  return'<i class="mark" style="background:'+o.d+';color:'+markTc(o.d)+';'+s+'">VR</i>';
}

/* ── Karten ── */
function cardHTML(a){
  var art=cardArt(a);
  var h='<div class="news-card" style="background:'+bgFor(a)+'" onclick="App.open(\''+a.id+'\')">';
  if(art.custom)h+='<img class="card-custom" src="'+art.custom+'" alt="">';
  else if(art.img)h+='<img class="card-motif" src="'+art.img+'" alt="" style="height:'+art.imgH+'px">';
  if(a.isNew)h+='<span class="badge-neu card-neu">NEU</span>';
  h+='<div class="card-overlay">'+
    '<span class="card-kat" style="color:'+katC(a.kat)+'">'+esc(a.kat)+'</span>'+
    '<strong class="card-title">'+esc(a.title)+'</strong>'+
    '<span class="meta-line">'+esc(a.date)+' · '+markChip(a.outlet)+esc(a.outlet)+'</span>'+
    '</div></div>';
  return h;
}
function topHTML(a,rank){
  var art=cardArt(a);
  var h='<div class="top-item" onclick="App.open(\''+a.id+'\')"><span class="top-rank">'+rank+'</span>'+
    '<div class="top-card" style="background:'+bgFor(a)+'">';
  if(art.custom)h+='<img class="card-custom" src="'+art.custom+'" alt="">';
  else if(art.img)h+='<img class="card-motif" src="'+art.img+'" alt="">';
  if(a.isNew)h+='<span class="badge-neu card-neu" style="top:6px;left:6px;font-size:8px;padding:2px 5px">NEU</span>';
  h+='<div class="card-overlay"><strong class="card-title">'+esc(a.title)+'</strong>'+
    '<span class="views">'+fmtViews(a.views)+'</span></div></div></div>';
  return h;
}

/* ── Übersicht ── */
function homeHTML(){
  var all=ALL();
  if(!all.length){
    return'<div style="text-align:center;padding:80px 20px;color:rgba(244,251,255,.4)">'+
      '<div style="font-size:48px;margin-bottom:16px">📰</div>'+
      '<div style="font-size:18px;font-weight:800;margin-bottom:8px">Noch keine News vorhanden</div>'+
      '<div style="font-size:14px;font-weight:600">Erstelle deine erste Vereinsmeldung mit dem roten Button oben.</div></div>';
  }
  var feat=all[0];
  var fa=cardArt(feat);
  var top=all.concat(SOCIAL).slice().sort(function(x,y){return(y.views||0)-(x.views||0);}).slice(0,10);
  var fans=all.filter(function(a){return a.kat==='Fans';}).concat(SOCIAL);

  var h='<div class="vn-billboard">';
  if(_d.stadium_url)h+='<img class="bb-bg" src="'+_d.stadium_url+'" alt="">';
  else h+='<div class="bb-bg" style="background:linear-gradient(135deg,#0a1c2a,#050b12)"></div>';
  if(fa.custom)h+='<img class="card-custom bb-bg" src="'+fa.custom+'" alt="">';
  h+='<div class="bb-shade"></div>';
  if(!fa.custom&&fa.img)h+='<img class="bb-motif" src="'+fa.img+'" alt="">';
  if(feat.isNew)h+='<span class="badge-neu" style="position:absolute;top:16px;left:16px;font-size:10px;padding:4px 9px">NEU</span>';
  h+='<div class="bb-body">'+
    '<div class="bb-kicker">'+N_SVG+'<span>GERADE ERSCHIENEN · '+esc(feat.kat.toUpperCase())+'</span></div>'+
    '<h2>'+esc(feat.title)+'</h2>'+
    '<p>'+esc(feat.sub)+'</p>'+
    '<span class="meta-line" style="font-size:11px;font-weight:800;color:rgba(244,251,255,.6)">'+esc(feat.date)+' · '+markChip(feat.outlet,true)+esc(feat.outlet)+'</span>'+
    '<div style="display:flex;gap:10px;margin-top:4px">'+
    '<button class="btn-red" style="font-size:14px;padding:12px 22px" onclick="App.open(\''+feat.id+'\')">'+PLAY_SVG+'Jetzt lesen</button>'+
    '<button class="btn-hero-soft" onclick="App.open(\''+feat.id+'\')">Mehr Infos</button>'+
    '</div></div>'+
    '<span class="bb-season">S'+SEASON+'</span></div>';

  h+='<h3 class="vn-row-title">Neu im Verein</h3><div class="vn-row">'+all.slice(0,7).map(cardHTML).join('')+'</div>';
  h+='<h3 class="vn-row-title">Top 10 nach Klicks</h3><div class="vn-row top10">'+top.map(function(a,i){return topHTML(a,i+1);}).join('')+'</div>';
  if(fans.length){
    h+='<h3 class="vn-row-title" style="margin-bottom:4px">Fans &amp; Medien</h3>'+
      '<span class="vn-row-sub">Beiträge deiner Fans und Social News, in denen dein Verein erwähnt wird</span>'+
      '<div class="vn-row">'+fans.map(cardHTML).join('')+'</div>';
  }
  return h;
}

/* ── Artikel-Blöcke ── */
function blocksHTML(blocks){
  return'<div class="art-blocks">'+blocks.map(function(b){
    if(b.k==='text')return'<p>'+esc(b.text)+'</p>';
    if(b.k==='head')return'<h3>'+esc(b.text)+'</h3>';
    if(b.k==='quote')return'<div class="blk-quote"><span class="bar"></span><div><p>„'+esc(b.text||'…')+'"</p><span class="autor">— '+esc(b.autor||'Unbekannt')+'</span></div></div>';
    if(b.k==='player'){
      var p=P[b.pid]||P[Object.keys(P)[0]];
      if(!p)return'';
      var f=b.f||{};
      var stats=[];
      if(f.mw&&p.mw)stats.push(['Marktwert',p.mw,'#30f29c']);
      if(f.tore&&p.tore!=null)stats.push(['Saisontore',p.tore,'#22e6ff']);
      if(f.note&&p.note)stats.push(['Ø-Note',p.note,'#30f29c']);
      if(f.fit&&p.fit)stats.push(['Fitness',p.fit,'#30f29c']);
      return'<div class="blk-player">'+
        (f.portrait!==false&&p.img?'<img src="'+p.img+'" onerror="this.onerror=null;this.src=\''+(window.wsDefaultPlayerUrl||'/static/assets/players/default_player.jpg')+'\'" alt="">':'')+
        '<div style="display:flex;flex-direction:column;gap:8px;min-width:0">'+
        '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><strong style="font-size:17px;font-weight:900">'+esc(p.n)+'</strong><span class="pos-badge">'+esc(p.pos)+'</span>'+(p.age?'<span style="font-size:11px;font-weight:800;color:rgba(244,251,255,.35);border:1px solid rgba(244,251,255,.15);border-radius:4px;padding:1px 5px">'+p.age+' J.</span>':'')+(p.flag?'<img src="'+p.flag+'" alt="'+esc(p.meta||'')+'" title="'+esc(p.meta||'')+'" class="nat-flag">':p.meta?'<span style="font-size:12px;font-weight:700;color:rgba(244,251,255,.5)">'+esc(p.meta)+'</span>':'')+'</div>'+
        '<div style="display:flex;gap:8px;flex-wrap:wrap">'+stats.map(function(s){return'<span class="stat-chip"><em>'+s[0]+'</em><b style="color:'+s[2]+'">'+s[1]+'</b></span>';}).join('')+'</div>'+
        '</div></div>';
    }
    if(b.k==='match'){
      var f2=b.f||{};
      var lm=_d.last_match;
      var hName=lm?lm.home_name:'Heimteam';
      var aName=lm?lm.away_name:'Auswärts';
      var hCrest=lm?lm.home_crest:(_d.crest_url||'');
      var aCrest=lm?lm.away_crest:'';
      var score=lm?lm.score:'?:?';
      var scorers=lm?lm.scorers:[];
      var crowd=lm?lm.crowd:'';
      var h='<div class="blk-match"><div class="m-meta">'+
        (_d.league_logo?'<img src="'+_d.league_logo+'" alt="" style="height:14px">':'')+
        esc(_d.league_name||'Liga')+'</div>'+
        '<div class="m-grid"><div class="m-team">'+
        (f2.crests!==false&&hCrest?'<img src="'+hCrest+'" alt="" style="height:52px;object-fit:contain;filter:drop-shadow(0 0 14px rgba(34,230,255,.28))">':'')+
        '<span>'+esc(hName)+'</span></div>'+
        (f2.score!==false?'<span class="m-score">'+esc(score)+'</span>':'<span></span>')+
        '<div class="m-team">'+
        (f2.crests!==false&&aCrest?'<img src="'+aCrest+'" alt="" style="height:52px;object-fit:contain;filter:drop-shadow(0 0 14px rgba(34,230,255,.28))">':'')+
        '<span>'+esc(aName)+'</span></div></div>';
      if(f2.scorers&&scorers.length)h+='<div class="m-scorers">'+scorers.map(function(g){return'<span><i class="m-min">'+esc(g[0])+'′</i>'+esc(g[1])+'</span>';}).join('')+'</div>';
      if(f2.momentum&&lm&&lm.momentum)h+='<div style="border-top:1px solid rgba(44,231,255,.14);padding-top:10px"><div class="micro-label" style="text-align:center;margin-bottom:6px">Matchmomentum</div><div class="m-momentum">'+
        MOM.map(function(v){return'<span style="height:'+Math.round(6+Math.abs(v)*20)+'px;background:'+(v>0?ha('#30f29c',.35+.5*Math.abs(v)):ha('#ff5570',.35+.5*Math.abs(v)))+';align-self:'+(v>0?'flex-start':'flex-end')+'"></span>';}).join('')+'</div></div>';
      if(f2.zuschauer&&crowd)h+='<div style="border-top:1px solid rgba(44,231,255,.14);padding-top:8px;text-align:center;font-size:12px;font-weight:800;color:rgba(244,251,255,.6)">Zuschauer <b style="color:#22e6ff">'+esc(crowd)+'</b></div>';
      return h+'</div>';
    }
    if(b.k==='image'){
      return'<figure class="blk-image" style="margin:0">'+
        (b.src?'<img src="'+b.src+'" alt="">':'<div class="img-placeholder">Bild-Platzhalter</div>')+
        '<figcaption>'+esc(b.cap||'')+'</figcaption></figure>';
    }
    if(b.k==='motm'){
      var mo=_d.motm;
      if(!mo)return'<div class="blk-player" style="justify-content:center;text-align:center;padding:16px 20px;color:rgba(244,251,255,.3)">★ Noch kein Spieler des Spiels verfügbar</div>';
      return'<div class="blk-player" style="flex-direction:column;align-items:flex-start;gap:12px;border-color:rgba(255,213,0,.3);background:linear-gradient(135deg,rgba(255,213,0,.05),rgba(255,195,0,.02))">'+
        '<div style="font-size:10px;font-weight:900;letter-spacing:1.5px;color:#ffd166;display:flex;align-items:center;gap:6px"><span>★</span> SPIELER DES SPIELS</div>'+
        '<div style="display:flex;align-items:center;gap:14px">'+
        (mo.img?'<img src="'+mo.img+'" onerror="this.onerror=null;this.src=\''+(window.wsDefaultPlayerUrl||'/static/assets/players/default_player.jpg')+'\'" alt="" style="height:72px;width:54px;object-fit:cover;object-position:top center;border-radius:6px;filter:drop-shadow(0 0 10px rgba(255,213,0,.28))">':'')+
        '<div style="display:flex;flex-direction:column;gap:8px">'+
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'+
        '<strong style="font-size:17px;font-weight:900">'+esc(mo.name)+'</strong>'+
        (mo.pos?'<span class="pos-badge">'+esc(mo.pos)+'</span>':'')+
        '</div>'+
        '<div style="display:flex;gap:8px;flex-wrap:wrap">'+
        (mo.grade?'<span class="stat-chip"><em>Note</em><b style="color:#ffd166">'+mo.grade.toFixed(1)+'</b></span>':'')+
        (mo.tore?'<span class="stat-chip"><em>Tore</em><b style="color:#22e6ff">'+mo.tore+'</b></span>':'')+
        (mo.assists?'<span class="stat-chip"><em>Vorlagen</em><b style="color:#30f29c">'+mo.assists+'</b></span>':'')+
        '</div></div></div></div>';
    }
    return'';
  }).join('')+'</div>';
}

/* ── Artikel-Ansicht ── */
function articleHTML(a){
  var art=cardArt(a);
  var kc=katC(a.kat),o=outletOf(a.outlet);
  var bigH=Math.min(250,Math.round((art.imgH||120)*1.9));
  return'<a class="back-link" onclick="App.goHome()">‹ Zurück zur Übersicht</a>'+
    '<div class="art-hero" style="background:'+bgFor(a).replace('.38','.4')+'">'+
    (art.custom?'<img class="card-custom" src="'+art.custom+'" alt=""><div class="bb-shade"></div>':'')+
    (!art.custom&&art.img?'<img class="art-motif" src="'+art.img+'" alt="" style="height:'+bigH+'px">':'')+
    '<div class="art-body">'+
    '<div style="display:flex;gap:10px;flex-wrap:wrap">'+
    '<span class="pill" style="border:1px solid '+kc+';color:'+kc+';text-transform:uppercase;letter-spacing:.8px;font-weight:900">'+esc(a.kat)+'</span>'+
    '<span class="pill" style="border:1px solid rgba(255,255,255,.14);color:rgba(244,251,255,.75)">'+(o.slug?'<img class="outlet-logo-xs" src="'+mediaLogoURL(o.slug)+'" alt="'+esc(a.outlet)+'" style="height:16px">':'<i style="width:7px;height:7px;border-radius:999px;background:'+o.d+'"></i>')+'Erschienen bei '+esc(a.outlet)+'</span>'+
    '</div><h2>'+esc(a.title)+'</h2></div></div>'+
    '<div class="art-content">'+
    '<p class="art-lead">'+esc(a.sub)+'</p>'+
    '<div class="art-meta"><span>'+esc(a.date)+'</span><span>·</span><span>'+fmtViews(a.views)+'</span><span>·</span><span style="color:#e50914">Vereinsredaktion '+esc(_d.club_abbr||'')+'</span></div>'+
    blocksHTML(a.blocks||[])+'</div>';
}

/* ── Editor (Regie-Modus) ── */
var LBL={text:'Fließtext',head:'Zwischentitel',quote:'Zitat',player:'Spielerkarte',match:'Spielkarte',motm:'Spieler d. Spiels',image:'Bild'};
var PTOG=[['portrait','Portrait'],['mw','Marktwert'],['tore','Tore'],['note','Ø-Note'],['fit','Fitness']];
var MTOG=[['crests','Wappen'],['score','Ergebnis'],['scorers','Torschützen'],['momentum','Matchmomentum'],['zuschauer','Zuschauer']];

function blockEdHTML(b,i){
  var h='<div class="panel" style="padding:12px 14px"><div class="blk-head">'+
    '<span class="blk-tag">'+(i+1)+' · '+LBL[b.k]+'</span><span style="flex:1"></span>'+
    '<button class="blk-btn" onclick="App.moveB('+i+',-1)">↑</button>'+
    '<button class="blk-btn" onclick="App.moveB('+i+',1)">↓</button>'+
    '<button class="blk-btn del" onclick="App.delB('+i+')">✕</button></div>';
  if(b.k==='text'||b.k==='head'){
    h+='<textarea class="inp" placeholder="Text schreiben…" oninput="App.updB('+i+',\'text\',this.value)">'+esc(b.text)+'</textarea>';
  }else if(b.k==='quote'){
    h+='<textarea class="inp quote" placeholder="Zitat…" oninput="App.updB('+i+',\'text\',this.value)">'+esc(b.text)+'</textarea>'+
      '<input class="inp small" placeholder="Wer sagt das?" value="'+esc(b.autor)+'" oninput="App.updB('+i+',\'autor\',this.value)">';
  }else if(b.k==='player'){
    var pkeys=Object.keys(P);
    h+='<select class="inp" style="margin-bottom:6px" onchange="App.updB('+i+',\'pid\',this.value)">'+
      pkeys.map(function(pid){return'<option value="'+pid+'"'+(b.pid===pid?' selected':'')+'>'+esc(P[pid].pos?P[pid].n+' ('+P[pid].pos+')':P[pid].n)+'</option>';}).join('')+
    '</select>'+
    '<span class="micro-label">Infos aus dem Spielerprofil</span><div class="chips">'+PTOG.map(function(t){
      return'<button class="chip pill-t'+(b.f[t[0]]?' on-green':'')+'" onclick="App.togB('+i+',\''+t[0]+'\')">'+t[1]+'</button>';
    }).join('')+'</div>';
  }else if(b.k==='match'){
    var lm=_d.last_match;
    var mLabel=lm?(lm.home_name+' '+lm.score+' '+lm.away_name):'Letztes Spiel';
    h+='<div style="display:flex;align-items:center;gap:8px;font-size:12px;font-weight:800;color:rgba(244,251,255,.7)">'+
      '<span style="color:rgba(244,251,255,.5)">'+esc(mLabel)+'</span></div>'+
      '<span class="micro-label">Infos aus dem Spielbericht</span><div class="chips">'+MTOG.map(function(t){
        return'<button class="chip pill-t'+(b.f[t[0]]?' on-green':'')+'" onclick="App.togB('+i+',\''+t[0]+'\')">'+t[1]+'</button>';
      }).join('')+'</div>';
  }else if(b.k==='image'){
    h+='<div class="dropzone" onclick="App.pickImg('+i+')" ondragover="event.preventDefault();this.classList.add(\'over\')" ondragleave="this.classList.remove(\'over\')" ondrop="App.dropImg(event,'+i+')">'+
      (b.src?'<img src="'+b.src+'" alt="">':'Bild hierher ziehen oder klicken')+'</div>'+
      '<input class="inp small" placeholder="Bildunterschrift…" value="'+esc(b.cap||'')+'" oninput="App.updB('+i+',\'cap\',this.value)">';
  }else if(b.k==='motm'){
    var mo=_d.motm;
    h+='<div style="font-size:12px;font-weight:700;color:rgba(244,251,255,.55);padding:4px 0;display:flex;align-items:center;gap:8px">'+
      (mo?'<span style="color:#ffd166">★</span>'+esc(mo.name)+(mo.grade?' &nbsp;·&nbsp; Note: '+mo.grade.toFixed(1):'')+(mo.tore?' &nbsp;·&nbsp; '+mo.tore+' Tor(e)':''):'Kein Spieler des Spiels — Daten erscheinen nach dem nächsten Spiel.')+
      '</div>';
  }
  return h+'</div>';
}

function editorHTML(){
  var ed=state.ed;
  var h='<div class="ed-top"><span class="ed-label">NEWS-STUDIO · REGIE-MODUS</span><div style="display:flex;gap:10px">'+
    '<button class="btn-ghost" onclick="App.goHome()">Entwurf speichern</button>'+
    '<button class="btn-red" onclick="App.publish()">'+PLAY_SVG+'Veröffentlichen</button></div></div>'+
    '<div class="ed-grid"><div style="display:flex;flex-direction:column;gap:14px">';

  h+='<div class="panel"><span class="panel-label">Schlagzeile</span>'+
    '<input class="inp" placeholder="Überschrift…" value="'+esc(ed.titel)+'" oninput="App.setEd(\'titel\',this.value)">'+
    '<input class="inp sub" placeholder="Untertitel…" value="'+esc(ed.sub)+'" oninput="App.setEd(\'sub\',this.value)"></div>';

  h+='<div class="panel"><span class="panel-label">Kategorie</span><div class="chips">'+KATS.map(function(k){
    var on=ed.kat===k.n;
    return'<button class="chip" style="'+(on?'background:'+ha(k.c,.14)+';border-color:'+ha(k.c,.55)+';color:'+k.c:'')+'" onclick="App.setEd(\'kat\',\''+k.n+'\')">'+k.n+'</button>';
  }).join('')+'</div></div>';

  var selOut=outletOf(ed.outlet);
  h+='<div class="panel"><span class="panel-label">Ausstrahlung über</span>'+
    '<div class="outlet-picker">'+
    (selOut.slug?'<img class="outlet-logo-prev" src="'+mediaLogoURL(selOut.slug)+'" alt="'+esc(selOut.n)+'">':
      '<span class="outlet-vr-badge">'+esc(selOut.n)+'</span>')+
    '<select class="inp outlet-sel" onchange="App.setEd(\'outlet\',this.value)">'+
    OUTLETS.map(function(o){
      return'<option value="'+esc(o.n)+'"'+(ed.outlet===o.n?' selected':'')+'>'+esc(o.n)+'</option>';
    }).join('')+
    '</select></div>'+
    '<span class="hint">Deine News erscheint als Beitrag der Vereinsredaktion — das gewählte Blatt greift sie auf und zitiert den Verein.</span></div>';

  h+='<div class="panel" style="border-color:rgba(44,231,255,.28)"><div class="blk-head"><span class="panel-label cyan">News-Karte gestalten</span><span style="flex:1"></span>'+
    '<button class="chip on-cyan" onclick="App.setPrev(\'karte\')">Vorschau</button></div>'+
    '<span class="micro-label">Motiv</span><div class="chips">'+[['wappen','Wappen'],['spieler','Spielerbild'],['eigenes','Eigenes Bild']].map(function(m){
      return'<button class="chip'+(ed.card.motiv===m[0]?' on-cyan':'')+'" onclick="App.setCard(\'motiv\',\''+m[0]+'\')">'+m[1]+'</button>';
    }).join('')+'</div>';
  if(ed.card.motiv==='spieler'){
    h+='<select class="inp" style="margin-bottom:6px" onchange="App.setCard(\'pid\',this.value)">'+
      Object.keys(P).map(function(pid){
        return'<option value="'+pid+'"'+(ed.card.pid===pid?' selected':'')+'>'+esc(P[pid].pos?P[pid].n+' ('+P[pid].pos+')':P[pid].n)+'</option>';
      }).join('')+
    '</select>';
  }
  if(ed.card.motiv==='eigenes'){
    h+='<div class="dropzone" onclick="App.pickImg(-1)" ondragover="event.preventDefault();this.classList.add(\'over\')" ondragleave="this.classList.remove(\'over\')" ondrop="App.dropImg(event,-1)">'+
      (ed.card.customSrc?'<img src="'+ed.card.customSrc+'" alt="">':'Hintergrundbild hierher ziehen oder klicken')+'</div>';
  }
  h+='<span class="micro-label">Akzentfarbe</span><div style="display:flex;gap:8px">'+['#22e6ff','#e50914','#30f29c','#ffd166'].map(function(c){
    return'<button class="swatch'+(ed.card.accent===c?' on':'')+'" style="background:'+c+';box-shadow:0 0 10px '+c+'" onclick="App.setCard(\'accent\',\''+c+'\')"></button>';
  }).join('')+'</div></div>';

  h+='<span class="panel-label" style="padding:0 2px">Bausteine</span>'+
    ed.blocks.map(blockEdHTML).join('')+
    '<div class="panel add-panel"><span class="micro-label">+ Block hinzufügen</span><div class="chips">'+
    [['text','Fließtext','T'],['head','Zwischentitel','H2'],['quote','Zitat','„"'],['player','Spielerkarte','SP'],['match','Spielkarte','VS'],['motm','Spieler d. Spiels','★'],['image','Bild','IMG']].map(function(p){
      return'<button class="chip add-chip" onclick="App.addB(\''+p[0]+'\')"><b>'+p[2]+'</b>'+p[1]+'</button>';
    }).join('')+'</div></div>';

  h+='</div>';

  h+='<div class="prev-wrap"><div class="prev-head"><span class="prev-title">LIVE-VORSCHAU</span>'+
    '<div class="prev-toggle"><button class="'+(state.edPrev==='artikel'?'on':'')+'" onclick="App.setPrev(\'artikel\')">Artikel</button>'+
    '<button class="'+(state.edPrev==='karte'?'on':'')+'" onclick="App.setPrev(\'karte\')">News-Karte</button></div>'+
    '<span class="prev-live"><i></i>LIVE</span></div><div id="prevPane">'+previewHTML()+'</div></div>';

  return h+'</div><input type="file" id="imgInput" accept="image/*" style="display:none">';
}

function previewHTML(){
  var ed=state.ed;
  if(state.edPrev==='karte'){
    var pa={id:'_pv',kat:ed.kat,outlet:ed.outlet,title:ed.titel||'Ohne Titel',date:VN_TODAY,isNew:true,card:ed.card};
    var art=cardArt(pa);
    return'<div class="prev-cardstage"><span class="prev-title" style="text-transform:uppercase">So erscheint deine News in den Reihen</span>'+
      '<div class="prev-bigcard" style="background:'+bgFor(pa)+'">'+
      (art.custom?'<img class="card-custom" src="'+art.custom+'" alt="">':'')+
      (!art.custom&&art.img?'<img class="card-motif" src="'+art.img+'" alt="" style="position:absolute;right:-4px;bottom:0;height:'+Math.round(art.imgH*1.35)+'px;object-fit:contain">':'')+
      '<span class="badge-neu" style="position:absolute;top:10px;left:10px">NEU</span>'+
      '<div class="card-overlay"><span class="card-kat" style="color:'+katC(ed.kat)+'">'+esc(ed.kat)+'</span>'+
      '<strong class="card-title">'+esc(ed.titel||'Ohne Titel')+'</strong>'+
      '<span class="meta-line" style="font-size:11px">'+VN_TODAY+' · '+markChip(ed.outlet,true)+esc(ed.outlet)+'</span></div></div>'+
      '<span class="hint" style="text-align:center;max-width:340px">Motiv, Spieler und Akzentfarbe stellst du links unter „News-Karte gestalten" ein.</span></div>';
  }
  var kc=katC(ed.kat),o=outletOf(ed.outlet);
  return'<div class="prev-body">'+
    '<div style="display:flex;gap:8px;flex-wrap:wrap">'+
    '<span class="pill" style="border:1px solid '+kc+';color:'+kc+';font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.8px;background:transparent">'+esc(ed.kat)+'</span>'+
    '<span class="pill" style="border:1px solid rgba(255,255,255,.14);color:rgba(244,251,255,.7);font-size:10px;background:transparent">'+(o.slug?'<img class="outlet-logo-xs" src="'+mediaLogoURL(o.slug)+'" alt="'+esc(ed.outlet)+'" style="height:14px">':'<i style="width:7px;height:7px;border-radius:999px;background:'+o.d+'"></i>')+esc(ed.outlet)+'</span></div>'+
    '<h2>'+esc(ed.titel)+'</h2><p class="prev-sub">'+esc(ed.sub)+'</p><div class="prev-sep"></div>'+
    blocksHTML(ed.blocks)+'</div>';
}

/* ── SVGs ── */
var N_SVG='<svg viewBox="0 0 34 60"><path d="M0 0h10v60H0z" fill="#8f070e"/><path d="M24 0h10v60H24z" fill="#8f070e"/><path d="M0 0h10l24 60H24z" fill="#e50914"/></svg>';
var N_SVG_BIG='<svg viewBox="0 0 34 60" style="width:24px;height:42px"><path d="M0 0h10v60H0z" fill="#8f070e"/><path d="M24 0h10v60H24z" fill="#8f070e"/><path d="M0 0h10l24 60H24z" fill="#e50914"/></svg>';
var PLAY_SVG='<svg viewBox="0 0 24 24" style="width:13px;height:13px" fill="currentColor"><path d="M6 4l14 8-14 8z"/></svg>';

/* ── Render ── */
function render(){
  var total=ALL().length;
  var h='<div class="vn-head"><div class="vn-brand">'+N_SVG_BIG+
    '<div><h1 class="vn-title">VEREINS<b>N</b>EWS</h1>'+
    '<span class="vn-sub">'+total+' Beiträge · Saison '+SEASON+' · Ausstrahlung über '+OUTLETS.length+' Blätter</span></div></div>';
  if(state.view==='home')h+='<button class="btn-red" onclick="App.goEditor()">+ Neue News</button>';
  h+='</div>';
  if(state.view==='home')h+=homeHTML();
  if(state.view==='article')h+=articleHTML(state.art);
  if(state.view==='editor')h+=editorHTML();
  document.getElementById('vereinsnews-app').innerHTML=h;
}

/* ── App-API ── */
window.App={
  open:function(id){var a=findArt(id);if(a){state.view='article';state.art=a;render();window.scrollTo(0,0);}},
  goHome:function(){state.view='home';render();window.scrollTo(0,0);},
  goEditor:function(){state.view='editor';render();window.scrollTo(0,0);},
  setEd:function(k,v){state.ed[k]=v;if(k==='kat'||k==='outlet')render();else this.sync();},
  setCard:function(k,v){state.ed.card[k]=v;render();},
  setPrev:function(p){state.edPrev=p;render();},
  updB:function(i,k,v){state.ed.blocks[i][k]=v;if(k==='pid')render();else this.sync();},
  togB:function(i,k){var b=state.ed.blocks[i];b.f[k]=!b.f[k];render();},
  moveB:function(i,d){var bl=state.ed.blocks,j=i+d;if(j<0||j>=bl.length)return;var t=bl[i];bl[i]=bl[j];bl[j]=t;render();},
  delB:function(i){state.ed.blocks.splice(i,1);render();},
  addB:function(k){
    var defs={text:T(''),head:H(''),quote:Q('',''),player:PL(Object.keys(P)[0]||''),match:M(),motm:{k:'motm'},image:IMG(null,'')};
    state.ed.blocks.push(JSON.parse(JSON.stringify(defs[k]||{k:k})));render();
  },
  pickImg:function(i){
    var inp=document.getElementById('imgInput');
    inp.onchange=function(){if(inp.files[0])App.readImg(inp.files[0],i);inp.value='';};
    inp.click();
  },
  dropImg:function(e,i){e.preventDefault();var f=e.dataTransfer.files[0];if(f)App.readImg(f,i);},
  readImg:function(file,i){
    var r=new FileReader();
    r.onload=function(){
      if(i<0)state.ed.card.customSrc=r.result;
      else state.ed.blocks[i].src=r.result;
      render();
    };
    r.readAsDataURL(file);
  },
  publish:function(){
    var e=state.ed;
    if(!e.titel.trim()){alert('Bitte eine Schlagzeile eingeben.');return;}
    var payload={
      titel:e.titel,sub:e.sub,kat:e.kat,outlet:e.outlet,
      card:e.card,blocks:e.blocks
    };
    var self=this;
    fetch(VN_PUBLISH_URL,{
      method:'POST',
      headers:{'Content-Type':'application/json','X-CSRFToken':VN_CSRF},
      body:JSON.stringify(payload)
    }).then(function(r){return r.json();}).then(function(data){
      if(data.ok){
        state.published.unshift(data.article);
        state.view='home';render();window.scrollTo(0,0);
      }else{
        alert(data.error||'Fehler beim Veröffentlichen.');
      }
    }).catch(function(){alert('Netzwerkfehler. Bitte erneut versuchen.');});
  },
  sync:function(){var p=document.getElementById('prevPane');if(p)p.innerHTML=previewHTML();}
};

// URL-Hash → Artikel direkt öffnen (z. B. aus Übersicht verlinkt)
(function(){
  var h=window.location.hash;
  if(h){var a=findArt(h.slice(1));if(a){state.view='article';state.art=a;}}
})();
render();
