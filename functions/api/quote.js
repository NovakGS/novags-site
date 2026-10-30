// Cloudflare Pages Function: /api/quote
// POST  -> validates a quote request, stores it in the SharePoint "Quote Requests" list,
//          and uploads any attachments to "01 - Clients & Projects/02 - Prospects & Quotes/<date name>".
// GET ?check=1 -> reports whether configuration is present and makes sure the list exists.
//
// Environment (Pages > Settings > Variables and Secrets):
//   MS_TENANT_ID, MS_CLIENT_ID, SP_SITE_ID   (text)
//   GRAPH_CLIENT_SECRET                      (secret)
//   TURNSTILE_SECRET                         (secret, optional — enables Cloudflare Turnstile check)

const LIST_NAME = 'Quote Requests';
const QUOTE_FOLDER = '01 - Clients & Projects/02 - Prospects & Quotes';
const MAX_FILES = 5;
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_BYTES = 25 * 1024 * 1024;
const MIN_FILL_MS = 3000;

const CHOICES = {
  PreferredContact: ['Call', 'Text', 'WhatsApp', 'Email'],
  ClientType: ['Developer or builder', 'Contractor or aggregate', 'Realtor or landowner', 'Farm or ag', 'Surveyor or engineer', 'Other'],
  County: ['Dane', 'Columbia', 'Dodge', 'Green', 'Iowa', 'Jefferson', 'Rock', 'Sauk', 'Grant', 'Milwaukee', 'Waukesha',
    'Calumet', 'Outagamie', 'Winnebago', 'Marathon', 'Portage', 'Other'],
  SiteSize: ['Under 5 acres', '5–20 acres', '20–80 acres', '80+ acres', 'Not sure'],
  Timing: ['ASAP', 'Within 2 weeks', 'Within a month', 'Flexible', 'By a specific date'],
  HearAbout: ['Business card', 'Google Business', 'Search', 'Referral', 'LinkedIn', 'Meta (Facebook/IG)', 'Social media', 'Other'],
  Status: ['New', 'Contacted', 'Quoted', 'Won', 'Lost'],
};

const SERVICES = [
  'Pre-development assessment', 'Build progress monitoring', 'Time-lapse & marketing media',
  'Stockpile volume reports', 'Orthomosaic site maps', 'Progress documentation',
  'Acreage listing package', 'High-resolution aerial maps', 'Property overview imagery',
  'Field & farmstead maps', 'Grain & silage pile volumes', 'Cut/fill analysis', 'Visual crop scouting maps',
  'White-label RTK data capture', '3D structure model & measurements', 'Not sure — help me choose',
];
const FORMATS = ['PDF report', 'Images', 'GeoTIFF', 'KMZ', 'CAD (DXF)', 'Point cloud (LAS)', '3D model (OBJ)', '3D viewer link', 'Not sure'];

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

class UserError extends Error {}

function configStatus(env) {
  return {
    MS_TENANT_ID: !!env.MS_TENANT_ID,
    MS_CLIENT_ID: !!env.MS_CLIENT_ID,
    SP_SITE_ID: !!env.SP_SITE_ID,
    GRAPH_CLIENT_SECRET: !!env.GRAPH_CLIENT_SECRET,
    TURNSTILE_SECRET: !!env.TURNSTILE_SECRET,
  };
}

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
  if (!res.ok || !data.access_token) {
    throw new Error(`Token request failed (${res.status}): ${data.error || ''} ${data.error_description || ''}`.trim());
  }
  return data.access_token;
}

