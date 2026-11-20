// basin.equora.institute/motor/* → basin-motor.equora.institute/api/*   (2026-11-19)
//
// A mérce-nézet (merce.js) ugyanarról a címről kéri az adatot, amelyről a lap jön. Így a CSP connect-src 'self'
// marad, és a motor a látogató IP-címét sosem látja: a kérést ez a függvény továbbítja, a saját nevében.
// Csak olvasó GET, négy végpont, öt paraméter. A válasz a Cloudflare gyorsítótárában végpontonként 30–120
// másodpercig él.
const MOTOR = 'https://basin-motor.equora.institute/api/';
const VEGPONT = { meta: 30, allomasok: 120, allapot: 30, nezet: 60 };   // gyorsítótár, másodperc
const PARAM = new Set(['tsz', 'af', 't0', 't1', 'px']);
const IDOKORLAT_MS = 15000;

const valasz = (obj, status, extra = {}) => new Response(JSON.stringify(obj), {
  status,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store',
    'x-robots-tag': 'noindex', ...extra },
});

export async function onRequest({ request, params }) {
  if (request.method !== 'GET' && request.method !== 'HEAD') return valasz({ hiba: 'csak GET' }, 405, { allow: 'GET, HEAD' });
  const ut = [].concat(params.ut || []);
  const nev = ut.length === 1 ? ut[0] : '';
  if (!Object.hasOwn(VEGPONT, nev)) return valasz({ hiba: 'ismeretlen végpont' }, 404);

  const be = new URL(request.url);
  const ki = new URL(MOTOR + nev);
  for (const [k, v] of be.searchParams) {
    if (PARAM.has(k) && v.length <= 32 && /^[0-9A-Za-z:.\-+]*$/.test(v)) ki.searchParams.set(k, v);
  }

  let r;
  try {
    r = await fetch(ki, {
      method: request.method,
      headers: { accept: 'application/json', 'user-agent': 'basin.equora.institute merce-nezet' },
      signal: AbortSignal.timeout(IDOKORLAT_MS),
      cf: { cacheEverything: true, cacheTtlByStatus: { '200-299': VEGPONT[nev], '400-499': 10, '500-599': 0 } },
    });
  } catch (e) {
    return valasz({ hiba: 'a motor nem válaszolt', ok: String((e && e.name) || e) }, 504);
  }
  const h = new Headers();
  h.set('content-type', r.headers.get('content-type') || 'application/json; charset=utf-8');
  h.set('cache-control', r.ok ? `public, max-age=${VEGPONT[nev]}` : 'no-store');
  h.set('x-robots-tag', 'noindex');
  h.set('x-content-type-options', 'nosniff');
  return new Response(request.method === 'HEAD' ? null : r.body, { status: r.status, headers: h });
}
