// Site-wide: send www.novakgs.com to novakgs.com with a permanent redirect,
// keeping the path and query string. Everything else passes through.
export async function onRequest({ request, next }) {
  const url = new URL(request.url);
  if (url.hostname === 'www.novakgs.com') {
    url.hostname = 'novakgs.com';
    url.protocol = 'https:';
    return Response.redirect(url.toString(), 301);
  }
  return next();
}
