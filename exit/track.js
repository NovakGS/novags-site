/* Novak|GS activity log for the EXIT package pages.
   Sends page views, clicks, downloads, call/text/email taps, map changes, FAQ opens, and time on
   page to /api/track (first-party, no cookies). ?r=<code> on the link tags the visitor on this
   browser (the code stands in for a name; functions/api/track.js turns it back into the name);
   browsers marked internal with ?internal=1 send nothing. Same script as the Hamele pages. */
(function () {
  'use strict';
  if (!navigator.sendBeacon || !window.URLSearchParams) return;
  if (/(?:^|;\s*)novak_internal=1(?:;|$)/.test(document.cookie)) return;

  var q = new URLSearchParams(location.search);
  var r = q.get('r');
  if (r !== null) {
    try { if (/^[a-z0-9-]{1,20}$/i.test(r)) localStorage.setItem('ngs_r', r.toLowerCase()); } catch (e) {}
    q.delete('r');
    var rest = q.toString();
    try { history.replaceState(history.state, '', location.pathname + (rest ? '?' + rest : '') + location.hash); } catch (e) {}
  }
  var tag = '';
  try { tag = localStorage.getItem('ngs_r') || ''; } catch (e) {}
  var visit = '';
  try {
    visit = sessionStorage.getItem('ngs_v') || '';
    if (!visit) { visit = Math.random().toString(36).slice(2, 8); sessionStorage.setItem('ngs_v', visit); }
  } catch (e) {}
  var touch = navigator.maxTouchPoints > 1 ? 1 : 0;

  var last = { key: '', at: 0 };
  function send(kind, label, extra) {
    label = clean(label).slice(0, 200);
    var key = kind + '|' + label, now = Date.now();
    if (kind !== 'time' && kind !== 'view' && key === last.key && now - last.at < 2000) return;
    last = { key: key, at: now };
    var body = { k: kind, p: location.pathname, l: label, r: tag, v: visit, t: touch };
    if (extra) for (var x in extra) body[x] = extra[x];
    try { navigator.sendBeacon('/api/track', new Blob([JSON.stringify(body)], { type: 'text/plain' })); } catch (e) {}
  }
  function clean(t) { return String(t || '').replace(/\s+/g, ' ').trim(); }
  function strip(t) { return clean(t).replace(/\s*[↑↗→↓]+$/, ''); }
  function heading(el) {
    var box = el.closest('article, section');
    var h = box && box.querySelector('h3, h2');
    return h ? strip(h.textContent) : '';
  }
  function textOf(el) {
    var out = [];
    (function walk(n) {
      for (var c = n.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) out.push(c.nodeValue);
        else if (c.nodeType === 1 && !/^(script|style|svg)$/i.test(c.tagName)) { out.push(' '); walk(c); out.push(' '); }
      }
    })(el);
    return out.join('');
  }
  function labelFor(el) {
    var strong = el.querySelector('strong');
    var img = el.querySelector('img[alt]');
    return strip(el.getAttribute('aria-label') || (strong && strong.textContent) || textOf(el) ||
      (img && img.getAttribute('alt')) || el.getAttribute('title') || '');
  }

  // Page view, with the site the visitor came from when it is another site.
  function view() {
    var from = '';
    try {
      if (document.referrer) {
        var h = new URL(document.referrer).hostname;
        if (h && h !== location.hostname) from = 'from ' + h.replace(/^www\./, '');
      }
    } catch (e) {}
    send('view', from);
  }
  view();
  window.addEventListener('pageshow', function (e) { if (e.persisted) view(); });

  var SKIP = /^(zoom in|zoom out|menu|switch theme)$/i;
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('a[href], button') : null;
    if (!el) return;
    if (el.tagName === 'BUTTON') {
      var b = labelFor(el);
      if (!b || SKIP.test(b) || el.classList.contains('theme-toggle') || el.classList.contains('uch-mbtn')) return;
      if (el.classList.contains('pre')) return send('map', b + ' (quick view)');
      if (el.classList.contains('show')) return send('map', (heading(el) || b) + ' (' + b + ')');
      if (el.id === 'zloc') return send('map', 'Show my location');
      return send('click', b);
    }
    var href = el.getAttribute('href') || '';
    var u;
    try { u = new URL(el.href, location.href); } catch (err) { return; }
    var label = labelFor(el);
    if (/^tel:/i.test(href)) return send('call', /\d/.test(label) ? label : (label ? label + ' ' : '') + href.slice(4));
    if (/^sms:/i.test(href)) return send('text', label);
    if (/^mailto:/i.test(href)) return send('email', label);
    var isFile = el.hasAttribute('download') || /\.(pdf|zip|kmz|kml|gpx|jpe?g|png|tiff?)$/i.test(u.pathname) ||
      (u.hostname === 'drive.google.com' && u.pathname === '/uc');
    if (isFile) {
      var dn = el.getAttribute('download');
      if (dn && !el.querySelector('strong')) label = dn;
      return send('download', label);
    }
    if (u.hostname === 'drive.google.com') return send('folder', label);
    if (u.origin === location.origin) {
      if (u.pathname === location.pathname && u.hash) return send('click', label + ' (jump on page)');
      return send('click', label);
    }
    var host = u.hostname.replace(/^www\./, '');
    return send('out', label && label.toLowerCase().indexOf(host) < 0 ? label + ' (' + host + ')' : (label || host));
  }, true);

  // Map layer checkboxes on the Country Property page.
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (!el || el.type !== 'checkbox' || !el.hasAttribute('data-k')) return;
    var row = el.closest('label');
    var name = row ? strip((row.querySelector('span') || row).textContent) : el.getAttribute('data-k');
    send('map', (el.checked ? 'Turned on ' : 'Turned off ') + name);
  }, true);

  // FAQ questions (details/summary) when opened.
  document.addEventListener('toggle', function (e) {
    var d = e.target;
    if (!d || d.tagName !== 'DETAILS' || !d.open) return;
    var s = d.querySelector('summary');
    send('faq', s ? s.textContent : '');
  }, true);

  // Time on page, counted only while the page is on screen.
  var shownAt = document.visibilityState === 'visible' ? Date.now() : 0, total = 0, sent = 0;
  function hidden() {
    if (shownAt) { total += Date.now() - shownAt; shownAt = 0; }
    var secs = Math.round(total / 1000);
    if (secs >= 10 && (sent === 0 || secs - sent >= 30)) { send('time', '', { s: secs }); sent = secs; }
  }
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') hidden();
    else shownAt = Date.now();
  });
  window.addEventListener('pagehide', hidden);
})();
