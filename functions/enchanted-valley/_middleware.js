// Cloudflare Pages Function: password gate for /enchanted-valley/ (page and images).
//
// Environment (Pages > Settings > Variables and Secrets):
//   EV_PASSWORD   (secret) — the password given to the Enchanted Valley owners.
//
// Visitors without a valid session see a branded password screen. A correct password sets an
// HttpOnly cookie for 30 days. The cookie is derived from the password, so changing EV_PASSWORD
// signs everyone out. If EV_PASSWORD is not set, the page stays locked.

const COOKIE = 'nv_ev';
const MAX_AGE = 60 * 60 * 24 * 30;
const BASE = '/enchanted-valley';

async function token(password) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', enc.encode(password), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode('novak-ev-session-v1'));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function safeEqual(a, b) {
  const x = new TextEncoder().encode(a);
  const y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}

function readCookie(request, name) {
  const header = request.headers.get('Cookie') || '';
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return v.join('=');
  }
  return '';
}

function loginPage(status, error) {
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Enchanted Valley Acres | Novak Geospatial Solutions</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700&family=Roboto+Mono:wght@400;500&display=swap">
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px 16px;
    background: #0a0d12 url("/topo-bg.jpg") center / cover no-repeat fixed; color: #eef1f3;
    font-family: Roboto, "Segoe UI", system-ui, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
  .card { width: 100%; max-width: 420px; background: rgba(12,16,22,.9); border: 1px solid rgba(255,255,255,.12);
    border-top: 2px solid #e8711a; border-radius: 14px; padding: 28px 24px; display: flex; flex-direction: column; gap: 16px; }
  img { height: 72px; width: auto; align-self: flex-start; }
  .kicker { margin: 0; font-size: 12px; font-weight: 600; letter-spacing: .24em; text-transform: uppercase; color: #e8711a; }
  h1 { margin: 0; font-size: 26px; line-height: 1.15; }
  p { margin: 0; color: #bec6ce; font-size: 15px; line-height: 1.55; }
  label { font-family: "Roboto Mono", Consolas, monospace; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: #c3cad1; }
  input { width: 100%; min-height: 48px; padding: 0 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,.25);
    background: #05070a; color: #eef1f3; font: 16px Roboto, system-ui, sans-serif; margin-top: 6px; }
  input:focus-visible, button:focus-visible { outline: 2px solid #e8711a; outline-offset: 2px; }
  button { min-height: 48px; border: 0; border-radius: 999px; background: #e8711a; color: #12161c; font: 600 15px Roboto, system-ui, sans-serif; cursor: pointer; }
  .err { color: #ffb38a; font-size: 14px; }
  .help { font-size: 13px; color: #a4adb6; }
  .help a { color: #eef1f3; }
</style>
</head>
<body>
<main class="card">
  <img src="/logo-dark.png" alt="Novak Geospatial Solutions">
  <p class="kicker">Private preview</p>
  <h1>Enchanted Valley Acres</h1>
  <p>This page was prepared for the owners of Enchanted Valley Acres. Enter the password you were given to view it.</p>
  <form method="post" action="${BASE}/" style="display: flex; flex-direction: column; gap: 14px">
    <div><label for="pw">Password</label><input id="pw" name="password" type="password" autocomplete="current-password" required autofocus></div>
    ${error ? '<p class="err" role="alert">That password didn’t work. Please try again.</p>' : ''}
    <button type="submit">View the page</button>
  </form>
  <p class="help">Need the password? Call or text <a href="tel:+16088200224">(608) 820-0224</a>.</p>
</main>
</body>
</html>`;
  return new Response(html, {
    status,
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow' },
  });
}

export async function onRequest({ request, env, next }) {
  const password = env.EV_PASSWORD;
  if (!password) {
    return new Response('This page is not available right now.', { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
  const expected = await token(password);
  const url = new URL(request.url);

  if (request.method === 'POST') {
    let given = '';
    try {
      const form = await request.formData();
      given = String(form.get('password') || '');
    } catch {
      return loginPage(400, true);
    }
    if (!safeEqual(given, password)) return loginPage(401, true);
    return new Response(null, {
      status: 303,
      headers: {
        Location: `${BASE}/`,
        'Set-Cookie': `${COOKIE}=${expected}; Path=${BASE}; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax`,
        'Cache-Control': 'no-store',
      },
    });
  }

  if (!safeEqual(readCookie(request, COOKIE), expected)) {
    // Images and other files just get a plain refusal; the page itself gets the password screen.
    const isPage = url.pathname === BASE || url.pathname === `${BASE}/` || url.pathname.endsWith('.html');
    return isPage ? loginPage(401, false) : new Response('Not authorized.', { status: 401, headers: { 'Cache-Control': 'no-store' } });
  }

  const response = await next();
  const out = new Response(response.body, response);
  out.headers.set('Cache-Control', 'private, no-store');
  out.headers.set('X-Robots-Tag', 'noindex, nofollow');
  return out;
}
