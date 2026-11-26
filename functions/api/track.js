// Cloudflare Pages Function: /api/track
// First-party activity log for the Hamele package pages (/hamele/...). No cookies are set and
// no third party is involved: each event becomes one item in a SharePoint list on the Novak site.
//
// POST (sent by /hamele/track.js with navigator.sendBeacon) -> logs one event:
//   page views, clicks, downloads, call/text/email taps, map changes, FAQ opens, and time on page.
//   Live link (LIVE_HOSTS)  -> list "Hamele Activity"
//   Any other host (preview builds) -> list "Hamele Activity Test", so testing never mixes in.
// Browsers marked internal with ?internal=1 (cookie novak_internal=1, set by functions/_middleware.js)
// are never logged. ?r=<name> on the page link tags a visitor (handled in /hamele/track.js).
//
// GET ?check=1 -> reports whether configuration is present and makes sure the list exists.
//   On test hosts only, it also lists the newest test rows, and &clear=1 deletes the test rows.
//
// Environment (Pages > Settings > Variables and Secrets), same as /api/quote:
//   MS_TENANT_ID, MS_CLIENT_ID, SP_SITE_ID (text), GRAPH_CLIENT_SECRET (secret)

const LIVE_HOSTS = new Set(['hamele.novags-site.pages.dev', 'novakgs.com']);
const LIVE_LIST = 'Hamele Activity';
const TEST_LIST = 'Hamele Activity Test';
const MAX_BODY = 2000;
const BOT_RE = /bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|headless|lighthouse|pingdom|monitor/i;

const PAGES = {
  '/hamele/': 'Presentation',
  '/hamele/map/': 'Hunting & Recreation',
  '/hamele/due-diligence/': 'Buyer Due Diligence',
  '/hamele/stewardship/': 'Stewardship',
  '/hamele/essentials/': 'Essentials',
};

const ACTIONS = {
  view: 'Viewed page',
  click: 'Clicked',
  download: 'Downloaded',
  folder: 'Opened Drive folder',
  call: 'Tapped call',
  text: 'Tapped text',
  email: 'Tapped email',
  out: 'Opened outside link',
  faq: 'Opened question',
  map: 'Changed map',
  time: 'Time on page so far',
};

const COLUMNS = [
  { name: 'EventTime', displayName: 'When', dateTime: { format: 'dateTime' } },
  { name: 'Visitor', displayName: 'Who', text: {} },
  { name: 'PageName', displayName: 'Page', text: {} },
  { name: 'Action', displayName: 'Action', text: {} },
  { name: 'Item', displayName: 'Item', text: {} },
  { name: 'TimeOnPage', displayName: 'Seconds on Page', number: {} },
  { name: 'Device', displayName: 'Device', text: {} },
  { name: 'Place', displayName: 'Place', text: {} },
  { name: 'VisitId', displayName: 'Visit', text: {} },
];

const json = (body, status = 200) =>
  new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
const noContent = () => new Response(null, { status: 204, headers: { 'cache-control': 'no-store' } });

const clip = (v, n) => String(v == null ? '' : v).replace(/[\u0000-\u001f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);
const isInternal = (request) => /(?:^|;\s*)novak_internal=1(?:;|$)/.test(request.headers.get('cookie') || '');
const listFor = (host) => (LIVE_HOSTS.has(host) ? LIVE_LIST : TEST_LIST);

// ---------- Microsoft Graph ----------
let tokenCache = { value: '', exp: 0 };
const listIds = new Map();

async function getToken(env) {
  if (tokenCache.value && Date.now() < tokenCache.exp) return tokenCache.value;
  const res = await fetch(`https://login.microsoftonline.com/${env.MS_TENANT_ID}/oauth2/v2.0/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: env.MS_CLIENT_ID,
      client_secret: env.GRAPH_CLIENT_SECRET,
      scope: 'https://graph.microsoft.com/.default',
      grant_type: 'client_credentials',
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token) throw new Error(`Token request failed (${res.status}): ${data.error || ''}`);
  tokenCache = { value: data.access_token, exp: Date.now() + Math.max(60, (Number(data.expires_in) || 3600) - 300) * 1000 };
  return tokenCache.value;
}

async function graph(token, method, path, body) {
  const url = path.startsWith('https://') ? path : `https://graph.microsoft.com/v1.0${path}`;
  const headers = { authorization: `Bearer ${token}` };
  if (body) headers['content-type'] = 'application/json';
  const res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  return { ok: res.ok, status: res.status, data };
}

const site = (env) => `/sites/${env.SP_SITE_ID}`;

async function ensureList(env, token, name) {
  if (listIds.has(name)) return { id: listIds.get(name), created: false };
  const lookup = () => graph(token, 'GET', `${site(env)}/lists/${encodeURIComponent(name)}?$select=id,webUrl`);
  let found = await lookup();
  if (found.ok) { listIds.set(name, found.data.id); return { id: found.data.id, webUrl: found.data.webUrl, created: false }; }
  if (found.status !== 404) throw new Error(`List lookup failed (${found.status}): ${JSON.stringify(found.data)}`);
  const made = await graph(token, 'POST', `${site(env)}/lists`, {
    displayName: name,
    list: { template: 'genericList' },
    columns: COLUMNS,
  });
  if (!made.ok) {
    // Another request may have made it a moment ago.
    found = await lookup();
    if (found.ok) { listIds.set(name, found.data.id); return { id: found.data.id, webUrl: found.data.webUrl, created: false }; }
    throw new Error(`List create failed (${made.status}): ${JSON.stringify(made.data)}`);
  }
  listIds.set(name, made.data.id);
  return { id: made.data.id, webUrl: made.data.webUrl, created: true };
}

// ---------- Event details ----------
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

const fmtCentral = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', weekday: 'short', month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit',
});
const central = (d) => fmtCentral.format(d).replace(/,/g, '').replace(/ /g, ' ');

