/* Schiedsrichter-Popup — schließen per X, Overlay-Klick und ESC */
(function(){
  'use strict';
  var overlay = document.getElementById('ref-overlay');
  if (!overlay) return;

  function openPopup(){ overlay.classList.remove('is-hidden'); }
  function closePopup(){ overlay.classList.add('is-hidden'); }

  document.querySelectorAll('.ref-trigger').forEach(function(btn){
    btn.addEventListener('click', openPopup);
  });

  var closeBtn = document.getElementById('ref-close-btn');
  if (closeBtn) closeBtn.addEventListener('click', closePopup);

  overlay.addEventListener('click', function(e){
    if (e.target === overlay) closePopup();
  });

  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') closePopup();
  });
})();
