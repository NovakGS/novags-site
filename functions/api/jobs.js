// Cloudflare Pages Function: /api/jobs
// Keeps the SharePoint "NGS Jobs" list (used by the Novak|GS Power App) in step with the job
// folders in C:\NovakGS_Work\01_Active, and lets the app ask for a new job.
//
// GET                      -> lists the jobs in "NGS Jobs"
// GET ?requests=1          -> only the app's New Job requests that still need a folder
//
// POST {"jobs":[{"jobNumber":"26-226","client":"Baker","site":"477-Blue-Mounds-Trl","folder":"26-226_Baker_477-Blue-Mounds-Trl"}, ...],
//       "full": true}
//   -> sync. Adds any job whose JobNumber is not in the list yet (Stage = Lead). A new job number
//      first fills the app request that is being created right now (FolderStatus = Creating), so a
//      job started in the app never shows up twice. App-edited fields (stage, dates, notes) are kept.
//      With "folder", a renamed folder updates Client, SiteAddress and Title.
//      With "full": true (the list is every folder in 01_Active), jobs whose folder is gone are
//      marked FolderStatus = Archived and come back to Active if the folder returns. Nothing is deleted.
//      The reply lists the open app requests.
// POST {"action":"claim","id":"12"}                                  -> request 12 is being created
// POST {"action":"done","id":"12","jobNumber":"26-240","folder":"26-240_Client_Site"}
// POST {"action":"fail","id":"12","note":"why"}
// All need the header  x-jobs-key: <JOBS_KEY>
//
// Environment (Pages > Settings > Variables and Secrets):
//   MS_TENANT_ID, MS_CLIENT_ID, SP_SITE_ID, GRAPH_CLIENT_SECRET   (same as /api/quote)
//   JOBS_KEY                                                      (secret, also in 99_Tools\config.json)

const LIST_NAME = 'NGS Jobs';
const JOB_RE = /^\d{2}-\d{3}$/;
const FIELDS = 'Title,JobNumber,Client,SiteAddress,Stage,FolderStatus,FolderName,FolderNote';

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
  let next = `${site(env)}/lists/${id}/items?$expand=fields($select=${FIELDS})&$top=999`;
  while (next) {
    const r = await graph(token, 'GET', next);
    if (!r.ok) throw new Error(`Reading "${LIST_NAME}" failed (${r.status})`);
    for (const it of r.data.value || []) {
      const f = it.fields || {};
      out.push({
        id: String(it.id), JobNumber: f.JobNumber || '', Title: f.Title || '', Client: f.Client || '',
        SiteAddress: f.SiteAddress || '', Stage: f.Stage || '', FolderStatus: f.FolderStatus || '',
        FolderName: f.FolderName || '', FolderNote: f.FolderNote || '', Created: it.createdDateTime || '',
      });
    }
    next = r.data['@odata.nextLink'] || null;
  }
  return out;
}

async function patch(env, token, id, itemId, fields) {
  const r = await graph(token, 'PATCH', `${site(env)}/lists/${id}/items/${itemId}/fields`, fields);
  if (!r.ok) throw new Error(`Updating item ${itemId} failed (${r.status}): ${JSON.stringify(r.data).slice(0, 300)}`);
}

const clean = (s, max = 120) => String(s ?? '').replace(/[<>]/g, '').trim().slice(0, max);
// Folder names use dashes for spaces ("477-Blue-Mounds-Trl"); the app shows them with spaces.
const words = (s) => clean(s).replace(/-+/g, ' ').replace(/\s+/g, ' ').trim();
const title = (client, siteName, jobNumber) => [client, siteName].filter(Boolean).join(' – ') || jobNumber;
const isOpenRequest = (j) => !j.JobNumber && (j.FolderStatus === 'Requested' || j.FolderStatus === 'Creating');
const requestsOf = (rows) => rows.filter(isOpenRequest)
  .sort((a, b) => a.Created.localeCompare(b.Created))
  .map((j) => ({ id: j.id, client: j.Client, site: j.SiteAddress, title: j.Title, status: j.FolderStatus, created: j.Created }));

