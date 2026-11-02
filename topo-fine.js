/* Novak GS - fine, slowly drifting contour background.
 * A quieter take on topo.js: tighter terrain, thin low-contrast lines, drawn at the
 * screen's pixel density so it stays crisp at any size. Static for reduced-motion users.
 * Usage: <div data-topo-fine aria-hidden="true"></div> anywhere in <body>.
 */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var perm = new Uint8Array(512);
  (function seed() {
    var p = [], i, j, t, s = 4271;
    for (i = 0; i < 256; i++) p[i] = i;
    for (i = 255; i > 0; i--) { s = (s * 16807) % 2147483647; j = s % (i + 1); t = p[i]; p[i] = p[j]; p[j] = t; }
    for (i = 0; i < 512; i++) perm[i] = p[i & 255];
  })();
  function fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function h(x, y, z) { return perm[(perm[(perm[x & 255] + y) & 255] + z) & 255] / 255; }
  function noise(x, y, z) {
    var X = Math.floor(x), Y = Math.floor(y), Z = Math.floor(z);
    var u = fade(x - X), v = fade(y - Y), w = fade(z - Z);
    return lerp(
      lerp(lerp(h(X, Y, Z), h(X + 1, Y, Z), u), lerp(h(X, Y + 1, Z), h(X + 1, Y + 1, Z), u), v),
      lerp(lerp(h(X, Y, Z + 1), h(X + 1, Y, Z + 1), u), lerp(h(X, Y + 1, Z + 1), h(X + 1, Y + 1, Z + 1), u), v),
      w);
  }
  function field(x, y, t) {
    return noise(x, y, t) * 0.62 + noise(x * 2.2 + 31, y * 2.2 + 7, t * 1.3) * 0.26 + noise(x * 4.7 + 3, y * 4.7 + 19, t * 1.6) * 0.12;
  }

  var LEVELS = 21;

  function Topo(canvas) {
    var ctx = canvas.getContext('2d'), W, H, dpr, cell, cols, rows, grid;
    function size() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth; H = window.innerHeight;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cell = W < 640 ? 6 : 8;
      cols = Math.ceil(W / cell) + 1; rows = Math.ceil(H / cell) + 1;
      grid = new Float32Array(cols * rows);
    }
    function seg(p, q) { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); }
    function trace(iso) {
      ctx.beginPath();
      for (var j = 0; j < rows - 1; j++) for (var i = 0; i < cols - 1; i++) {
        var a = grid[j * cols + i], b = grid[j * cols + i + 1], c = grid[(j + 1) * cols + i + 1], d = grid[(j + 1) * cols + i];
        var idx = (a > iso ? 8 : 0) | (b > iso ? 4 : 0) | (c > iso ? 2 : 0) | (d > iso ? 1 : 0);
        if (idx === 0 || idx === 15) continue;
        var x = i * cell, y = j * cell;
        var top = [x + cell * (iso - a) / (b - a), y], right = [x + cell, y + cell * (iso - b) / (c - b)],
            bottom = [x + cell * (iso - d) / (c - d), y + cell], left = [x, y + cell * (iso - a) / (d - a)];
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
    function draw(t) {
      var scale = 1 / (W < 640 ? 150 : 210), i, j, k;
      for (j = 0; j < rows; j++) for (i = 0; i < cols; i++) grid[j * cols + i] = field(i * cell * scale, j * cell * scale, t);
      ctx.fillStyle = '#0a0d12'; ctx.fillRect(0, 0, W, H);
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      for (k = 1; k < LEVELS; k++) {
        trace(0.2 + (k / LEVELS) * 0.6);
        if (k === 11) { ctx.strokeStyle = 'rgba(232,113,26,.32)'; ctx.lineWidth = 1; }
        else if (k % 5 === 0) { ctx.strokeStyle = 'rgba(70,119,160,.28)'; ctx.lineWidth = 0.8; }
        else { ctx.strokeStyle = 'rgba(170,179,188,.12)'; ctx.lineWidth = 0.6; }
        ctx.stroke();
      }
    }
    this.size = size; this.draw = draw;
    size();
  }

  function boot() {
    var host = document.querySelector('[data-topo-fine]');
    if (!host) return;
    var canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;display:block';
    host.appendChild(canvas);
    if (!canvas.getContext || !canvas.getContext('2d')) return;
    var topo = new Topo(canvas), now = 0;

    var lastW = window.innerWidth, lastH = window.innerHeight, rt;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(function () {
        // phones fire resize as the address bar slides; ignore small height changes
        if (Math.abs(window.innerWidth - lastW) > 2 || Math.abs(window.innerHeight - lastH) > 120) {
          lastW = window.innerWidth; lastH = window.innerHeight; topo.size(); topo.draw(now);
        }
      }, 150);
    });

    if (reduce) { topo.draw(0); return; }
    var start = performance.now(), last = 0, running = true;
    function frame(ts) {
      if (!running) return;
      if (ts - last > 66) { // ~15 fps is plenty for a slow drift
        last = ts; now = (ts - start) / 1000 * 0.03; topo.draw(now);
      }
      requestAnimationFrame(frame);
    }
    document.addEventListener('visibilitychange', function () {
      running = !document.hidden;
      if (running) requestAnimationFrame(frame);
    });
    topo.draw(0);
    requestAnimationFrame(frame);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
