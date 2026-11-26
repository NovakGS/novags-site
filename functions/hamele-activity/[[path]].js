// Cloudflare Pages Function: /hamele-activity/
// Gregg's private view of the Hamele activity log (events stored by /api/track in D1, ACTIVITY_DB).
//
// Access: a password Gregg chooses himself. The first time the page is opened, and only from a
// browser marked internal with ?internal=1, it asks him to choose one; after that it asks for it.
// Only a salted PBKDF2 hash is stored (settings table, key "pw"). The sign-in cookie is an HMAC
// of that hash, so changing the password signs every device out. To reset a forgotten password,
// delete the "pw" row from the settings table.

const COOKIE = 'ngs_act';
const BASE = '/hamele-activity';
const MAX_AGE = 60 * 60 * 24 * 365;
const LIVE_HOSTS = ['hamele.novags-site.pages.dev', 'novakgs.com'];
const ITER = 100000;
const enc = new TextEncoder();

const b64e = (u8) => btoa(String.fromCharCode(...u8)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const b64d = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const isInternal = (request) => /(?:^|;\s*)novak_internal=1(?:;|$)/.test(request.headers.get('cookie') || '');

function readCookie(request, name) {
  const m = (request.headers.get('cookie') || '').match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return m ? m[1] : '';
}

function safeEqual(a, b) {
  a = String(a); b = String(b);
  if (a.length !== b.length) return false;
  let x = 0;
  for (let i = 0; i < a.length; i++) x |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return x === 0;
}

async function hashPassword(password, saltText) {
  const salt = saltText ? b64d(saltText) : crypto.getRandomValues(new Uint8Array(16));
  const key = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: ITER }, key, 256);
  return `${b64e(salt)}:${b64e(new Uint8Array(bits))}`;
}