async function sync(env, token, id, existing, body) {
  const jobs = Array.isArray(body.jobs) ? body.jobs.slice(0, 500) : [];
  const full = body.full === true;
  const byNumber = new Map(existing.filter((j) => j.JobNumber).map((j) => [j.JobNumber, j]));
  const seen = new Set();
  const added = [], claimed = [], renamed = [], archived = [], reactivated = [], skipped = [], invalid = [];

  for (const j of jobs) {
    const jobNumber = clean(j.jobNumber, 10);
    if (!JOB_RE.test(jobNumber)) { invalid.push(jobNumber || '(blank)'); continue; }
    if (seen.has(jobNumber)) continue;
    seen.add(jobNumber);
    const client = words(j.client);
    const siteName = words(j.site);
    const folder = clean(j.folder, 255);
    const row = byNumber.get(jobNumber);

    if (!row) {
      // A new folder. If the app asked for a job and the PC is making it right now, this is that job.
      const creating = existing.filter((x) => !x.JobNumber && x.FolderStatus === 'Creating');
      if (creating.length === 1) {
        const req = creating[0];
        const fields = { JobNumber: jobNumber, FolderStatus: 'Active', FolderNote: '' };
        if (folder) fields.FolderName = folder;
        await patch(env, token, id, req.id, fields);
        Object.assign(req, fields);
        byNumber.set(jobNumber, req);
        claimed.push(jobNumber);
        continue;
      }
      const fields = { Title: title(client, siteName, jobNumber), JobNumber: jobNumber, Client: client, SiteAddress: siteName, Stage: 'Lead', FolderStatus: 'Active' };
      if (folder) fields.FolderName = folder;
      const r = await graph(token, 'POST', `${site(env)}/lists/${id}/items`, { fields });
      if (!r.ok) throw new Error(`Adding ${jobNumber} failed (${r.status}): ${JSON.stringify(r.data).slice(0, 300)}`);
      const made = { id: String(r.data.id), JobNumber: jobNumber, ...fields };
      existing.push(made);
      byNumber.set(jobNumber, made);
      added.push(jobNumber);
      continue;
    }

    const fields = {};
    if (row.FolderStatus !== 'Active') {
      fields.FolderStatus = 'Active';
      if (row.FolderStatus === 'Archived') reactivated.push(jobNumber);
    }
    if (folder && row.FolderName !== folder) {
      fields.FolderName = folder;
      // Only a real rename changes the names; the first time a folder is seen just records it.
      if (row.FolderName) {
        fields.Client = client;
        fields.SiteAddress = siteName;
        fields.Title = title(client, siteName, jobNumber);
        renamed.push(jobNumber);
      }
    }
    if (Object.keys(fields).length) { await patch(env, token, id, row.id, fields); Object.assign(row, fields); }
    else skipped.push(jobNumber);
  }

  // Jobs whose folder has left 01_Active. Only on a full listing, and never when it came back empty.
  if (full && seen.size > 0) {
    for (const row of existing) {
      if (!JOB_RE.test(row.JobNumber) || seen.has(row.JobNumber) || row.FolderStatus === 'Archived') continue;
      await patch(env, token, id, row.id, { FolderStatus: 'Archived' });
      row.FolderStatus = 'Archived';
      archived.push(row.JobNumber);
    }
  }
  return { ok: true, added, claimed, renamed, archived, reactivated, skipped, invalid, requests: requestsOf(existing) };
}

async function act(env, token, id, existing, body) {
  const row = existing.find((j) => j.id === String(body.id || ''));
  if (!row) return json({ ok: false, error: 'No such request' }, 404);

  if (body.action === 'claim') {
    if (row.JobNumber || row.FolderStatus !== 'Requested') return json({ ok: false, error: `Request is ${row.FolderStatus || 'not open'}` }, 409);
    await patch(env, token, id, row.id, { FolderStatus: 'Creating', FolderNote: '' });
    return json({ ok: true, id: row.id, status: 'Creating' });
  }

  if (body.action === 'done') {
    const jobNumber = clean(body.jobNumber, 10);
    if (!JOB_RE.test(jobNumber)) return json({ ok: false, error: 'Bad job number' }, 400);
    const folder = clean(body.folder, 255);
    if (row.JobNumber && row.JobNumber !== jobNumber) return json({ ok: false, error: `Request already has ${row.JobNumber}` }, 409);
    const other = existing.find((j) => j.JobNumber === jobNumber && j.id !== row.id);
    if (other) {
      // The folder was made but listed on its own row. Keep both rows; say so on the request.
      await patch(env, token, id, row.id, { FolderStatus: 'Failed', FolderNote: `Folder made as ${jobNumber}, which is listed as its own job` });
      return json({ ok: false, error: `${jobNumber} is already on another row`, duplicateOf: other.id }, 409);
    }
    const fields = { JobNumber: jobNumber, FolderStatus: 'Active', FolderNote: '' };
    if (folder) fields.FolderName = folder;
    await patch(env, token, id, row.id, fields);
    return json({ ok: true, id: row.id, jobNumber });
  }

  if (body.action === 'fail') {
    if (row.JobNumber) return json({ ok: false, error: `Request already has ${row.JobNumber}` }, 409);
    await patch(env, token, id, row.id, { FolderStatus: 'Failed', FolderNote: clean(body.note, 250) || 'The PC could not make the folder' });
    return json({ ok: true, id: row.id, status: 'Failed' });
  }
  return json({ ok: false, error: 'Unknown action' }, 400);
}

export async function onRequest({ request, env }) {
  if (!authed(request, env)) return json({ ok: false, error: 'Missing or wrong key' }, 401);
  try {
    const token = await getToken(env);
    const id = await listId(env, token);
    const existing = await readJobs(env, token, id);

    if (request.method === 'GET') {
      if (new URL(request.url).searchParams.get('requests')) return json({ ok: true, requests: requestsOf(existing) });
      existing.sort((a, b) => b.JobNumber.localeCompare(a.JobNumber));
      return json({ ok: true, count: existing.length, jobs: existing, requests: requestsOf(existing) });
    }
    if (request.method !== 'POST') return json({ ok: false, error: 'Use GET or POST' }, 405);

    const body = await request.json().catch(() => ({}));
    if (body.action) return await act(env, token, id, existing, body);
    return json(await sync(env, token, id, existing, body));
  } catch (err) {
    return json({ ok: false, error: String(err.message || err) }, 500);
  }
}
