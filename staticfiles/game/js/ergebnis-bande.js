/* ============================================================
   ERGEBNIS-BANDE — rendert den Ticker aus einem Daten-Array.
   Erweiterung: Wappen-Links (club url) + Ergebnis-Links (match url).
   ============================================================ */
(function () {
  'use strict';

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  }

  function teamNode(team) {
    var frag = document.createDocumentFragment();
    if (team.crest) {
      var img = el('img', 'eb-crest');
      img.src = team.crest;
      img.alt = team.abbr || '';
      img.loading = 'lazy';
      if (team.url && team.url !== '#') {
        var link = document.createElement('a');
        link.className = 'eb-crest-link';
        link.href = team.url;
        link.setAttribute('aria-label', team.abbr || '');
        link.appendChild(img);
        frag.appendChild(link);
      } else {
        frag.appendChild(img);
      }
    } else {
      frag.appendChild(el('span', 'eb-monogram', team.abbr || '?'));
    }
    return frag;
  }

  function scoreClass(match, ownClub) {
    if (!ownClub) return '';
    var isHome = match.home.abbr === ownClub;
    var isAway = match.away.abbr === ownClub;
    if (!isHome && !isAway) return '';
    var own = isHome ? match.homeGoals : match.awayGoals;
    var opp = isHome ? match.awayGoals : match.homeGoals;
    return own > opp ? 'eb-win' : own < opp ? 'eb-loss' : 'eb-draw';
  }

  function buildCopy(data, opts, hidden) {
    var copy = el('div', 'eb-copy');
    if (hidden) copy.setAttribute('aria-hidden', 'true');

    data.forEach(function (seg, si) {
      var segment = el('div', 'eb-segment');
      if (si > 0) segment.appendChild(el('span', 'eb-divider'));

      var comp = el('div', 'eb-comp');
      if (seg.logo) {
        var logo = el('img', 'eb-comp-logo');
        logo.src = seg.logo;
        logo.alt = seg.name;
        comp.appendChild(logo);
      }
      comp.appendChild(el('span', 'eb-comp-name', seg.name));
      comp.appendChild(el('span', 'eb-comp-round', '\u00b7 ' + seg.round));
      segment.appendChild(comp);

      seg.matches.forEach(function (m, mi) {
        var wrap = el('div', 'eb-match-wrap');
        if (mi > 0) wrap.appendChild(el('span', 'eb-match-divider'));

        var isOwn = opts.ownClub &&
          (m.home.abbr === opts.ownClub || m.away.abbr === opts.ownClub);
        var match = el('div', 'eb-match' + (isOwn && opts.highlightOwnClub !== false ? ' eb-own' : ''));

        match.appendChild(teamNode(m.home));
        if (opts.showAbbr !== false && m.home.crest) {
          match.appendChild(el('span', 'eb-abbr', m.home.abbr));
        }

        var cls = opts.highlightOwnClub !== false ? scoreClass(m, opts.ownClub) : '';
        var scoreTag = (m.matchUrl && m.matchUrl !== '#') ? 'a' : 'span';
        var scoreEl = el(scoreTag, 'eb-score' + (cls ? ' ' + cls : ''), m.homeGoals + ':' + m.awayGoals);
        if (scoreTag === 'a') { scoreEl.href = m.matchUrl; }
        match.appendChild(scoreEl);

        if (opts.showAbbr !== false && m.away.crest) {
          match.appendChild(el('span', 'eb-abbr', m.away.abbr));
        }
        match.appendChild(teamNode(m.away));

        wrap.appendChild(match);
        segment.appendChild(wrap);
      });

      copy.appendChild(segment);
    });

    return copy;
  }

  function mount(target, data, opts) {
    opts = opts || {};
    var root = typeof target === 'string' ? document.querySelector(target) : target;
    if (!root) { return; }
    if (!data || !data.length) { root.style.display = 'none'; return; }

    var bande = el('div', 'eb-bande');
    bande.dataset.pauseOnHover = String(opts.pauseOnHover !== false);
    bande.style.setProperty('--eb-duration', (opts.speed || 100) + 's');

    var cap = el('div', 'eb-cap');
    cap.appendChild(el('span', 'eb-cap-dot'));
    cap.appendChild(el('span', 'eb-cap-label', opts.label || 'Ergebnisse'));
    bande.appendChild(cap);

    var viewport = el('div', 'eb-viewport');
    var track = el('div', 'eb-track');
    track.appendChild(buildCopy(data, opts, false));
    track.appendChild(buildCopy(data, opts, true));
    viewport.appendChild(track);
    bande.appendChild(viewport);

    root.innerHTML = '';
    root.appendChild(bande);
    return bande;
  }

  window.ErgebnisBande = { mount: mount };
})();
