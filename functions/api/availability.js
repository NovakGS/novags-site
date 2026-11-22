// Cloudflare Pages Function: /api/availability
// Public, read-only deer recovery availability for the next 7 days, in 30-minute slots.
//
// Source of truth: the SharePoint list "Deer Recovery Availability", edited from the
// Novak|GS Power App. One row per day that differs from the standard hours:
//   Title      text  "YYYY-MM-DD" (Central time)
//   OpenHours  text  comma-wrapped open slot starts in minutes after midnight,
//                    e.g. ",480,510,540," (8:00, 8:30, 9:00). "," = whole day unavailable.
// A day with no row uses the standard hours:
//   every day 8:00 AM-5:00 PM; Sunday and Monday until 10:00 PM;
//   Tuesday until 10:00 PM except 5:30-7:30 PM.
//
// GET           -> { ok, tz, firstSlot, lastSlot, slotMinutes, days:[{date, weekday, open:[480,510,...], custom}] }
// GET ?check=1  -> makes sure the list exists (creates it if missing) and reports config.
//
// Environment: MS_TENANT_ID, MS_CLIENT_ID, SP_SITE_ID, GRAPH_CLIENT_SECRET (same as /api/quote)

const LIST_NAME = 'Deer Recovery Availability';
const TZ = 'America/Chicago';
const DAYS = 7;
const SLOT = 30;          // minutes per slot
const FIRST_SLOT = 8 * 60;  // 8:00 AM
const LAST_SLOT = 21 * 60 + 30; // 9:30 PM slot, ends 10:00 PM
const CACHE_SECONDS = 60;

const json = (body, status = 200, cache = 'no-store') =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': cache, 'access-control-allow-origin': '*' },
  });

async function getToken(env) {
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
  return data.access_token;
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

async function ensureList(env, token) {
  const found = await graph(token, 'GET', `${site(env)}/lists/${encodeURIComponent(LIST_NAME)}?$select=id,webUrl`);
  if (found.ok) return { id: found.data.id, webUrl: found.data.webUrl, created: false };
  if (found.status !== 404) throw new Error(`List lookup failed (${found.status})`);
  const made = await graph(token, 'POST', `${site(env)}/lists`, {
    displayName: LIST_NAME,
    list: { template: 'genericList' },
    columns: [
      { name: 'OpenHours', text: {} },
      { name: 'Note', text: {} },
    ],
  });
  if (!made.ok) throw new Error(`List create failed (${made.status}): ${JSON.stringify(made.data).slice(0, 300)}`);
  return { id: made.data.id, webUrl: made.data.webUrl, created: true };
}

// Today's date in Central time, as YYYY-MM-DD.
function centralToday() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

function addDays(ymd, n) {
  const d = new Date(`${ymd}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

const weekdayOf = (ymd) => new Date(`${ymd}T12:00:00Z`).getUTCDay(); // 0 = Sunday

// Standard open windows [start, end) in minutes after midnight, by weekday (0 = Sunday).
const DAY = [[8 * 60, 17 * 60]];
const LATE = [[8 * 60, 22 * 60]];
const STANDARD = {
  0: LATE,                                          // Sunday 8:00 AM-10:00 PM
  1: LATE,                                          // Monday 8:00 AM-10:00 PM
  2: [[8 * 60, 17 * 60 + 30], [19 * 60 + 30, 22 * 60]], // Tuesday, off 5:30-7:30 PM
  3: DAY, 4: DAY, 5: DAY, 6: DAY,                   // 8:00 AM-5:00 PM
};

function standardHours(ymd) {
  const out = [];
  for (const [a, b] of STANDARD[weekdayOf(ymd)]) for (let m = a; m + SLOT <= b; m += SLOT) out.push(m);
  return out;
}

function parseHours(s) {
  return [...new Set(String(s || '').split(',').map((x) => Number(x.trim())).filter((m) => Number.isInteger(m) && m % SLOT === 0 && m >= FIRST_SLOT && m <= LAST_SLOT))]
    .sort((a, b) => a - b);
}

async function readOverrides(env, token, listId, from, to) {
  const out = {};
  let next = `${site(env)}/lists/${listId}/items?$expand=fields($select=Title,OpenHours)&$top=500`;
  while (next) {
    const r = await graph(token, 'GET', next);
    if (!r.ok) throw new Error(`Reading "${LIST_NAME}" failed (${r.status})`);
    for (const it of r.data.value || []) {
      const f = it.fields || {};
      const day = String(f.Title || '').trim();
      if (/^\d{4}-\d{2}-\d{2}$/.test(day) && day >= from && day <= to) out[day] = f.OpenHours ?? '';
    }
    next = r.data['@odata.nextLink'] || null;
  }
  return out;
}

export async function onRequestGet({ request, env, waitUntil }) {
  const url = new URL(request.url);
  const required = ['MS_TENANT_ID', 'MS_CLIENT_ID', 'SP_SITE_ID', 'GRAPH_CLIENT_SECRET'];
  const configured = required.every((k) => !!env[k]);

  if (url.searchParams.get('check') === '1') {
    if (!configured) return json({ ok: false, error: 'Missing configuration' }, 500);
    try {
      const token = await getToken(env);
      const list = await ensureList(env, token);
      return json({ ok: true, list: list.created ? 'created' : 'ready', webUrl: list.webUrl });
    } catch (err) {
      return json({ ok: false, error: String(err.message || err) }, 500);
    }
  }

  // Short edge cache so a page full of visitors doesn't hit SharePoint on every load.
  const cache = caches.default;
  const cacheKey = new Request(`${url.origin}/api/availability#v2`);
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const today = centralToday();
  const last = addDays(today, DAYS - 1);
  let overrides = {};
  let source = 'standard';
  if (configured) {
    try {
      const token = await getToken(env);
      const list = await ensureList(env, token);
      overrides = await readOverrides(env, token, list.id, today, last);
      source = 'live';
    } catch (err) {
      console.error('availability read failed:', err && err.message ? err.message : err);
    }
  }

  const days = [];
  for (let i = 0; i < DAYS; i++) {
    const date = addDays(today, i);
    const custom = Object.prototype.hasOwnProperty.call(overrides, date);
    days.push({ date, weekday: weekdayOf(date), open: custom ? parseHours(overrides[date]) : standardHours(date), custom });
  }

  const res = json(
    { ok: true, source, tz: TZ, today, firstSlot: FIRST_SLOT, lastSlot: LAST_SLOT, slotMinutes: SLOT, updated: new Date().toISOString(), days },
    200,
    `public, max-age=${CACHE_SECONDS}`,
  );
  if (source === 'live') waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}
