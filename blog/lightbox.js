// Tap-to-enlarge for photos in long-form posts: any <figure> image wrapped in a <button>.
(function(){
  var lb=document.getElementById('lb'); if(!lb) return;
  var im=document.getElementById('lbimg'), cap=document.getElementById('lbcap'), last=null;
  function open(btn){ var i=btn.querySelector('img'), fc=btn.closest('figure').querySelector('figcaption'); last=btn; im.src=i.currentSrc||i.src; im.alt=i.alt; cap.textContent=fc?fc.textContent:''; lb.hidden=false; document.body.style.overflow='hidden'; document.getElementById('lbx').focus(); }
  function close(){ lb.hidden=true; im.removeAttribute('src'); document.body.style.overflow=''; if(last) last.focus(); }
  document.querySelectorAll('.post-flow figure button').forEach(function(b){ b.addEventListener('click',function(){open(b);}); });
  lb.addEventListener('click',close);
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'&&!lb.hidden) close(); });
})();