async function graph(token, method, path, body, extraHeaders = {}) {
  const url = path.startsWith('https://') ? path : `https://graph.microsoft.com/v1.0${path}`;
  const headers = { authorization: `Bearer ${token}`, ...extraHeaders };
  let payload = body;
  if (body && !(body instanceof ArrayBuffer) && typeof body !== 'string') {
    headers['content-type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(url, { method, headers, body: payload });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  return { ok: res.ok, status: res.status, data };
}

const site = (env) => `/sites/${env.SP_SITE_ID}`;
const encPath = (p) => p.split('/').map(encodeURIComponent).join('/');

function listColumns() {
  const choice = (name, choices, extra = {}) => ({ name, choice: { choices, displayAs: 'dropDownMenu', allowTextEntry: false }, ...extra });
  const text = (name) => ({ name, text: {} });
  const longText = (name) => ({ name, text: { allowMultipleLines: true, textType: 'plain', linesForEditing: 6 } });
  return [
    text('Company'),
    text('Email'),
    text('Phone'),
    choice('PreferredContact', CHOICES.PreferredContact),
    choice('ClientType', CHOICES.ClientType),
    text('SiteLocation'),
    choice('County', CHOICES.County),
    { name: 'Latitude', number: { decimalPlaces: 'automatic' } },
    { name: 'Longitude', number: { decimalPlaces: 'automatic' } },
    choice('SiteSize', CHOICES.SiteSize),
    longText('Services'),
    longText('ServiceDetails'),
    choice('Timing', CHOICES.Timing),
    { name: 'TargetDate', dateTime: { format: 'dateOnly' } },
    longText('Formats'),
    longText('Notes'),
    choice('HearAbout', CHOICES.HearAbout),
    text('Source'),
    text('AttachmentsLink'),
    choice('Status', CHOICES.Status, { defaultValue: { value: 'New' } }),
    { name: 'QuoteAmount', currency: { locale: 'en-us' } },
    { name: 'SubmittedAt', dateTime: { format: 'dateTime' } },
  ];
}

async function ensureList(env, token) {
  const found = await graph(token, 'GET', `${site(env)}/lists/${encodeURIComponent(LIST_NAME)}?$select=id,displayName,webUrl`);
  if (found.ok) return { id: found.data.id, webUrl: found.data.webUrl, created: false };
  if (found.status !== 404) throw new Error(`List lookup failed (${found.status}): ${JSON.stringify(found.data)}`);
  const made = await graph(token, 'POST', `${site(env)}/lists`, {
    displayName: LIST_NAME,
    list: { template: 'genericList' },
    columns: listColumns(),
  });
  if (!made.ok) throw new Error(`List create failed (${made.status}): ${JSON.stringify(made.data)}`);
  return { id: made.data.id, webUrl: made.data.webUrl, created: true };
}

async function uploadFile(env, token, folderPath, file) {
  const name = safeName(file.name || 'attachment') || 'attachment';
  const path = encPath(`${folderPath}/${name}`);
  const buf = await file.arrayBuffer();
  const session = await graph(token, 'POST', `${site(env)}/drive/root:/${path}:/createUploadSession`, {
    item: { '@microsoft.graph.conflictBehavior': 'rename' },
  });
  if (!session.ok) throw new Error(`Upload session failed (${session.status}): ${JSON.stringify(session.data)}`);
  const put = await fetch(session.data.uploadUrl, {
    method: 'PUT',
    headers: { 'content-length': String(buf.byteLength), 'content-range': `bytes 0-${buf.byteLength - 1}/${buf.byteLength}` },
    body: buf,
  });
  if (!put.ok) throw new Error(`Upload failed (${put.status}): ${await put.text()}`);
}

function safeName(s) {
  return String(s).replace(/["*:<>?/\\|#%]/g, '').replace(/\s+/g, ' ').trim().slice(0, 120);
}

const str = (fd, k, max = 255) => String(fd.get(k) ?? '').trim().slice(0, max);
const oneOf = (v, list) => (list.includes(v) ? v : '');

async function verifyTurnstile(env, fd, ip) {
  if (!env.TURNSTILE_SECRET) return true;
  const tokenValue = str(fd, 'cf-turnstile-response', 4096);
  if (!tokenValue) return false;
  const res = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
    method: 'POST',
    body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: tokenValue, remoteip: ip || '' }),
  });
  const data = await res.json().catch(() => ({}));
  return !!data.success;
}

