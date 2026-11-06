// Cloudflare Pages Function: /api/jobs
// Keeps the SharePoint "NGS Jobs" list (used by the Novak|GS Power App) in step with the job
// folders made by New-Job.ps1, so jobs are only ever created by that script.
//
// GET   -> lists the jobs in "NGS Jobs" (JobNumber, Title, Client, SiteAddress, Stage)
// POST  {"jobs":[{"jobNumber":"26-226","client":"Baker","site":"477-Blue-Mounds-Trl"}, ...]}
//       -> adds any job whose JobNumber is not in the list yet (Stage = Lead). Existing rows are
//          never changed, so anything edited in the app (stage, dates, address) is kept.
// Both need the header  x-jobs-key: <JOBS_KEY>
//
// Environment (Pages > Settings > Variables and Secrets):
//   MS_TENANT_ID, MS_CLIENT_ID, SP_SITE_ID, GRAPH_CLIENT_SECRET   (same as /api/quote)
//   JOBS_KEY                                                      (secret, also in 99_Tools\config.json)

const LIST_NAME = 'NGS Jobs';
const JOB_RE = /^\d{2}-\d{3}$/;

const json = (body, status = 200) =>
  new Response(JSON.stringify(body, null, 2), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

function authed(request, env) {
  const a = String(request.headers.get('x-jobs-key') || '');
  const b = String(env.JOBS_KEY || '');
  if (!b || a.length !== b.length) return false;
  let x = 0;
  for (let i = 0; i < a.length; i++) x |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return x === 0;
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

async function listId(env, token) {
  const r = await graph(token, 'GET', `${site(env)}/lists/${encodeURIComponent(LIST_NAME)}?$select=id`);
  if (!r.ok) throw new Error(`"${LIST_NAME}" list lookup failed (${r.status})`);
  return r.data.id;
}

async function readJobs(env, token, id) {
  const out = [];
  let next = `${site(env)}/lists/${id}/items?$expand=fields($select=Title,JobNumber,Client,SiteAddress,Stage)&$top=999`;
  while (next) {
    const r = await graph(token, 'GET', next);
    if (!r.ok) throw new Error(`Reading "${LIST_NAME}" failed (${r.status})`);
    for (const it of r.data.value || []) {
      const f = it.fields || {};
      out.push({ id: it.id, JobNumber: f.JobNumber || '', Title: f.Title || '', Client: f.Client || '', SiteAddress: f.SiteAddress || '', Stage: f.Stage || '' });
    }
    next = r.data['@odata.nextLink'] || null;
  }
  return out;
}

const clean = (s, max = 120) => String(s ?? '').replace(/[<>]/g, '').trim().slice(0, max);
// Folder names use dashes for spaces ("477-Blue-Mounds-Trl"); the app shows them with spaces.
const words = (s) => clean(s).replace(/-+/g, ' ').replace(/\s+/g, ' ').trim();

export async function onRequest({ request, env }) {
  if (!authed(request, env)) return json({ ok: false, error: 'Missing or wrong key' }, 401);
  try {
    const token = await getToken(env);
    const id = await listId(env, token);
    const existing = await readJobs(env, token, id);

    if (request.method === 'GET') {
      existing.sort((a, b) => b.JobNumber.localeCompare(a.JobNumber));
      return json({ ok: true, count: existing.length, jobs: existing });
    }
    if (request.method !== 'POST') return json({ ok: false, error: 'Use GET or POST' }, 405);

    const body = await request.json().catch(() => ({}));
    const jobs = Array.isArray(body.jobs) ? body.jobs.slice(0, 200) : [];
    const have = new Set(existing.map((j) => j.JobNumber));
    const added = [], skipped = [], invalid = [];

    for (const j of jobs) {
      const jobNumber = clean(j.jobNumber, 10);
      if (!JOB_RE.test(jobNumber)) { invalid.push(jobNumber || '(blank)'); continue; }
      if (have.has(jobNumber)) { skipped.push(jobNumber); continue; }
      const client = words(j.client);
      const siteName = words(j.site);
      const fields = {
        Title: [client, siteName].filter(Boolean).join(' – ') || jobNumber,
        JobNumber: jobNumber,
        Client: client,
        SiteAddress: siteName,
        Stage: 'Lead',
      };
      const r = await graph(token, 'POST', `${site(env)}/lists/${id}/items`, { fields });
      if (!r.ok) throw new Error(`Adding ${jobNumber} failed (${r.status}): ${JSON.stringify(r.data).slice(0, 300)}`);
      have.add(jobNumber);
      added.push(jobNumber);
    }
    return json({ ok: true, added, skipped, invalid });
  } catch (err) {
    return json({ ok: false, error: String(err.message || err) }, 500);
  }
}
