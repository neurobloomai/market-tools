/**
 * Cloudflare Worker — newsletter signup proxy
 * Keeps RESEND_API_KEY + RESEND_AUDIENCE_ID server-side.
 *
 * Deploy:
 *   npm install -g wrangler
 *   wrangler login
 *   wrangler secret put RESEND_API_KEY        # paste key
 *   wrangler secret put RESEND_AUDIENCE_ID    # paste audience ID from Resend dashboard
 *   wrangler deploy
 */

const ALLOWED_ORIGIN = 'https://neurobloom.ai';

function cors(origin) {
  const allowed = origin === ALLOWED_ORIGIN || origin === 'https://neurobloomai.github.io';
  return {
    'Access-Control-Allow-Origin':  allowed ? origin : ALLOWED_ORIGIN,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...cors(origin) },
  });
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors(origin) });
    }

    if (request.method !== 'POST') {
      return json({ error: 'Method not allowed' }, 405, origin);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: 'Invalid JSON' }, 400, origin);
    }

    const email = (body.email || '').trim().toLowerCase();
    if (!email || !isValidEmail(email)) {
      return json({ error: 'Valid email required' }, 400, origin);
    }

    const resp = await fetch(
      `https://api.resend.com/audiences/${env.RESEND_AUDIENCE_ID}/contacts`,
      {
        method:  'POST',
        headers: {
          Authorization:  `Bearer ${env.RESEND_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, unsubscribed: false }),
      }
    );

    if (resp.ok) {
      return json({ ok: true }, 200, origin);
    }

    const err = await resp.json().catch(() => ({}));
    // 422 = already subscribed — treat as success
    if (resp.status === 422) {
      return json({ ok: true }, 200, origin);
    }
    console.error('Resend error', resp.status, err);
    return json({ error: 'Subscription failed — try again' }, 502, origin);
  },
};
