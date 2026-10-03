/* Schiedsrichterprofil als Hover-Karte, wie das Wetter-Popup. */
(function(){
  'use strict';
  var popup = document.getElementById('ref-popup');
  if (!popup) return;
  var current = null;
  var GAP = 9;
  var EDGE = 8;

  function place(){
    if (!current) return;
    var scale = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--game-scale')
    ) || 1;
    var rect = current.getBoundingClientRect();
    var width = popup.offsetWidth * scale;
    var height = popup.offsetHeight * scale;
    var left = rect.left + rect.width / 2 - width / 2;
    left = Math.max(EDGE, Math.min(left, window.innerWidth - width - EDGE));
    var top = rect.top - height - GAP * scale;
    if (top < EDGE) top = rect.bottom + GAP * scale;
    top = Math.max(EDGE, Math.min(top, window.innerHeight - height - EDGE));
    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
    popup.style.transformOrigin = 'top left';
    popup.style.transform = 'scale(' + scale + ')';
  }

  function show(btn){
    current = btn;
    if (popup.parentElement !== document.body) document.body.appendChild(popup);
    popup.classList.remove('is-hidden');
    popup.setAttribute('aria-hidden', 'false');
    place();
  }

  function hide(){
    popup.classList.add('is-hidden');
    popup.setAttribute('aria-hidden', 'true');
    current = null;
  }

  document.querySelectorAll('.ref-trigger').forEach(function(btn){
    btn.addEventListener('mouseenter', function(){ show(btn); });
    btn.addEventListener('mouseleave', hide);
    btn.addEventListener('focus', function(){ show(btn); });
    btn.addEventListener('blur', hide);
  });

  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') hide();
  });
  window.addEventListener('scroll', place, true);
  window.addEventListener('resize', place);
})();