function buildDetails(fd, services) {
  const lines = [];
  const has = (...names) => names.some((n) => services.includes(n));
  if (has('Stockpile volume reports', 'Grain & silage pile volumes')) {
    lines.push(`Volumes — piles: ${str(fd, 'pileCount', 20) || '?'}; material: ${str(fd, 'material', 120) || '?'}; frequency: ${str(fd, 'volumeFreq', 40) || '?'}`);
  }
  if (has('Build progress monitoring', 'Progress documentation')) {
    lines.push(`Progress — frequency: ${str(fd, 'progressFreq', 40) || '?'}; project length: ${str(fd, 'projectLength', 80) || '?'}`);
  }
  if (has('Acreage listing package', 'Property overview imagery')) {
    lines.push(`Listing — target listing date: ${str(fd, 'listingDate', 20) || '?'}`);
  }
  if (has('Visual crop scouting maps')) {
    lines.push(`Crop scouting — crop: ${str(fd, 'cropType', 80) || '?'}; growth stage: ${str(fd, 'growthStage', 80) || '?'}`);
  }
  if (has('White-label RTK data capture')) {
    lines.push(`White-label — coordinate system: ${str(fd, 'coordSystem', 160) || '?'}; accuracy: ${str(fd, 'accuracy', 120) || '?'}`);
  }
  if (has('3D structure model & measurements')) {
    lines.push(`3D structure — structure: ${str(fd, 'structure', 120) || '?'}; use: ${str(fd, 'structureUse', 60) || '?'}`);
  }
  return lines.join('\n');
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  if (url.searchParams.get('check') !== '1') return json({ ok: false, error: 'Use POST to submit a quote request.' }, 405);
  const config = configStatus(env);
  const required = ['MS_TENANT_ID', 'MS_CLIENT_ID', 'SP_SITE_ID', 'GRAPH_CLIENT_SECRET'];
  if (!required.every((k) => config[k])) return json({ ok: false, config });
  try {
    const token = await getToken(env);
    const list = await ensureList(env, token);
    return json({ ok: true, config, list: list.created ? 'created' : 'ready' });
  } catch (err) {
    return json({ ok: false, config, error: String(err.message || err) }, 500);
  }
}

