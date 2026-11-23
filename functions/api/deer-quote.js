// Cloudflare Pages Function: /api/deer-quote
// Instant deer recovery quote from the hunter's location.
//
// POST { q: "address, town, or 'lat, lon'" }  or  { lat, lon }
//   -> { ok, place, roundTripMiles, billableMiles, rate, search, mileage, notLocated, located, inArea, approx }
//
// The pilot's home (trip start) is NEVER sent to the browser and never stored in this public repo.
// Set it in Cloudflare Pages > Settings > Variables and Secrets (as a Secret):
//   NOVAK_HOME   street address, e.g. "123 Main St, Cross Plains, WI 53528"
//                (or "lat, lon" to skip geocoding)
// Optional:
//   MILEAGE_RATE  dollars per mile (defaults to the IRS business rate below)
//
// Until NOVAK_HOME is set, trips are measured from the center of Cross Plains, WI.

const SEARCH_FEE = 225;
const LOCATED_FEE = 100;
const FREE_ROUND_TRIP_MILES = 50;
const IRS_RATE = 0.76; // IRS business standard mileage rate, effective July 1, 2026 (Announcement 2026-11)
const FALLBACK_HOME = { lat: 43.1145, lon: -89.6557 }; // Cross Plains village center
const UA = 'NovakGS-DeerQuote/1.0 (info@novakgs.com)';

// Southern Wisconsin: roughly from the Illinois line north to about Hwy 10.
const SOUTH_WI = { minLat: 42.49, maxLat: 44.45, minLon: -91.3, maxLon: -86.8 };

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

const parseLatLon = (s) => {
  const m = String(s || '').trim().match(/^(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)$/);
  if (!m) return null;
  const lat = Number(m[1]), lon = Number(m[2]);
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null;
};

async function geocode(q) {
  const ll = parseLatLon(q);
  if (ll) return { ...ll, label: `${ll.lat.toFixed(5)}, ${ll.lon.toFixed(5)}` };
  // 1) US Census geocoder (street addresses)
  try {
    const u = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?benchmark=Public_AR_Current&format=json&address=' + encodeURIComponent(q);
    const r = await fetch(u, { headers: { 'user-agent': UA }, cf: { cacheTtl: 86400 } });
    if (r.ok) {
      const m = (await r.json())?.result?.addressMatches?.[0];
      if (m) return { lat: m.coordinates.y, lon: m.coordinates.x, label: m.matchedAddress };
    }
  } catch (e) {}
  // 2) OpenStreetMap Nominatim (towns, roads, landmarks)
  try {
    const hint = /\b(wi|wisconsin)\b/i.test(q) ? q : q + ', Wisconsin';
    const u = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=us&q=' + encodeURIComponent(hint);
    const r = await fetch(u, { headers: { 'user-agent': UA, 'accept-language': 'en' }, cf: { cacheTtl: 86400 } });
    if (r.ok) {
      const m = (await r.json())?.[0];
      if (m) return { lat: Number(m.lat), lon: Number(m.lon), label: m.display_name.split(', ').slice(0, 4).join(', ') };
    }
  } catch (e) {}
  return null;
}

let homeCache = null;
async function home(env) {
  const raw = (env.NOVAK_HOME || '').trim();
  if (!raw) return FALLBACK_HOME;
  if (homeCache && homeCache.raw === raw) return homeCache.pt;
  const g = await geocode(raw);
  const pt = g ? { lat: g.lat, lon: g.lon } : FALLBACK_HOME;
  homeCache = { raw, pt };
  return pt;
}

const haversineMi = (a, b) => {
  const R = 3958.8, rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
};

async function drivingMiles(a, b) {
  try {
    const u = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=false`;
    const r = await fetch(u, { headers: { 'user-agent': UA } });
    if (r.ok) {
      const d = await r.json();
      if (d.code === 'Ok' && d.routes?.[0]) return { miles: d.routes[0].distance / 1609.344, approx: false };
    }
  } catch (e) {}
  return { miles: haversineMi(a, b) * 1.3, approx: true }; // road-distance estimate if routing is down
}

export async function onRequestPost({ request, env }) {
  let body;
  try { body = await request.json(); } catch (e) { return json({ ok: false, error: 'Bad request.' }, 400); }

  let dest;
  if (Number.isFinite(body.lat) && Number.isFinite(body.lon)) {
    dest = { lat: body.lat, lon: body.lon, label: 'Your current location' };
  } else {
    const q = String(body.q || '').trim().slice(0, 200);
    if (q.length < 3) return json({ ok: false, error: 'Enter an address, town, or GPS coordinates.' }, 400);
    dest = await geocode(q);
    if (!dest) return json({ ok: false, error: "That location couldn't be found. Try a nearby address or town, or use your current location." }, 404);
  }

  const start = await home(env);
  const leg = await drivingMiles(start, dest);
  const roundTrip = Math.round(leg.miles * 2);
  const rate = Number(env.MILEAGE_RATE) > 0 ? Number(env.MILEAGE_RATE) : IRS_RATE;
  const billable = Math.max(0, roundTrip - FREE_ROUND_TRIP_MILES);
  const mileage = Math.round(billable * rate * 100) / 100;
  const inArea = dest.lat >= SOUTH_WI.minLat && dest.lat <= SOUTH_WI.maxLat && dest.lon >= SOUTH_WI.minLon && dest.lon <= SOUTH_WI.maxLon;

  return json({
    ok: true,
    place: dest.label,
    roundTripMiles: roundTrip,
    freeMiles: FREE_ROUND_TRIP_MILES,
    billableMiles: billable,
    rate,
    search: SEARCH_FEE,
    locatedFee: LOCATED_FEE,
    mileage,
    notLocated: SEARCH_FEE + mileage,
    located: SEARCH_FEE + LOCATED_FEE + mileage,
    inArea,
    approx: leg.approx,
  });
}

export const onRequestGet = () => json({ ok: false, error: 'Use POST.' }, 405);
