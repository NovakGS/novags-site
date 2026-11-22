// Cloudflare Pages Function: first-party proxy for the Origami website visitor snippet.
// Forwards exactly three paths to Origami and answers 404 to anything else under /_ov/:
//   /_ov/o.js      -> https://origami-web-visitors.com/v1/o.js
//   /_ov/e         -> https://origami-web-visitors.com/v1/e
//   /_ov/identify  -> https://origami-web-visitors.com/v1/identify
// Never widen this to a catch-all: the proxy attaches the secret key, and Origami's /v1/s
// endpoint accepts deletions.
//
// Environment (Pages > Settings > Variables and Secrets):
//   ORIGAMI_VISITORS_SECRET_KEY   (secret) — the site's og_sk_... key from Origami.
// If it is not set, the proxy answers 503 and nothing is sent to Origami.

const ORIGIN = 'https://origami-web-visitors.com/v1/';
const ALLOWED = new Set(['o.js', 'e', 'identify']);

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const path = url.pathname.slice('/_ov/'.length);
  if (!ALLOWED.has(path)) return new Response(null, { status: 404 });

  const secret = env.ORIGAMI_VISITORS_SECRET_KEY;
  if (!secret) return new Response(null, { status: 503, headers: { 'Cache-Control': 'no-store' } });

  const headers = new Headers(request.headers);
  // The visitor's IP as Cloudflare saw it; overwrites anything the browser sent.
  headers.set('X-Origami-Client-IP', request.headers.get('CF-Connecting-IP') ?? '');
  headers.set('Authorization', `Bearer ${secret}`);
  headers.delete('Cookie');

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  return fetch(ORIGIN + path + url.search, {
    method: request.method,
    headers,
    body: hasBody ? request.body : null,
  });
}