async function sessionToken(stored) {
  const key = await crypto.subtle.importKey('raw', enc.encode(stored), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return b64e(new Uint8Array(await crypto.subtle.sign('HMAC', key, enc.encode('hamele-activity-session'))));
}

// Creates the tables on first use, so a fresh database needs no setup step.
const SCHEMA = [
  "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, host TEXT NOT NULL, who TEXT NOT NULL DEFAULT '', page TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT '', item TEXT NOT NULL DEFAULT '', secs INTEGER, device TEXT NOT NULL DEFAULT '', place TEXT NOT NULL DEFAULT '', visit TEXT NOT NULL DEFAULT '')",
  'CREATE INDEX IF NOT EXISTS events_ts ON events(ts)',
  'CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT NOT NULL)',
];
let schemaReady = null;
function ensureSchema(db) {
  if (!schemaReady) {
    schemaReady = db.batch(SCHEMA.map((sql) => db.prepare(sql))).catch((err) => { schemaReady = null; throw err; });
  }
  return schemaReady;
}

async function getSetting(db, k) {
  const row = await db.prepare('SELECT v FROM settings WHERE k = ?').bind(k).first();
  return row ? row.v : null;
}
const setSetting = (db, k, v) =>
  db.prepare('INSERT INTO settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v').bind(k, v).run();

// ---------- Page shell ----------
const CSS = `
:root{--bg:#0a0d12;--panel:#131820;--edge:#232b36;--ink:#eef1f3;--muted:#aab4be;--faint:#7d8792;--or:#e8711a}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 Roboto,"Segoe UI",system-ui,-apple-system,Arial,sans-serif}
main{max-width:760px;margin:0 auto;padding:22px 16px 60px}
h1{font-size:22px;margin:0 0 4px}h1 b{color:var(--or)}
.sub{color:var(--muted);margin:0 0 16px;font-size:14px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}
.chips a{color:var(--ink);text-decoration:none;border:1px solid var(--edge);border-radius:999px;padding:6px 12px;font-size:14px;background:var(--panel)}
.chips a.on{border-color:var(--or);color:#fff;background:#3a2412}
.sum{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 18px}
.sum div{background:var(--panel);border:1px solid var(--edge);border-radius:10px;padding:10px 12px}
.sum b{display:block;font-size:20px}.sum span{color:var(--muted);font-size:12.5px}
.visit{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:12px 14px;margin:0 0 12px}
.visit h2{font-size:16px;margin:0}.visit h2 .who{color:var(--or)}
.meta{color:var(--muted);font-size:13px;margin:2px 0 8px}
ol{list-style:none;margin:0;padding:0;border-top:1px solid var(--edge)}
li{display:grid;grid-template-columns:72px 1fr;gap:8px;padding:6px 0;border-bottom:1px solid var(--edge);font-size:14px}
li:last-child{border-bottom:0}li time{color:var(--faint);font-variant-numeric:tabular-nums}
li .pg{color:var(--faint);font-size:12.5px}li.dl b{color:var(--or)}
.empty{color:var(--muted);background:var(--panel);border:1px dashed var(--edge);border-radius:12px;padding:18px}
.foot{color:var(--faint);font-size:12.5px;margin-top:20px}
form.box{max-width:380px;margin:12vh auto 0;background:var(--panel);border:1px solid var(--edge);border-radius:14px;padding:22px}
form.box h1{font-size:20px}label{display:block;font-size:13px;color:var(--muted);margin:12px 0 4px}
input{width:100%;font:inherit;color:var(--ink);background:#0d1117;border:1px solid var(--edge);border-radius:8px;padding:10px}
button{margin-top:16px;width:100%;font:inherit;font-weight:600;color:#fff;background:var(--or);border:0;border-radius:8px;padding:11px;cursor:pointer}
.err{color:#ff8a80;font-size:14px;margin:10px 0 0}.top{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.top a{color:var(--muted);font-size:13px}`;

function page(title, body, status = 200, extraHeaders = {}) {
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>${esc(title)}</title><style>${CSS}</style></head><body>${body}</body></html>`;
  return new Response(html, {
    status,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'private, no-store', 'x-robots-tag': 'noindex, nofollow', 'referrer-policy': 'no-referrer', ...extraHeaders },
  });
}

function formPage(kind, error, status = 200) {
  const setup = kind === 'setup';
  const body = `<form class="box" method="post" action="${BASE}/">
<h1>Hamele <b style="color:var(--or)">Activity</b></h1>
<p class="sub">${setup ? 'Choose a password for this page. You’ll use it on each phone or computer you check it from.' : 'Enter your password to see who opened the Hamele pages.'}</p>
<input type="hidden" name="action" value="${setup ? 'setup' : 'login'}">
<label for="pw">Password</label><input id="pw" name="password" type="password" autocomplete="${setup ? 'new-password' : 'current-password'}" required minlength="${setup ? 8 : 1}" autofocus>
${setup ? '<label for="pw2">Password again</label><input id="pw2" name="password2" type="password" autocomplete="new-password" required minlength="8">' : ''}
${error ? `<p class="err" role="alert">${esc(error)}</p>` : ''}
<button type="submit">${setup ? 'Save Password' : 'View Activity'}</button></form>`;
  return page('Hamele Activity', body, status);
}

// ---------- Activity view ----------
const fmt = (opts) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', ...opts });
const fDay = fmt({ weekday: 'short', month: 'short', day: 'numeric' });
const fTime = fmt({ hour: 'numeric', minute: '2-digit' });
const clean = (s) => s.replace(/ /g, ' ');
const day = (ts) => clean(fDay.format(new Date(ts)));
const time = (ts) => clean(fTime.format(new Date(ts)));

function duration(s) {
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60), r = s % 60;
  return r ? `${m} min ${r} s` : `${m} min`;
}

function describe(e) {
  const it = esc(e.item);
  switch (e.kind) {
    case 'view': return `Opened <b>${esc(e.page)}</b>${it ? ` <span class="pg">${it}</span>` : ''}`;
    case 'time': return `Spent <b>${duration(e.secs || 0)}</b> on ${esc(e.page)}`;
    case 'download': return `Downloaded <b>${it}</b>`;
    case 'folder': return `Opened Drive folder <b>${it}</b>`;
    case 'call': return `Tapped call <b>${it}</b>`;
    case 'text': return `Tapped text <b>${it}</b>`;
    case 'email': return `Tapped email <b>${it}</b>`;
    case 'out': return `Opened outside link <b>${it}</b>`;
    case 'faq': return `Opened question <b>${it}</b>`;
    case 'map': return `Changed map: <b>${it}</b>`;
    default: return `Clicked <b>${it}</b>`;
  }
}

async function activity(request, env, url) {
  const db = env.ACTIVITY_DB;
  const onLive = LIVE_HOSTS.includes(url.host);
  const showTest = !onLive || url.searchParams.get('test') === '1';
  const who = (url.searchParams.get('who') || '').toLowerCase();
  const since = Date.now() - 90 * 86400000;

  const hostSql = showTest ? '' : ` AND host IN (${LIVE_HOSTS.map(() => '?').join(',')})`;
  const hostArgs = showTest ? [] : LIVE_HOSTS;
  const tags = (await db.prepare(`SELECT DISTINCT who FROM events WHERE ts > ? AND who <> ''${hostSql}`).bind(since, ...hostArgs).all()).results.map((r) => r.who);

  let whoSql = '', whoArgs = [];
  if (who === 'none') { whoSql = " AND who = ''"; }
  else if (who) { whoSql = ' AND lower(who) = ?'; whoArgs = [who]; }
  const rows = (await db.prepare(`SELECT ts, host, who, page, kind, item, secs, device, place, visit FROM events WHERE ts > ?${hostSql}${whoSql} ORDER BY ts DESC LIMIT 600`)
    .bind(since, ...hostArgs, ...whoArgs).all()).results;

  // Group into visits (one browser tab session), newest visit first.
  const visits = new Map();
  for (const r of rows.slice().reverse()) {
    const key = `${r.host}|${r.visit || r.ts}`;
    if (!visits.has(key)) visits.set(key, { who: r.who, device: r.device, place: r.place, host: r.host, events: [], last: 0, lastTime: {} });
    const v = visits.get(key);
    if (r.who && !v.who) v.who = r.who;
    // Keep only the latest running "time on page" for each page view.
    if (r.kind === 'view') v.lastTime[r.page] = null;
    if (r.kind === 'time') {
      const prev = v.lastTime[r.page];
      if (prev) prev.hide = true;
      v.lastTime[r.page] = r;
    }
    v.events.push(r);
    v.last = r.ts;
  }
  const list = [...visits.values()].sort((a, b) => b.last - a.last);

  const views = rows.filter((r) => r.kind === 'view').length;
  const downloads = rows.filter((r) => r.kind === 'download').length;
  const q = (params) => {
    const p = new URLSearchParams();
    if (params.who) p.set('who', params.who);
    if (onLive && params.test) p.set('test', '1');
    const s = p.toString();
    return `${BASE}/${s ? `?${s}` : ''}`;
  };
  const chips = [`<a href="${q({ test: showTest && onLive })}"${!who ? ' class="on"' : ''}>Everyone</a>`]
    .concat(tags.map((t) => `<a href="${q({ who: t.toLowerCase(), test: showTest && onLive })}"${who === t.toLowerCase() ? ' class="on"' : ''}>${esc(t)}</a>`))
    .concat([`<a href="${q({ who: 'none', test: showTest && onLive })}"${who === 'none' ? ' class="on"' : ''}>Untagged</a>`]);
  if (onLive) chips.push(`<a href="${q({ who, test: !showTest })}"${showTest ? ' class="on"' : ''}>Test Builds</a>`);

  const visitHtml = list.map((v) => {
    const first = v.events[0].ts;
    const range = time(first) === time(v.last) ? time(first) : `${time(first)} – ${time(v.last)}`;
    const meta = [v.device, v.place, showTest && !LIVE_HOSTS.includes(v.host) ? `test build (${v.host.split('.')[0]})` : ''].filter(Boolean).map(esc).join(' · ');
    const items = v.events.filter((e) => !e.hide).map((e) =>
      `<li${e.kind === 'download' ? ' class="dl"' : ''}><time>${time(e.ts)}</time><span>${describe(e)}${e.kind !== 'view' && e.kind !== 'time' && e.page ? ` <span class="pg">on ${esc(e.page)}</span>` : ''}</span></li>`).join('');
    return `<section class="visit"><h2><span class="who">${esc(v.who || 'Untagged visitor')}</span> · ${esc(day(first))}, ${esc(range)}</h2>
<p class="meta">${meta}</p><ol>${items}</ol></section>`;
  }).join('');

  const lastLine = rows.length ? `Last activity ${esc(day(rows[0].ts))} at ${esc(time(rows[0].ts))}, Central time.` : 'Nothing logged yet.';
  const body = `<main><div class="top"><h1>Hamele <b>Activity</b></h1><a href="${esc(url.pathname + url.search)}">Refresh</a></div>
<p class="sub">${lastLine}</p>
<nav class="chips">${chips.join('')}</nav>
<div class="sum"><div><b>${list.length}</b><span>Visits</span></div><div><b>${views}</b><span>Page Views</span></div><div><b>${downloads}</b><span>Downloads</span></div></div>
${visitHtml || '<p class="empty">No visits to show yet. Activity appears here a few seconds after someone opens a Hamele page.</p>'}
<p class="foot">Shows the last 90 days, newest visit first. A visit is one browser tab session. Places are approximate, from the visitor’s internet connection. Browsers you marked with your don’t-count link are never logged.</p></main>`;
  return page('Hamele Activity', body);
}

// ---------- Handler ----------
export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  if (url.pathname !== BASE && url.pathname !== `${BASE}/`) return new Response('Not found.', { status: 404 });
  if (url.pathname === BASE) return Response.redirect(`${url.origin}${BASE}/${url.search}`, 301);
  const db = env.ACTIVITY_DB;
  if (!db) return page('Hamele Activity', '<main><p class="empty">The activity database isn’t connected to this build yet.</p></main>', 503);

  try { await ensureSchema(db); } catch { return page('Hamele Activity', '<main><p class="empty">The activity database didn’t answer. Try again in a minute.</p></main>', 503); }
  const stored = await getSetting(db, 'pw');

  if (request.method === 'POST') {
    let form;
    try { form = await request.formData(); } catch { return formPage(stored ? 'login' : 'setup', 'Please try again.', 400); }
    const action = String(form.get('action') || '');
    const password = String(form.get('password') || '');

    if (!stored) {
      if (action !== 'setup' || !isInternal(request)) return page('Hamele Activity', '<main><p class="empty">This page isn’t set up yet.</p></main>', 403);
      if (password.length < 8) return formPage('setup', 'Use at least 8 characters.', 400);
      if (password !== String(form.get('password2') || '')) return formPage('setup', 'The two passwords didn’t match.', 400);
      const hashed = await hashPassword(password);
      // Only the first setup wins.
      const res = await db.prepare('INSERT OR IGNORE INTO settings (k, v) VALUES (?, ?)').bind('pw', hashed).run();
      if (!res.meta || !res.meta.changes) return formPage('login', 'A password was already set. Enter it here.', 409);
      return new Response(null, { status: 303, headers: { Location: `${BASE}/`, 'Set-Cookie': `${COOKIE}=${await sessionToken(hashed)}; Path=${BASE}; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax`, 'Cache-Control': 'no-store' } });
    }

    // Login, with a simple brake on repeated wrong passwords.
    const now = Date.now();
    let fails = [];
    try { fails = JSON.parse((await getSetting(db, 'fails')) || '[]').filter((t) => now - t < 15 * 60000); } catch { fails = []; }
    if (fails.length >= 10) return formPage('login', 'Too many tries. Wait 15 minutes and try again.', 429);
    const [salt] = stored.split(':');
    if (!safeEqual(await hashPassword(password, salt), stored)) {
      fails.push(now);
      await setSetting(db, 'fails', JSON.stringify(fails));
      return formPage('login', 'That password didn’t work.', 401);
    }
    return new Response(null, { status: 303, headers: { Location: `${BASE}/`, 'Set-Cookie': `${COOKIE}=${await sessionToken(stored)}; Path=${BASE}; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax`, 'Cache-Control': 'no-store' } });
  }

  if (request.method !== 'GET' && request.method !== 'HEAD') return new Response(null, { status: 405 });
  if (!stored) {
    if (!isInternal(request)) return page('Hamele Activity', '<main><p class="empty">This page isn’t set up yet. Open your don’t-count link on this device first, then come back here.</p></main>', 403);
    return formPage('setup');
  }
  if (!safeEqual(readCookie(request, COOKIE), await sessionToken(stored))) return formPage('login', '', 401);
  return activity(request, env, url);
}
