// Cloudflare Pages Function: /api/availability
// Public, read-only deer recovery availability for the next 7 days, in 30-minute slots.
//
// Source of truth: the SharePoint list "NGS Deer Availability", edited from the
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
// Weather hold: the "BASE" row of the SharePoint list "NGS Weather" (written by the Ops Worker and
// shown on the app's Go / No-Go screen) is read on every request. If any current factor is No-Go
// (st = 2), open slots in the next 60 minutes become "hold" instead of "open". Daylight is ignored,
// because deer searches fly at night. Weather data older than WEATHER_MAX_AGE_MIN is ignored.
//
// Environment: MS_TENANT_ID, MS_CLIENT_ID, SP_SITE_ID, GRAPH_CLIENT_SECRET (same as /api/quote)

const LIST_NAME = 'NGS Deer Availability';
const TZ = 'America/Chicago';
const DAYS = 7;
const SLOT = 30;          // minutes per slot
const FIRST_SLOT = 8 * 60;  // 8:00 AM
const LAST_SLOT = 21 * 60 + 30; // 9:30 PM slot, ends 10:00 PM
const CACHE_SECONDS = 10;  // short, so a change made in the app shows on the site within seconds
const WEATHER_LIST = 'NGS Weather';
const WEATHER_ROW = 'BASE';
const HOLD_WINDOW_MIN = 60;      // "right now" = slots overlapping the next 60 minutes
const WEATHER_MAX_AGE_MIN = 120; // ignore stale weather

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

// Current No-Go factors at base, ignoring daylight. Returns null when there is no usable data.
async function readWeather(env, token) {
  const r = await graph(token, 'GET',
    `${site(env)}/lists/${encodeURIComponent(WEATHER_LIST)}/items?$expand=fields($select=Title,FactorsJson,UpdatedAt,Verdict)&$top=200`);
  if (!r.ok) throw new Error(`Reading "${WEATHER_LIST}" failed (${r.status})`);
  const row = (r.data.value || []).map((it) => it.fields || {}).find((f) => String(f.Title || '').trim() === WEATHER_ROW);
  if (!row || !row.UpdatedAt) return null;
  const ageMin = (Date.now() - Date.parse(row.UpdatedAt)) / 60000;
  if (!(ageMin >= -5 && ageMin <= WEATHER_MAX_AGE_MIN)) return null;
  let factors = [];
  try { factors = JSON.parse(row.FactorsJson || '[]'); } catch { return null; }
  const nogo = factors
    .filter((f) => f && Number(f.st) === 2 && !/daylight/i.test(String(f.label || '')))
    .map((f) => ({ label: String(f.label || '').slice(0, 60), val: String(f.val || '').slice(0, 30), note: String(f.note || '').slice(0, 60) }));
  return { updatedAt: row.UpdatedAt, nogo };
}

// Minutes after midnight, Central time, right now.
function centralNowMinutes() {
  const p = {};
  new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
    .formatToParts(new Date()).forEach((x) => { p[x.type] = x.value; });
  return Number(p.hour) * 60 + Number(p.minute);
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
  const cacheKey = new Request(`${url.origin}/api/availability#v5`);
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const today = centralToday();
  const last = addDays(today, DAYS - 1);
  let overrides = {};
  let source = 'standard';
  let weather = null;
  if (configured) {
    try {
      const token = await getToken(env);
      const list = await ensureList(env, token);
      overrides = await readOverrides(env, token, list.id, today, last);
      source = 'live';
      try { weather = await readWeather(env, token); } catch (err) {
        console.error('weather read failed:', err && err.message ? err.message : err);
      }
    } catch (err) {
      console.error('availability read failed:', err && err.message ? err.message : err);
    }
  }
  const holdActive = !!(weather && weather.nogo.length);
  const nowMin = centralNowMinutes();
  // Today, nothing before the end of the next full hour is bookable (same rule as the page:
  // at 3:19 PM everything before 5:00 PM is closed), and past times are never open.
  const cutoff = (Math.floor(nowMin / 60) + 2) * 60;

  const days = [];
  for (let i = 0; i < DAYS; i++) {
    const date = addDays(today, i);
    const custom = Object.prototype.hasOwnProperty.call(overrides, date);
    let open = custom ? parseHours(overrides[date]) : standardHours(date);
    let hold = [];
    if (holdActive && i === 0) {
      // Slots that overlap [now, now + HOLD_WINDOW_MIN) are held for weather.
      const inWindow = (m) => m + SLOT > nowMin && m < nowMin + HOLD_WINDOW_MIN;
      hold = open.filter(inWindow);
      open = open.filter((m) => !inWindow(m));
    }
    if (i === 0) open = open.filter((m) => m >= cutoff);
    days.push({ date, weekday: weekdayOf(date), open, hold, custom });
  }

  const res = json(
    { ok: true, source, tz: TZ, today, firstSlot: FIRST_SLOT, lastSlot: LAST_SLOT, slotMinutes: SLOT, updated: new Date().toISOString(),
      weather: holdActive ? { hold: true, updatedAt: weather.updatedAt, reasons: weather.nogo } : { hold: false }, days },
    200,
    `public, max-age=${CACHE_SECONDS}`,
  );
  if (source === 'live') waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}
