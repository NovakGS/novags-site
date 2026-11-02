/* Novak GS - live contour background.
 * Add data-topo="page" to <body> for a full-screen fixed background,
 * or data-topo="band" to any element (e.g. a header) to fill just that element.
 * Content inside a band is lifted above the canvas automatically.
 */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // --- 3D value noise (x, y, time) ---
  var perm = new Uint8Array(512);
  (function seed() {
    var p = [], i, j, t, s = 7919;
    for (i = 0; i < 256; i++) p[i] = i;
    for (i = 255; i > 0; i--) {
      s = (s * 16807) % 2147483647;
      j = s % (i + 1); t = p[i]; p[i] = p[j]; p[j] = t;
    }
    for (i = 0; i < 512; i++) perm[i] = p[i & 255];
  })();
  function fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function h(x, y, z) { return perm[(perm[(perm[x & 255] + y) & 255] + z) & 255] / 255; }
  function noise(x, y, z) {
    var X = Math.floor(x), Y = Math.floor(y), Z = Math.floor(z);
    var fx = x - X, fy = y - Y, fz = z - Z;
    var u = fade(fx), v = fade(fy), w = fade(fz);
    return lerp(
      lerp(lerp(h(X, Y, Z), h(X + 1, Y, Z), u), lerp(h(X, Y + 1, Z), h(X + 1, Y + 1, Z), u), v),
      lerp(lerp(h(X, Y, Z + 1), h(X + 1, Y, Z + 1), u), lerp(h(X, Y + 1, Z + 1), h(X + 1, Y + 1, Z + 1), u), v),
      w);
  }
  function field(x, y, t) {
    return noise(x, y, t) * 0.65 + noise(x * 2.1 + 17, y * 2.1 + 9, t * 1.3) * 0.35;
  }

  // Two looks: the default bold style, and data-topo-style="fine" for a denser, quieter map.
  var STYLES = {
    bold: { levels: 14, accent: 7, scale: 380, scaleSm: 260, cell: 14, cellSm: 12, index: 3,
            line: 'rgba(170,179,188,.22)', lineW: 1, idx: 'rgba(70,119,160,.55)', idxW: 1.2, glow: true },
    fine: { levels: 34, accent: 17, scale: 170, scaleSm: 130, cell: 9, cellSm: 8, index: 5,
            line: 'rgba(170,179,188,.085)', lineW: 0.8, idx: 'rgba(70,119,160,.26)', idxW: 1, glow: false }
  };

  function Topo(host, mode) {
    var S = STYLES[host.getAttribute('data-topo-style')] || STYLES.bold;
    var LEVELS = S.levels, ACCENT = S.accent;
    var canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    canvas.className = 'topo-canvas';
    var cs = canvas.style;
    cs.position = mode === 'page' ? 'fixed' : 'absolute';
    cs.left = cs.top = '0'; cs.width = '100%'; cs.height = '100%';
    cs.zIndex = '0'; cs.pointerEvents = 'none'; cs.display = 'block';
    if (mode === 'band') {
      if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
      host.style.overflow = 'hidden';
      host.style.isolation = 'isolate';
      for (var c = host.firstElementChild; c; c = c.nextElementSibling) {
        if (getComputedStyle(c).position === 'static') c.style.position = 'relative';
        if (!c.style.zIndex) c.style.zIndex = '1';
      }
    }
    host.insertBefore(canvas, host.firstChild);
    var ctx = canvas.getContext && canvas.getContext('2d');
    if (!ctx) { canvas.remove(); return; }

    var W, H, dpr, cell, cols, rows, grid;
    function size() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (mode === 'page') { W = window.innerWidth; H = window.innerHeight; }
      else { var r = host.getBoundingClientRect(); W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height)); }
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cell = W < 640 ? S.cellSm : S.cell;
      cols = Math.ceil(W / cell) + 1; rows = Math.ceil(H / cell) + 1;
      grid = new Float32Array(cols * rows);
    }
    function seg(p, q) { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); }
    function trace(iso) {
      ctx.beginPath();
      for (var j = 0; j < rows - 1; j++) {
        for (var i = 0; i < cols - 1; i++) {
          var a = grid[j * cols + i], b = grid[j * cols + i + 1],
              c = grid[(j + 1) * cols + i + 1], d = grid[(j + 1) * cols + i];
          var idx = (a > iso ? 8 : 0) | (b > iso ? 4 : 0) | (c > iso ? 2 : 0) | (d > iso ? 1 : 0);
          if (idx === 0 || idx === 15) continue;
          var x = i * cell, y = j * cell;
          var top = [x + cell * (iso - a) / (b - a), y],
              right = [x + cell, y + cell * (iso - b) / (c - b)],
              bottom = [x + cell * (iso - d) / (c - d), y + cell],
              left = [x, y + cell * (iso - a) / (d - a)];
          switch (idx) {
            case 1: case 14: seg(left, bottom); break;
            case 2: case 13: seg(bottom, right); break;
            case 3: case 12: seg(left, right); break;
            case 4: case 11: seg(top, right); break;
            case 6: case 9: seg(top, bottom); break;
            case 7: case 8: seg(left, top); break;
            case 5: seg(left, top); seg(bottom, right); break;
            case 10: seg(top, right); seg(left, bottom); break;
          }
        }
      }
    }
    function draw(t) {
      var scale = 1 / (W < 640 ? S.scaleSm : S.scale), i, j, k;
      for (j = 0; j < rows; j++)
        for (i = 0; i < cols; i++)
          grid[j * cols + i] = field(i * cell * scale, j * cell * scale, t);
      ctx.fillStyle = '#0a0d12';
      ctx.fillRect(0, 0, W, H);
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      for (k = 1; k < LEVELS; k++) {
        var iso = 0.18 + (k / LEVELS) * 0.64;
        trace(iso);
        if (k === ACCENT) {
          if (S.glow) {
            // the orange line: a soft glow under a bright, crisp stroke
            ctx.strokeStyle = 'rgba(255,138,40,.16)'; ctx.lineWidth = 8; ctx.stroke();
            ctx.strokeStyle = 'rgba(255,138,40,.28)'; ctx.lineWidth = 4; ctx.stroke();
            ctx.strokeStyle = 'rgba(255,150,58,.98)'; ctx.lineWidth = 2; ctx.stroke();
          } else {
            ctx.strokeStyle = 'rgba(255,150,58,.45)'; ctx.lineWidth = 1.1; ctx.stroke();
          }
        } else if (k % S.index === 0) {
          ctx.strokeStyle = S.idx; ctx.lineWidth = S.idxW; ctx.stroke();
        } else {
          ctx.strokeStyle = S.line; ctx.lineWidth = S.lineW; ctx.stroke();
        }
      }
    }
    this.size = size; this.draw = draw;
    size();
    if (mode === 'band' && window.ResizeObserver) new ResizeObserver(function () { size(); if (reduce) draw(0); }).observe(host);
  }

  var all = [];
  function boot() {
    var els = document.querySelectorAll('[data-topo]');
    for (var i = 0; i < els.length; i++) {
      var t = new Topo(els[i], els[i].getAttribute('data-topo') === 'page' ? 'page' : 'band');
      if (t.draw) all.push(t);
    }
    if (!all.length) return;
    window.addEventListener('resize', function () { all.forEach(function (t) { t.size(); if (reduce) t.draw(0); }); });
    if (reduce) { all.forEach(function (t) { t.draw(0); }); return; }
    var start = performance.now(), last = 0, running = true;
    function frame(now) {
      if (!running) return;
      if (now - last > 40) { // ~25 fps is plenty for slow drift
        last = now;
        var tt = (now - start) / 1000 * 0.035;
        all.forEach(function (t) { t.draw(tt); });
      }
      requestAnimationFrame(frame);
    }
    document.addEventListener('visibilitychange', function () {
      running = !document.hidden;
      if (running) requestAnimationFrame(frame);
    });
    requestAnimationFrame(frame);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
