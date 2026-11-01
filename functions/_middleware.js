// basin.equora.institute — látogatottsági statisztika a szerveren (Plausible Events API), az Erdőfigyelő
// mintájára (forest: src/meres.js), 2026-11-01.
//
// A böngészőben mérőszkript nincs: a statisztika a lapkérésekből készül, a készülékre semmit sem ír, és onnan
// semmit sem olvas ki. A válasz után (waitUntil) a függvény elküldi a Plausible-nak a megnyitott lap címét, a
// hivatkozó oldalt, a böngésző azonosító sorát és az IP-cím álnevét. IPv4-nél az első három bájt marad
// (nagyjából városi szintű helymeghatározás), az utolsó a teljes cím napi titkos sóval képzett kivonatából jön;
// IPv6-nál az első 48 bit marad. A só a Pages-projekt titka (HASH_SALT); a nyilvános repóban nem szerepel.
//
// Kimarad: GPC- vagy DNT-jelzés, előtöltés, robotok és link-előnézetek. A _routes.json csak a HTML-lapokat
// engedi ide, így az adatfájlok, betűtípusok és képek kérése a függvényt el sem éri.
const PL_EVENT = 'https://plausible.io/api/event';
const PL_DOMAIN = 'basin.equora.institute';
const ROBOT_UA = /bot|crawl|spider|slurp|headless|lighthouse|pagespeed|preview|facebookexternalhit|embedly|whatsapp|telegram|discord|slack|curl|wget|python|httpx|go-http|java\/|okhttp|node-fetch|undici|axios|monitor|uptime|playwright|puppeteer/i;

function expandV6(ip) {
  const [a, b = ''] = ip.split('::');
  const head = a ? a.split(':') : [];
  const tail = ip.includes('::') ? (b ? b.split(':') : []) : [];
  const fill = ip.includes('::') ? Array(8 - head.length - tail.length).fill('0') : [];
  return [...head, ...fill, ...tail].slice(0, 8);
}

async function pseudoIp(ip, salt) {
  if (!ip || !salt) return '';
  const day = new Date().toISOString().slice(0, 10);
  const h = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${salt}|pl|${day}|${ip}`)));
  if (/^\d+\.\d+\.\d+\.\d+$/.test(ip)) { const q = ip.split('.'); return `${q[0]}.${q[1]}.${q[2]}.${h[0]}`; }
  if (ip.includes(':')) {
    const keep = expandV6(ip).slice(0, 3);
    const rest = Array.from({ length: 5 }, (_, i) => ((h[2 * i] << 8) | h[2 * i + 1]).toString(16));
    return [...keep, ...rest].join(':');
  }
  return '';
}

function kimarad(request) {
  const h = request.headers;
  const ua = h.get('user-agent') || '';
  if (!ua || ROBOT_UA.test(ua)) return 'robot';
  if (h.get('sec-gpc') === '1' || h.get('dnt') === '1') return 'jelzes';
  if (/prefetch|prerender/i.test(`${h.get('sec-purpose') || ''} ${h.get('purpose') || ''} ${h.get('x-moz') || ''}`)) return 'elotoltes';
  return '';
}

function tisztaUrl(u) {
  try { const x = new URL(u); x.hash = ''; return x.toString(); } catch (e) { return null; }
}

async function kuld(request, env, url) {
  try {
    const headers = { 'content-type': 'application/json', 'user-agent': request.headers.get('user-agent') || '' };
    const pip = await pseudoIp(request.headers.get('cf-connecting-ip') || '', env.HASH_SALT);
    if (pip) headers['x-forwarded-for'] = pip;
    const ref = request.headers.get('referer');
    const r = await fetch(PL_EVENT, {
      method: 'POST', headers,
      body: JSON.stringify({ name: 'pageview', domain: PL_DOMAIN, url: tisztaUrl(url), referrer: (ref && tisztaUrl(ref)) || null }),
    });
    if (!r.ok) console.error(JSON.stringify({ msg: 'pl_event', status: r.status }));
  } catch (e) {
    console.error(JSON.stringify({ msg: 'pl_event_failed', err: String(e) }));
  }
}

export async function onRequest(context) {
  const { request, env } = context;
  const res = await context.next();
  try {
    if (request.method === 'GET') {
      const dest = request.headers.get('sec-fetch-dest');
      const lap = dest ? ['document', 'iframe'].includes(dest) : /text\/html/.test(request.headers.get('accept') || '');
      const jo = res.status === 304 || (res.status === 200 && (res.headers.get('content-type') || '').startsWith('text/html'));
      if (lap && jo && !kimarad(request)) context.waitUntil(kuld(request, env, request.url));
    }
  } catch (e) { /* a statisztika hibája sosem akasztja meg a lapot */ }
  return res;
}