function duration(s) {
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60), r = s % 60;
  return r ? `${m} min ${r} s` : `${m} min`;
}

function buildFields(evt, request) {
  const now = new Date();
  const kind = Object.prototype.hasOwnProperty.call(ACTIONS, evt.k) ? evt.k : 'click';
  const page = pageName(evt.p);
  const tag = /^[a-z0-9-]{1,20}$/i.test(String(evt.r || '')) ? String(evt.r) : '';
  const who = tag ? tag.charAt(0).toUpperCase() + tag.slice(1).toLowerCase() : 'Other visitor';
  const secs = kind === 'time' ? Math.max(0, Math.min(86400, Math.round(Number(evt.s) || 0))) : null;
  const item = kind === 'time' ? duration(secs) : clip(evt.l, 200);
  const action = ACTIONS[kind];

  let title = `${central(now)} · ${who} · ${action}`;
  if (kind === 'view') title += `: ${page}${item ? ` (${item})` : ''}`;
  else if (kind === 'time') title += `: ${page}, ${item}`;
  else title += `${item ? `: ${item}` : ''} (${page})`;

  return {
    Title: clip(title, 255),
    EventTime: now.toISOString(),
    Visitor: who,
    PageName: page,
    Action: action,
    Item: clip(item, 255),
    ...(secs == null ? {} : { TimeOnPage: secs }),
    Device: device(request.headers.get('user-agent') || '', !!evt.t),
    Place: place(request.cf),
    VisitId: clip(evt.v, 12),
  };
}

async function writeEvent(env, listName, fields) {
  const token = await getToken(env);
  const list = await ensureList(env, token, listName);
  let r = await graph(token, 'POST', `${site(env)}/lists/${list.id}/items`, { fields });
  if (!r.ok && (r.status === 429 || r.status >= 500)) {
    await new Promise((ok) => setTimeout(ok, 1500));
    r = await graph(token, 'POST', `${site(env)}/lists/${list.id}/items`, { fields });
  }
  if (!r.ok) console.log('track: item write failed', r.status, JSON.stringify(r.data).slice(0, 300));
}

// ---------- Handlers ----------
export async function onRequestPost({ request, env, waitUntil }) {
  const url = new URL(request.url);
  const origin = request.headers.get('origin');
  if (origin && origin !== 'null') {
    try { if (new URL(origin).host !== url.host) return new Response(null, { status: 403 }); } catch { return new Response(null, { status: 403 }); }
  }
  if (isInternal(request)) return noContent();
  if (BOT_RE.test(request.headers.get('user-agent') || '')) return noContent();
  if (!env.MS_TENANT_ID || !env.MS_CLIENT_ID || !env.SP_SITE_ID || !env.GRAPH_CLIENT_SECRET) return noContent();

  const raw = await request.text().catch(() => '');
  if (!raw || raw.length > MAX_BODY) return noContent();
  let evt;
  try { evt = JSON.parse(raw); } catch { return noContent(); }
  if (!evt || typeof evt !== 'object' || !pageName(evt.p)) return noContent();

  const fields = buildFields(evt, request);
  waitUntil(writeEvent(env, listFor(url.host), fields).catch((err) => console.log('track:', String(err.message || err))));
  return noContent();
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  if (url.searchParams.get('check') !== '1') return json({ ok: false, error: 'Not found.' }, 404);
  const config = {
    MS_TENANT_ID: !!env.MS_TENANT_ID,
    MS_CLIENT_ID: !!env.MS_CLIENT_ID,
    SP_SITE_ID: !!env.SP_SITE_ID,
    GRAPH_CLIENT_SECRET: !!env.GRAPH_CLIENT_SECRET,
  };
  if (!Object.values(config).every(Boolean)) return json({ ok: false, config });
  const name = listFor(url.host);
  try {
    const token = await getToken(env);
    const list = await ensureList(env, token, name);
    const out = { ok: true, config, list: name, status: list.created ? 'created' : 'ready' };
    if (name === TEST_LIST) {
      const items = await graph(token, 'GET', `${site(env)}/lists/${list.id}/items?$expand=fields($select=Title,Device,Place,VisitId)&$top=200`);
      const rows = (items.ok && items.data && items.data.value ? items.data.value : []).sort((a, b) => Number(b.id) - Number(a.id));
      if (url.searchParams.get('clear') === '1') {
        let deleted = 0;
        for (const row of rows) {
          const d = await graph(token, 'DELETE', `${site(env)}/lists/${list.id}/items/${row.id}`);
          if (d.ok) deleted++;
        }
        out.deleted = deleted;
      } else {
        out.count = rows.length;
        out.newest = rows.slice(0, 25).map((r) => [r.fields.Title, r.fields.Device, r.fields.Place, r.fields.VisitId].join(' | '));
      }
    }
    return json(out);
  } catch (err) {
    return json({ ok: false, config, error: String(err.message || err) }, 500);
  }
}
