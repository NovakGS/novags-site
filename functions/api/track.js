// Cloudflare Pages Function: /api/track
// First-party activity log for the Hamele package pages (/hamele/...). No cookies are set on
// visitors and no third party is involved: each event is one row in the D1 database bound as
// ACTIVITY_DB (database "novags-hamele-activity", table "events"). Gregg reads it at /hamele-activity/.
//
// POST (sent by /hamele/track.js with navigator.sendBeacon) -> stores one event:
//   page views, clicks, downloads, call/text/email taps, map changes, FAQ opens, and time on page.
// Browsers marked internal with ?internal=1 (cookie novak_internal=1, set by functions/_middleware.js)
// are never logged. ?r=<name> on the page link tags a visitor (handled in /hamele/track.js).
//
// Binding (Pages > Settings > Bindings, Preview environment): ACTIVITY_DB -> novags-hamele-activity.
// Without it, events are quietly dropped.

const MAX_BODY = 2000;
// Link codes that stand in for a name, so the link someone receives doesn't show who it's for.
// The link carries the code (?r=k7m2); the activity log shows the name.
const ALIASES = { k7m2: 'Sarina' };
const BOT_RE = /bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|headless|lighthouse|pingdom|monitor/i;
const KINDS = new Set(['view', 'click', 'download', 'folder', 'call', 'text', 'email', 'out', 'faq', 'map', 'time']);
const PAGES = {
  '/hamele/': 'Presentation',
  '/hamele/map/': 'Hunting & Recreation',
  '/hamele/due-diligence/': 'Buyer Due Diligence',
  '/hamele/stewardship/': 'Stewardship',
  '/hamele/essentials/': 'Essentials',
};

const clip = (v, n) => String(v == null ? '' : v).replace(/[\u0000-\u001f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);
const noContent = () => new Response(null, { status: 204, headers: { 'cache-control': 'no-store' } });

function pageName(path) {
  let p = String(path || '').split('?')[0].split('#')[0].replace(/index\.html$/, '');
  if (!p.endsWith('/')) p += '/';
  return PAGES[p] || '';
}

function device(ua, touch) {
  let d = 'Other device';
  if (/iPad/.test(ua) || (/Macintosh/.test(ua) && touch)) d = 'iPad';
  else if (/iPhone|iPod/.test(ua)) d = 'iPhone';
  else if (/Android/.test(ua)) d = /Mobile/.test(ua) ? 'Android phone' : 'Android tablet';
  else if (/Windows/.test(ua)) d = 'Windows PC';
  else if (/Macintosh/.test(ua)) d = 'Mac';
  else if (/CrOS/.test(ua)) d = 'Chromebook';
  else if (/Linux/.test(ua)) d = 'Linux PC';
  let b = '';
  if (/Outlook/i.test(ua)) b = 'Outlook app';
  else if (/FBAN|FBAV/.test(ua)) b = 'Facebook app';
  else if (/Instagram/.test(ua)) b = 'Instagram app';
  else if (/LinkedInApp/.test(ua)) b = 'LinkedIn app';
  else if (/GSA\//.test(ua)) b = 'Google app';
  else if (/Edg(A|iOS)?\//.test(ua)) b = 'Edge';
  else if (/SamsungBrowser/.test(ua)) b = 'Samsung Internet';
  else if (/OPR\//.test(ua)) b = 'Opera';
  else if (/CriOS|Chrome\//.test(ua)) b = 'Chrome';
  else if (/FxiOS|Firefox\//.test(ua)) b = 'Firefox';
  else if (/Safari\//.test(ua)) b = 'Safari';
  return b ? `${d}, ${b}` : d;
}

function place(cf) {
  if (!cf) return '';
  const city = clip(cf.city, 60);
  const region = cf.country === 'US' ? clip(cf.regionCode, 10) : clip(cf.region || cf.country, 40);
  return [city, region].filter(Boolean).join(', ');
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

export async function onRequestPost({ request, env, waitUntil }) {
  const url = new URL(request.url);
  const origin = request.headers.get('origin');
  if (origin && origin !== 'null') {
    try { if (new URL(origin).host !== url.host) return new Response(null, { status: 403 }); } catch { return new Response(null, { status: 403 }); }
  }
  if (!env.ACTIVITY_DB) return noContent();
  if (/(?:^|;\s*)novak_internal=1(?:;|$)/.test(request.headers.get('cookie') || '')) return noContent();
  const ua = request.headers.get('user-agent') || '';
  if (!ua || BOT_RE.test(ua)) return noContent();

  const raw = await request.text().catch(() => '');
  if (!raw || raw.length > MAX_BODY) return noContent();
  let evt;
  try { evt = JSON.parse(raw); } catch { return noContent(); }
  if (!evt || typeof evt !== 'object') return noContent();
  const page = pageName(evt.p);
  if (!page) return noContent();

  const kind = KINDS.has(evt.k) ? evt.k : 'click';
  const tag = /^[a-z0-9-]{1,20}$/i.test(String(evt.r || '')) ? String(evt.r).toLowerCase() : '';
  const who = tag ? (ALIASES[tag] || tag.charAt(0).toUpperCase() + tag.slice(1)) : '';
  const secs = kind === 'time' ? Math.max(0, Math.min(86400, Math.round(Number(evt.s) || 0))) : null;

  const stmt = env.ACTIVITY_DB.prepare(
    'INSERT INTO events (ts, host, who, page, kind, item, secs, device, place, visit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind(Date.now(), url.host, who, page, kind, kind === 'time' ? '' : clip(evt.l, 200), secs,
    device(ua, !!evt.t), place(request.cf), clip(evt.v, 12));
  waitUntil(ensureSchema(env.ACTIVITY_DB).then(() => stmt.run()).catch((err) => console.log('track:', String(err.message || err))));
  return noContent();
}

export function onRequestGet() {
  return new Response('Not found.', { status: 404, headers: { 'cache-control': 'no-store' } });
}
