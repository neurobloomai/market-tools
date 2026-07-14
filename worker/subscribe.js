/**
 * Cloudflare Worker — newsletter signup
 * Appends submitted email to subscribers.json in the GitHub repo.
 *
 * Secrets (set via wrangler secret put):
 *   GITHUB_TOKEN   — PAT with repo Contents write scope
 *
 * Deploy:
 *   wrangler secret put GITHUB_TOKEN
 *   wrangler deploy
 */

const REPO    = 'neurobloomai/market-tools';
const BRANCH  = 'main';
const FILE    = 'subscribers.json';
const GH_API  = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

const ALLOWED_ORIGINS = [
  'https://neurobloom.ai',
  'https://neurobloomai.github.io',
];

function corsHeaders(origin) {
  const allowed = ALLOWED_ORIGINS.includes(origin);
  return {
    'Access-Control-Allow-Origin':  allowed ? origin : ALLOWED_ORIGINS[0],
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function respond(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
  });
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

async function getSubscribers(token) {
  const resp = await fetch(GH_API, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
    },
  });
  if (!resp.ok) throw new Error(`GitHub GET failed: ${resp.status}`);
  const data    = await resp.json();
  const decoded = atob(data.content.replace(/\n/g, ''));
  return { list: JSON.parse(decoded), sha: data.sha };
}

async function saveSubscribers(token, list, sha) {
  const content = btoa(JSON.stringify(list, null, 2) + '\n');
  const resp    = await fetch(GH_API, {
    method: 'PUT',
    headers: {
      Authorization:  `Bearer ${token}`,
      Accept:         'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: `subscribers: add via web form`,
      content,
      sha,
      branch: BRANCH,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(`GitHub PUT failed: ${resp.status} ${JSON.stringify(err)}`);
  }
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    if (request.method !== 'POST') {
      return respond({ error: 'Method not allowed' }, 405, origin);
    }

    let body;
    try { body = await request.json(); }
    catch { return respond({ error: 'Invalid JSON' }, 400, origin); }

    const email = (body.email || '').trim().toLowerCase();
    if (!email || !isValidEmail(email)) {
      return respond({ error: 'Valid email required' }, 400, origin);
    }

    try {
      const { list, sha } = await getSubscribers(env.GITHUB_TOKEN);
      if (list.includes(email)) {
        return respond({ ok: true }, 200, origin);  // already subscribed
      }
      list.push(email);
      await saveSubscribers(env.GITHUB_TOKEN, list, sha);
      return respond({ ok: true }, 200, origin);
    } catch (e) {
      console.error(e.message);
      return respond({ error: 'Could not save — try again' }, 502, origin);
    }
  },
};
