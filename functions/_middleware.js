// Site-wide middleware.
// 1. Send www.novakgs.com to novakgs.com with a permanent redirect,
//    keeping the path and query string.
// 2. ?internal=1 marks this browser as internal (yours) with a 1-year cookie;
//    ?internal=0 clears it. Zaraz blocks GA4 for browsers with that cookie.
//    Either way, redirect to the same URL without the parameter.
export async function onRequest({ request, next }) {
  const url = new URL(request.url);
  if (url.hostname === 'www.novakgs.com') {
    url.hostname = 'novakgs.com';
    url.protocol = 'https:';
    return Response.redirect(url.toString(), 301);
  }
  const flag = url.searchParams.get('internal');
  if (flag === '1' || flag === '0') {
    url.searchParams.delete('internal');
    const cookie = flag === '1'
      ? 'novak_internal=1; Path=/; Max-Age=31536000; Secure; SameSite=Lax'
      : 'novak_internal=; Path=/; Max-Age=0; Secure; SameSite=Lax';
    return new Response(null, {
      status: 302,
      headers: { Location: url.toString(), 'Set-Cookie': cookie, 'Cache-Control': 'no-store' },
    });
  }
  return next();
}