export async function onRequestPost({ request, env }) {
  try {
    const ctype = request.headers.get('content-type') || '';
    if (!ctype.includes('multipart/form-data') && !ctype.includes('application/x-www-form-urlencoded')) {
      throw new UserError('Unsupported form submission.');
    }
    const fd = await request.formData();

    // Bot checks: honeypot field and minimum fill time.
    if (str(fd, 'website')) return json({ ok: true });
    const started = Number(fd.get('startedAt') || 0);
    if (started && Date.now() - started < MIN_FILL_MS) return json({ ok: true });
    if (!(await verifyTurnstile(env, fd, request.headers.get('cf-connecting-ip')))) {
      throw new UserError('Please complete the verification check and try again.');
    }

    const name = str(fd, 'name', 120);
    const email = str(fd, 'email', 160);
    const phone = str(fd, 'phone', 40);
    const preferred = oneOf(str(fd, 'preferredContact'), CHOICES.PreferredContact);
    const clientType = oneOf(str(fd, 'clientType'), CHOICES.ClientType);
    const siteLocation = str(fd, 'siteLocation', 255);
    const county = oneOf(str(fd, 'county'), CHOICES.County);
    const services = fd.getAll('services').map(String).filter((s) => SERVICES.includes(s));
    const timing = oneOf(str(fd, 'timing'), CHOICES.Timing);

    const missing = [];
    if (!name) missing.push('name');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) missing.push('a valid email');
    if (phone.replace(/\D/g, '').length < 10) missing.push('a phone number');
    if (!preferred) missing.push('how to reach you');
    if (!siteLocation) missing.push('the site location');
    if (!county) missing.push('the county');
    if (!services.length) missing.push('at least one service');
    if (missing.length) throw new UserError(`Please add ${missing.join(', ')}.`);

    const files = fd.getAll('files').filter((f) => f && typeof f === 'object' && f.size > 0);
    if (files.length > MAX_FILES) throw new UserError(`Please attach no more than ${MAX_FILES} files.`);
    let total = 0;
    for (const f of files) {
      if (f.size > MAX_FILE_BYTES) throw new UserError(`"${f.name}" is over 10 MB. Please send a smaller file.`);
      total += f.size;
    }
    if (total > MAX_TOTAL_BYTES) throw new UserError('Attachments are over 25 MB in total. Please send fewer or smaller files.');

    const lat = Number(fd.get('lat'));
    const lng = Number(fd.get('lng'));
    const targetDate = str(fd, 'targetDate', 10);
    const formats = fd.getAll('formats').map(String).filter((s) => FORMATS.includes(s));
    const source = str(fd, 'source', 40);
    let hearAbout = oneOf(str(fd, 'hearAbout'), CHOICES.HearAbout);
    if (!hearAbout && source === 'card') hearAbout = 'Business card';

    const token = await getToken(env);
    const list = await ensureList(env, token);

    let attachmentsLink = '';
    if (files.length) {
      const stamp = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
      const folder = `${QUOTE_FOLDER}/${stamp} ${safeName(name) || 'Quote request'}`;
      for (const f of files) await uploadFile(env, token, folder, f);
      const info = await graph(token, 'GET', `${site(env)}/drive/root:/${encPath(folder)}?$select=webUrl`);
      attachmentsLink = info.ok ? info.data.webUrl : folder;
    }

    const fields = {
      Title: name,
      Company: str(fd, 'company', 160),
      Email: email,
      Phone: phone,
      PreferredContact: preferred,
      SiteLocation: siteLocation,
      County: county,
      SiteSize: oneOf(str(fd, 'siteSize'), CHOICES.SiteSize) || 'Not sure',
      Services: services.join('\n'),
      ServiceDetails: buildDetails(fd, services),
      Formats: formats.join(', '),
      Notes: str(fd, 'notes', 4000),
      Source: source,
      AttachmentsLink: attachmentsLink,
      Status: 'New',
      SubmittedAt: new Date().toISOString(),
    };
    if (clientType) fields.ClientType = clientType;
    if (timing) fields.Timing = timing;
    if (hearAbout) fields.HearAbout = hearAbout;
    if (Number.isFinite(lat) && Number.isFinite(lng) && lat !== 0 && lng !== 0) {
      fields.Latitude = Math.round(lat * 1e6) / 1e6;
      fields.Longitude = Math.round(lng * 1e6) / 1e6;
    }
    if (/^\d{4}-\d{2}-\d{2}$/.test(targetDate)) fields.TargetDate = `${targetDate}T12:00:00Z`;

    let item = await graph(token, 'POST', `${site(env)}/lists/${list.id}/items`, { fields });
    if (!item.ok && fields.HearAbout) {
      // The SharePoint choice column may not list a newer option yet; keep the answer in Source and save anyway.
      fields.Source = [fields.Source, `heard: ${fields.HearAbout}`].filter(Boolean).join(' | ');
      delete fields.HearAbout;
      item = await graph(token, 'POST', `${site(env)}/lists/${list.id}/items`, { fields });
    }
    if (!item.ok) throw new Error(`Item create failed (${item.status}): ${JSON.stringify(item.data)}`);

    return json({ ok: true });
  } catch (err) {
    if (err instanceof UserError) return json({ ok: false, error: err.message }, 400);
    console.error('quote submission failed:', err && err.message ? err.message : err);
    return json({ ok: false, error: 'Something went wrong on our end. Please call or text 608-820-0224, or email info@novakgs.com.' }, 500);
  }
}
