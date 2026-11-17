/* Novak|GS light/dark theme. Light is the default; the visitor's choice is remembered. */
(function () {
  var root = document.documentElement, saved = null;
  try { saved = new URLSearchParams(location.search).get('theme') || localStorage.getItem('ngs-theme'); } catch (e) {}
  root.setAttribute('data-theme', saved === 'dark' ? 'dark' : 'light');

  var ICONS =
    '<svg class="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/></svg>' +
    '<svg class="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.8 6.8 0 0 0 10.7 10.7z"/></svg>';

  function isLight() { return root.getAttribute('data-theme') !== 'dark'; }

  function swapLogos() {
    var light = isLight();
    var imgs = document.querySelectorAll('img[src*="/logo-dark-v2."], img[src*="/logo-light-v2."]');
    for (var i = 0; i < imgs.length; i++) {
      var im = imgs[i];
      if (im.classList.contains('logo-dark') || im.classList.contains('logo-light') || im.hasAttribute('data-keep-logo')) continue;
      im.src = light ? '/logo-light-v2.png' : '/logo-dark-v2.png';
    }
    var srcs = document.querySelectorAll('source[srcset*="/logo-dark-v2."], source[srcset*="/logo-light-v2."]');
    for (var j = 0; j < srcs.length; j++) {
      if (srcs[j].hasAttribute('data-keep-logo')) continue;
      srcs[j].srcset = light ? '/logo-light-v2.webp' : '/logo-dark-v2.webp';
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', light ? '#f3f4f6' : '#0a0d12');
  }

  function init() {
    var b = document.querySelector('.theme-toggle');
    if (!b) {
      b = document.createElement('button');
      b.type = 'button';
      b.className = 'theme-toggle';
      b.innerHTML = ICONS;
      var slot = document.querySelector('[data-theme-slot]');
      if (slot) slot.appendChild(b);
      else { b.classList.add('floating'); document.body.classList.add('has-floating-toggle'); document.body.appendChild(b); }
    }
    function sync() {
      var light = isLight();
      b.setAttribute('aria-label', light ? 'Light mode on. Switch to dark mode' : 'Dark mode on. Switch to light mode');
      b.setAttribute('title', light ? 'Switch to dark mode' : 'Switch to light mode');
      swapLogos();
    }
    sync();
    b.addEventListener('click', function () {
      root.setAttribute('data-theme', isLight() ? 'dark' : 'light');
      try { localStorage.setItem('ngs-theme', root.getAttribute('data-theme')); } catch (e) {}
      sync();
    });
  }
  function bandHeight() {
    var band = document.querySelector('.band');
    if (!band) return;
    var setH = function () { root.style.setProperty('--band-h', Math.round(band.getBoundingClientRect().height) + 'px'); };
    setH();
    if (window.ResizeObserver) new ResizeObserver(setH).observe(band); else window.addEventListener('resize', setH);
  }
  /* Clicking into a page (menu, logo, any link) always lands at the top.
     Links with a #section still jump to that section, and Back/Forward/Reload
     keep the browser's normal scroll memory. */
  function topOnArrival() {
    if (location.hash) return;
    var nav = window.performance && performance.getEntriesByType ? performance.getEntriesByType('navigation')[0] : null;
    if (nav && nav.type !== 'navigate') return;
    var userMoved = false;
    var mark = function () { userMoved = true; };
    ['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(function (ev) {
      window.addEventListener(ev, mark, { once: true, passive: true });
    });
    var toTop = function () { if (!userMoved && !location.hash) window.scrollTo(0, 0); };
    toTop();
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', toTop);
    window.addEventListener('load', toTop);
  }
  topOnArrival();

  function start() { init(); bandHeight(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
