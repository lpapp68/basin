// tesztmotor.mjs — a /motor/* továbbító (functions/motor/[[ut]].js) futásidejű ellenőrzése, álkérésekkel.
// Futtatás: node tesztmotor.mjs   (a publikal.sh minden kitétel előtt lefuttatja)
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const forras = readFileSync(new URL('./functions/motor/[[ut]].js', import.meta.url), 'utf8');
const { onRequest } = await import('data:text/javascript;base64,' + Buffer.from(forras).toString('base64'));

const hivasok = [];
globalThis.fetch = async (url, opt) => {
  hivasok.push({ url: String(url), opt });
  return new Response('{"ok":true}', { status: 200, headers: { 'content-type': 'application/json' } });
};
const keres = (ut, query = '', method = 'GET') => onRequest({
  request: new Request('https://basin.equora.institute/motor/' + ut + query, { method }),
  params: { ut: ut.split('/').filter(Boolean) },
});

let r = await keres('nezet', '?tsz=1026&af=87&t0=2026-11-12&t1=1795104000&px=800&rossz=1&tsz2=x');
assert.equal(r.status, 200);
assert.equal(r.headers.get('cache-control'), 'public, max-age=60');
assert.equal(r.headers.get('x-robots-tag'), 'noindex');
const u = new URL(hivasok.at(-1).url);
assert.equal(u.origin + u.pathname, 'https://basin-motor.equora.institute/api/nezet');
assert.deepEqual([...u.searchParams.keys()].sort(), ['af', 'px', 't0', 't1', 'tsz']);
assert.ok(!('cf-connecting-ip' in (hivasok.at(-1).opt.headers || {})), 'a látogató IP-je nem megy tovább');

r = await keres('nezet', '?tsz=1026%27%3B--');
assert.ok(!new URL(hivasok.at(-1).url).searchParams.has('tsz'), 'a gyanús paraméter kimarad');

const n = hivasok.length;
assert.equal((await keres('admin/feed')).status, 404);
assert.equal((await keres('valami')).status, 404);
assert.equal((await keres('allapot', '', 'POST')).status, 405);
assert.equal(hivasok.length, n, 'tiltott kérés a motorig nem jut el');

globalThis.fetch = async () => { throw new DOMException('időtúllépés', 'TimeoutError'); };
assert.equal((await keres('meta')).status, 504);

console.log('tesztmotor: a /motor továbbító rendben (9 ellenőrzés)');
