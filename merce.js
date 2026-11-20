// merce.js — egy mérce közelről (2026-11-19).
//
// Mért adat, saját fejlesztésű állapotbecslés és 90%-os sáv, a nézethez illő bontásban. Az adat a lap saját
// címéről jön (/motor/*, functions/motor/[[ut]].js), amely a basin-motor nyilvános API-ját továbbítja.
//
// A motor két dolgot ad: az állapotot (érték, sebesség, kovariancia, a modell q-ja) és a granularitás-motor
// választotta bontást. A legutolsó mérés és a „most” közötti szakaszt a böngésző számolja ugyanazzal a
// képlettel, amelyet a motor közöl (/motor/allapot → modell.keplet), ezért a „most” érték másodpercenként lép.
// Vízhozamnál Q(τ) = Q_ref + m·(szint(τ) − h_ref), σ_Q = m·σ_szint, ahol m a vízhozamgörbe helyi meredeksége.
(() => {
  'use strict';
  const gyoker = document.getElementById('mnezet');
  if (!gyoker || !window.fetch || !window.Intl) return;

  const Z90 = 1.6449;
  const NS = 'http://www.w3.org/2000/svg';
  const ABLAKOK = [[21600, '6 óra'], [86400, '1 nap'], [604800, '7 nap'], [2592000, '30 nap']];
  const AF = {
    68: { nev: 'vízállás', me: 'cm', seb: 'cm/óra' },
    87: { nev: 'vízhozam', me: 'm³/s', seb: 'm³/s óránként' },
  };
  const SZINT = { ora: 'órás vödrök', '6ora': '6 órás vödrök', nap: 'napi vödrök', het: 'heti vödrök', honap: 'havi vödrök' };
  const UTEM = { 300: '5 percenként', 600: '10 percenként', 900: 'negyedóránként', 1800: 'félóránként', 3600: 'óránként',
    7200: '2 óránként', 10800: '3 óránként', 21600: '6 óránként', 43200: '12 óránként', 86400: 'naponta' };
  const csendes = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };

  const all = { tsz: 1026, af: 68, ablak: 86400, lista: {}, van87: new Set(), allapot: null, nezet: null, hiba: null,
    betoltve: 0, skala: null };

  // ── segédek ────────────────────────────────────────────────────────────
  const most = () => Date.now() / 1000;
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const sv = (tag, attr, szulo) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attr) e.setAttribute(k, attr[k]);
    if (szulo) szulo.appendChild(e);
    return e;
  };
  const fmt = (x, d = 0) => (Number.isFinite(x)
    ? x.toLocaleString('hu-HU', { minimumFractionDigits: d, maximumFractionDigits: d }).replace('-', '−') : '–');
  const elojel = (x, d) => (x > 0 ? '+' : '') + fmt(x, d);
  const egyseg = (s) => (s > 0 ? Math.pow(10, Math.round(Math.log10(2 * s))) : 1);
  const tizedes = (u) => Math.max(0, -Math.round(Math.log10(u)));
  const kerekit = (x, u) => Math.round(x / u) * u;
  const BP = new Intl.DateTimeFormat('hu-HU', { timeZone: 'Europe/Budapest', hour: '2-digit', minute: '2-digit' });
  const BPS = new Intl.DateTimeFormat('hu-HU', { timeZone: 'Europe/Budapest', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const BPN = new Intl.DateTimeFormat('hu-HU', { timeZone: 'Europe/Budapest', month: 'short', day: 'numeric' });
  const ido = (t) => BP.format(new Date(t * 1000));
  const idoMp = (t) => BPS.format(new Date(t * 1000));
  const nap = (t) => BPN.format(new Date(t * 1000));
  const RESZ = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Budapest', hourCycle: 'h23', year: 'numeric',
    month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric' });
  function eltolas(t) {           // Budapest helyi ideje − UTC, másodpercben
    const p = {};
    for (const x of RESZ.formatToParts(new Date(Math.floor(t) * 1000))) p[x.type] = +x.value;
    return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) / 1000 - Math.floor(t);
  }
  function kor(s) {
    s = Math.max(0, Math.floor(s));
    if (s < 60) return `${s} másodperce`;
    if (s < 3600) return `${Math.floor(s / 60)} perc ${s % 60} másodperce`;
    const o = Math.floor(s / 3600);
    return o < 48 ? `${o} óra ${Math.floor((s % 3600) / 60)} perce` : `${Math.floor(o / 24)} napja`;
  }
  function tartam(s) {
    if (!(s > 0) || !Number.isFinite(s)) return '–';
    if (s < 90) return `${Math.round(s)} másodperc`;
    if (s < 5400) return `${Math.round(s / 60)} perc`;
    if (s < 172800) return `${fmt(s / 3600, s < 36000 ? 1 : 0)} óra`;
    return `${fmt(s / 86400, 1)} nap`;
  }
  const lepesKerek = (r, n) => {
    const x = r / n, p = Math.pow(10, Math.floor(Math.log10(x))), m = x / p;
    return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
  };

  // Az állapot továbbléptetése τ időpontra: a motor közölt képlete (állandó sebességű modell).
  function elore(a, t) {
    if (!a || !a.allapot || !a.modell) return null;
    const [x0, x1] = a.allapot.x, P = a.allapot.P, q = a.modell.q;
    const dt = Math.max(0, (t - a.allapot.t) / 3600);
    const x = x0 + dt * x1;
    const s = Math.sqrt(Math.max(0, P[0][0] + 2 * dt * P[0][1] + dt * dt * P[1][1] + (q * dt * dt * dt) / 3));
    const sv1 = Math.sqrt(Math.max(0, P[1][1] + q * dt));
    const g = a.szarmaztatott;
    if (g) return { x: g.q_ref + g.meredekseg * (x - g.h_ref), s: g.meredekseg * s, v: g.meredekseg * x1, sv: g.meredekseg * sv1 };
    return { x, s, v: x1, sv: sv1 };
  }

  async function kerd(ut, p) {
    const u = new URL('/motor/' + ut, location.origin);
    for (const k in p) u.searchParams.set(k, p[k]);
    const r = await fetch(u, { headers: { accept: 'application/json' } });
    if (!r.ok) { const e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
    return r.json();
  }

  // ── felület ────────────────────────────────────────────────────────────
  gyoker.textContent = '';
  const fej = el('div', 'mn-fej');
  const cim = el('div', 'mn-cim');
  const cimNev = el('b', 'mn-nev', 'Budapest');
  cimNev.setAttribute('aria-live', 'polite');
  const cimHely = el('span', 'mn-hely', '');
  cim.append(el('span', 'u', 'Egy mérce közelről'), cimNev, cimHely);
  const keres = el('label', 'mn-keres');
  const inp = el('input');
  Object.assign(inp, { type: 'search', id: 'mn-kereso', placeholder: 'pl. Szeged, Tisza', autocomplete: 'off' });
  inp.setAttribute('list', 'mn-lista');
  const dl = el('datalist'); dl.id = 'mn-lista';
  const keresU = el('span', 'u', 'Mérce keresése');
  keres.append(keresU, inp, dl);
  fej.append(cim, keres);

  function gombsor(felirat, elemek, valt) {
    const d = el('div', 'mn-gombok');
    d.setAttribute('role', 'group'); d.setAttribute('aria-label', felirat);
    d.append(el('span', 'u', felirat));
    const gombok = elemek.map(([v, t]) => {
      const b = el('button', null, t); b.type = 'button'; b.dataset.v = v;
      b.addEventListener('click', () => { if (!b.disabled) valt(+v); });
      d.append(b); return b;
    });
    return { d, gombok, jelol: (v) => gombok.forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.v === v))) };
  }
  const afSor = gombsor('Mennyiség', [[68, 'vízállás'], [87, 'vízhozam']], (v) => { all.af = v; horgony(); tolt(true); });
  const abSor = gombsor('Időablak', ABLAKOK, (v) => { all.ablak = v; horgony(); tolt(true); });
  const vez = el('div', 'mn-vez'); vez.append(afSor.d, abSor.d);

  function doboz(cls, felirat) {
    const d = el('div', cls), v = el('div', 'v', '–'), m = el('div', 'm', '');
    d.append(el('span', 'u', felirat), v, m);
    return { d, v, m };
  }
  const kMost = doboz('most', 'Most · becslés');
  const kMert = doboz('mert', 'Utolsó mérés');
  const kSeb = doboz('seb', 'Változás · becslés');
  const ki = el('div', 'mn-ki'); ki.append(kMost.d, kMert.d, kSeb.d);

  const graf = el('div', 'mn-graf');
  const mutato = el('div', 'mn-mutato', '');
  const jel = el('div', 'mn-jel');
  function jelmagyarazat(nyers) {
    jel.innerHTML = nyers
      ? '<span><i class="mert"></i>mért érték, minden mérés</span>' +
        '<span><i class="farok"></i>becslés a legutolsó mérés óta, 90%-os sávval</span>'
      : '<span><i class="mert"></i>mért érték, vödrönkénti átlag</span>' +
        '<span><i class="burok"></i>a vödörben mért legkisebb és legnagyobb érték</span>' +
        '<span><i class="sav"></i>90%-os sáv</span>' +
        '<span><i class="farok"></i>becslés a legutolsó mérés óta</span>';
  }
  jelmagyarazat(true);
  const bontas = el('p', 'mn-bontas', '');
  const modszer = el('p', 'mn-modszer', '');
  const forras = el('p', 'mn-forras',
    'Forrás: OVF Országos Vízjelző Szolgálat, data.vizugy.hu — operatív, korrekció nélküli adat. A becslést az ' +
    'EQUORA Institute basin-motorja számolja negyedóránként; a böngésző a legutolsó állapotból lépteti tovább.');
  gyoker.append(fej, vez, ki, graf, mutato, jel, bontas, modszer, forras);
  const ALAP_MUTATO = 'Az egérrel vagy ujjal a grafikonon bármely időpont értéke leolvasható.';
  mutato.textContent = ALAP_MUTATO;

  // ── fejléc, gombok, leolvasás ──────────────────────────────────────────
  function frissFej() {
    const a = (all.lista[68] || []).find((x) => x.tsz === all.tsz) || (all.lista[87] || []).find((x) => x.tsz === all.tsz);
    const nev = (all.allapot && all.allapot.nev) || (a && a.nev) || `#${all.tsz}`;
    cimNev.textContent = nev;
    const folyo = (a && a.folyo) || (all.allapot && all.allapot.folyo) || '';
    cimHely.textContent = [folyo, a && Number.isFinite(a.fkm) ? `${fmt(a.fkm, 1)} fkm` : '', a && a.telepules && a.telepules !== nev ? a.telepules : '']
      .filter(Boolean).join(' · ');
    const van87 = all.van87.has(all.tsz);
    afSor.gombok[1].disabled = !van87;
    afSor.gombok[1].title = van87 ? '' : 'ezen a mércén az OVF vízállást közöl, vízhozamot nem';
    afSor.jelol(all.af); abSor.jelol(all.ablak);
    document.querySelectorAll('#mercesor .merce[data-tsz]').forEach((b) => b.classList.toggle('valasztott', +b.dataset.tsz === all.tsz));
  }

  function frissKi() {
    const a = all.allapot, t = most(), f = AF[all.af];
    const e = elore(a, t);
    if (e) {
      const u = egyseg(e.s), d = tizedes(u);
      kMost.v.textContent = `${fmt(kerekit(e.x, u), d)} ${f.me}`;
      kMost.m.textContent = `90%-os sáv: ± ${fmt(Math.max(u, Math.ceil((Z90 * e.s) / u) * u), d)} ${f.me} · ${idoMp(t)}`;
      // a sebességnél egy jeggyel finomabb egység: a ± mellette áll, így a jegy jelentése látható
      const us = egyseg(e.sv) / 10, ds = Math.min(2, tizedes(us));
      kSeb.v.textContent = `${elojel(kerekit(e.v, us), ds)} ${f.seb}`;
      kSeb.m.textContent = `90%-os sáv: ± ${fmt(Math.max(us, Math.ceil((Z90 * e.sv) / us) * us), ds)} ${f.seb} · a legutolsó mérésig tanult sebesség`;
    } else {
      kMost.v.textContent = '–';
      kMost.m.textContent = a ? 'a becslés az első mérések után indul' : '';
      kSeb.v.textContent = '–'; kSeb.m.textContent = '';
    }
    const um = a && a.utolso_meres;
    if (um && Number.isFinite(um.ertek)) {
      kMert.v.textContent = `${fmt(um.ertek, um.ertek % 1 ? 1 : 0)} ${f.me}`;
      kMert.m.textContent = `${t - um.t > 86400 ? nap(um.t) + ' ' : ''}${ido(um.t)} · ${kor(t - um.t)}`;
    } else { kMert.v.textContent = '–'; kMert.m.textContent = ''; }
  }

  function szovegek() {
    const n = all.nezet, a = all.allapot, f = AF[all.af];
    bontas.textContent = '';
    if (n && n.granularitas) {
      const g = n.granularitas;
      const sz = g.szint === 'nyers'
        ? `minden egyes mérés (a mérce ${UTEM[g.nativ_lepes_s] || tartam(g.nativ_lepes_s) + 'ként'} mér)`
        : SZINT[g.szint] || g.szint;
      const px = (n.ablak && n.ablak.px) || 800;
      const sig = g.tipikus_sigma, v = g.tipikus_sebesseg_ora;
      const ds = tizedes(egyseg(sig || 1)) + 1;
      bontas.append(el('b', null, 'Bontás: ' + sz + '. '));
      let s = `Két korlát dönt. A képernyő: ${px} képpont szélességen legfeljebb ${Math.floor(px / 2)} pont, ` +
        `ez ezen az időablakon ${tartam(g.kepponthatar_s)} lépés. A változás üteme: Δt* = σ/|v| = ${tartam(g.dt_csillag_s)}, ` +
        `ennyi idő alatt mozdul el a ${f.nev} egy bizonytalanságnyit` +
        (sig > 0 && v > 0 ? ` (σ ≈ ${fmt(sig, ds)} ${f.me}, |v| ≈ ${fmt(v, ds)} ${f.seb})` : '') +
        '. A durvább korlát érvényes, a szabványos lépések közül a legközelebbire kerekítve.';
      if (g.modell_finomabbat_indokol) {
        s += ` A ${f.nev} most gyorsabban változik, mint ahogy a mérce mér: két mérés között a becslés lép tovább, ` +
          'ezért frissül a „most” érték másodpercenként.';
      }
      const elso = n.pontok && n.pontok.length ? n.pontok[0].t : null;
      if (elso && n.ablak && elso > n.ablak.t0 + 0.1 * (n.ablak.t1 - n.ablak.t0)) {
        s += ` A motor adatsora ${nap(elso)} óta gyűlik, ezért az ablak eleje üres.`;
      }
      bontas.append(document.createTextNode(s));
    }
    let m = 'Saját fejlesztésű állapotbecslés: minden új mérés frissíti a mérce becsült értékét és változási sebességét; ' +
      'két mérés között a becslés a sebességgel lép tovább, és a bizonytalansága az eltelt idővel nő. A 90%-os sáv ezt ' +
      'a bizonytalanságot mutatja: a modell szerint 10 esetből 9-ben ezen belül van a valódi érték. A vízállás-sávot egy ' +
      'előre rögzített teszt 2026. december 3-ig ellenőrzi az összes mércén.';
    if (all.af === 87 && a && a.szarmaztatott) {
      m += ` Az operatív vízhozam a vízállásból, a mérce vízhozamgörbéjével adódik, ezért a bizonytalansága a vízállásé, ` +
        `szorozva a görbe helyi meredekségével: itt ${fmt(a.szarmaztatott.meredekseg, 1)} m³/s minden centiméterre ` +
        `(az elmúlt 14 nap ${a.szarmaztatott.par} órás párjából, mediánmeredekséggel). Ez a vízhozam-sáv a vízállás-sávból ` +
        'származik; saját ellenőrző tesztje a későbbi lépések egyike.';
    }
    modszer.textContent = m;
  }

  // ── grafikon ───────────────────────────────────────────────────────────
  function szakaszok(pontok, rés) {          // [[t, ...], ...] → hézagoknál szétvágva
    const ki = []; let cs = [];
    for (const p of pontok) {
      if (cs.length && p[0] - cs[cs.length - 1][0] > rés) { ki.push(cs); cs = []; }
      cs.push(p);
    }
    if (cs.length) ki.push(cs);
    return ki;
  }

  function rajzol() {
    graf.textContent = ''; all.skala = null;
    const n = all.nezet;
    if (!n) { graf.append(el('p', 'mn-uzenet', all.hiba || 'Betöltés…')); return; }
    const W = Math.max(280, Math.min(1400, Math.round(graf.clientWidth || 800)));
    const H = W < 520 ? 210 : 270;
    const M = { b: 52, j: 14, f: 14, l: 24 };
    const t1 = most(), t0 = t1 - all.ablak, tMax = t1 + all.ablak * 0.015;
    const g = n.granularitas, nyers = g.szint === 'nyers';
    jelmagyarazat(nyers);
    const lepes = nyers ? g.nativ_lepes_s || 900 : g.lepes_s || 3600;
    const vonal = [], burok = [], sav = [], ys = [];
    for (const p of n.pontok || []) {
      if (nyers) {
        if (p.t < t0 || p.t > t1 || !Number.isFinite(p.ertek)) continue;
        vonal.push([p.t, p.ertek, p]); ys.push(p.ertek); continue;
      }
      const tk = p.t + lepes / 2;
      if (tk < t0 || p.t > t1 || !Number.isFinite(p.atlag)) continue;
      vonal.push([tk, p.atlag, p]); ys.push(p.atlag);
      if (Number.isFinite(p.min) && Number.isFinite(p.max)) { burok.push([tk, p.min, p.max]); ys.push(p.min, p.max); }
      const k = Number.isFinite(p.becsles) ? p.becsles : p.atlag;
      if (p.sigma > 0) { sav.push([tk, k - Z90 * p.sigma, k + Z90 * p.sigma]); ys.push(k - Z90 * p.sigma, k + Z90 * p.sigma); }
    }
    const a = all.allapot;
    const ts = a && a.allapot ? Math.max(a.allapot.t, t0) : null;
    const eMost = elore(a, t1);
    if (eMost) ys.push(eMost.x, elore(a, ts).x);
    if (!ys.length) { graf.append(el('p', 'mn-uzenet', 'Ebben az időablakban ennél a mércénél nincs mérés.')); return; }
    let lo = Math.min(...ys), hi = Math.max(...ys);
    if (eMost) {                              // a farok sávja legfeljebb a tartomány felével tágíthat
      const r = Math.max(hi - lo, 1e-9);
      lo = Math.min(lo, Math.max(eMost.x - Z90 * eMost.s, lo - r / 2));
      hi = Math.max(hi, Math.min(eMost.x + Z90 * eMost.s, hi + r / 2));
    }
    if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    const x = (t) => M.b + ((t - t0) / (tMax - t0)) * (W - M.b - M.j);
    const y = (v) => M.f + ((hi - v) / (hi - lo)) * (H - M.f - M.l);
    const f = AF[all.af];

    const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label':
      `${cimNev.textContent}, ${f.nev} az elmúlt ${{ 21600: '6 órában', 86400: '1 napban', 604800: '7 napban', 2592000: '30 napban' }[all.ablak]}` });
    const defs = sv('defs', {}, svg);
    const klip = sv('clipPath', { id: 'mn-klip' }, defs);
    sv('rect', { x: M.b, y: M.f, width: W - M.b - M.j, height: H - M.f - M.l }, klip);

    // rács és tengelyek
    const racs = sv('g', { class: 'racs' }, svg);
    const ly = lepesKerek(hi - lo, H < 240 ? 4 : 5), dy = Math.max(0, tizedes(ly));
    for (let v = Math.ceil(lo / ly) * ly; v <= hi; v += ly) {
      sv('line', { x1: M.b, x2: W - M.j, y1: y(v), y2: y(v) }, racs);
      sv('text', { x: M.b - 6, y: y(v) + 3.5, 'text-anchor': 'end' }, svg).textContent = fmt(v, dy);
    }
    sv('text', { x: 2, y: M.f - 4 }, svg).textContent = f.me;
    const lx = { 21600: 3600, 86400: W < 520 ? 21600 : 10800, 604800: 86400, 2592000: W < 520 ? 7 * 86400 : 5 * 86400 }[all.ablak];
    const off = eltolas(t1);
    for (let t = Math.ceil((t0 + off) / lx) * lx - off; t <= t1; t += lx) {
      sv('line', { x1: x(t), x2: x(t), y1: M.f, y2: H - M.l }, racs);
      const ejfel = ((t + off) % 86400 + 86400) % 86400 === 0;
      sv('text', { x: x(t), y: H - 7, 'text-anchor': 'middle' }, svg).textContent = lx >= 86400 || (ejfel && all.ablak > 21600) ? nap(t) : ido(t);
    }
    sv('line', { class: 'tengely', x1: M.b, x2: W - M.j, y1: H - M.l, y2: H - M.l }, svg);

    const rajz = sv('g', { 'clip-path': 'url(#mn-klip)' }, svg);
    const res = nyers ? Math.max(3 * lepes, 3 * 3600) : 2.5 * lepes;
    for (const cs of szakaszok(burok, res)) {
      sv('polygon', { class: 'mn-burok', points: cs.map((p) => `${x(p[0])},${y(p[2])}`).concat(cs.slice().reverse().map((p) => `${x(p[0])},${y(p[1])}`)).join(' ') }, rajz);
    }
    for (const cs of szakaszok(sav, res)) {
      sv('polygon', { class: 'mn-sav', points: cs.map((p) => `${x(p[0])},${y(p[2])}`).concat(cs.slice().reverse().map((p) => `${x(p[0])},${y(p[1])}`)).join(' ') }, rajz);
    }
    for (const cs of szakaszok(vonal, res)) {
      if (cs.length === 1) sv('circle', { class: 'mn-pont', cx: x(cs[0][0]), cy: y(cs[0][1]), r: 2 }, rajz);
      else sv('polyline', { class: 'mn-vonal', points: cs.map((p) => `${x(p[0])},${y(p[1])}`).join(' ') }, rajz);
    }
    if (nyers && vonal.length <= 160) for (const p of vonal) sv('circle', { class: 'mn-pont', cx: x(p[0]), cy: y(p[1]), r: 1.8 }, rajz);
    const um = a && a.utolso_meres;
    if (um && um.t >= t0 && Number.isFinite(um.ertek)) sv('circle', { class: 'mn-utolso', cx: x(um.t), cy: y(um.ertek), r: 3.6 }, rajz);

    const farok = sv('g', {}, rajz);
    const mutVonal = sv('line', { class: 'mn-mutato-vonal', x1: M.b, x2: M.b, y1: M.f, y2: H - M.l, visibility: 'hidden' }, svg);
    graf.append(svg);
    all.skala = { x, y, t0, tMax, M, W, H, farok, ts, vonal, burok, sav, nyers, lepes, svg, mutVonal };
    farokRajz();

    const olvas = (ev) => {
      const s = all.skala; if (!s) return;
      const r = svg.getBoundingClientRect();
      const tx = s.t0 + (((ev.clientX - r.left) * (s.W / r.width) - s.M.b) / (s.W - s.M.b - s.M.j)) * (s.tMax - s.t0);
      mutatoIr(tx);
    };
    svg.addEventListener('pointermove', olvas);
    svg.addEventListener('pointerdown', olvas);
    svg.addEventListener('pointerleave', () => { mutato.textContent = ALAP_MUTATO; mutVonal.setAttribute('visibility', 'hidden'); });
  }

  function farokRajz() {
    const s = all.skala, a = all.allapot;
    if (!s) return;
    s.farok.textContent = '';
    const t = Math.min(most(), s.tMax);
    if (!a || !a.allapot || !a.modell || s.ts == null || s.ts >= t) return;
    const N = 40, pp = [];
    for (let i = 0; i <= N; i++) { const tt = s.ts + ((t - s.ts) * i) / N; const e = elore(a, tt); pp.push([tt, e.x, e.s]); }
    sv('polygon', { class: 'mn-farok-sav', points: pp.map((p) => `${s.x(p[0])},${s.y(p[1] + Z90 * p[2])}`)
      .concat(pp.slice().reverse().map((p) => `${s.x(p[0])},${s.y(p[1] - Z90 * p[2])}`)).join(' ') }, s.farok);
    sv('polyline', { class: 'mn-farok', points: pp.map((p) => `${s.x(p[0])},${s.y(p[1])}`).join(' ') }, s.farok);
    sv('line', { class: 'mn-most-vonal', x1: s.x(t), x2: s.x(t), y1: s.M.f, y2: s.H - s.M.l }, s.farok);
    const v = pp[pp.length - 1];
    sv('circle', { class: 'mn-most-pont', cx: s.x(t), cy: s.y(v[1]), r: 4 }, s.farok);
  }

  function mutatoIr(tx) {
    const s = all.skala, f = AF[all.af];
    if (!s) return;
    const a = all.allapot, tMost = most();
    let szoveg = '', tPont = null;
    if (a && a.allapot && a.modell && s.ts != null && tx >= s.ts && tx <= tMost + 60) {
      const t = Math.min(tx, tMost), e = elore(a, t), u = egyseg(e.s), d = tizedes(u);
      tPont = t;
      szoveg = `${nap(t)} ${ido(t)} · becslés ${fmt(kerekit(e.x, u), d)} ${f.me}, 90%-os sáv ± ${fmt(Math.max(u, Math.ceil((Z90 * e.s) / u) * u), d)} ${f.me}`;
    } else if (s.vonal.length) {
      let lo = 0, hi = s.vonal.length - 1;
      while (hi - lo > 1) { const k = (lo + hi) >> 1; if (s.vonal[k][0] < tx) lo = k; else hi = k; }
      const q = Math.abs(s.vonal[lo][0] - tx) <= Math.abs(s.vonal[hi][0] - tx) ? s.vonal[lo] : s.vonal[hi];
      const p = q[2]; tPont = q[0];
      const d = q[1] % 1 && Math.abs(q[1]) < 100 ? 1 : 0;
      if (s.nyers) szoveg = `${nap(p.t)} ${ido(p.t)} · mérés ${fmt(p.ertek, p.ertek % 1 ? 1 : 0)} ${f.me}`;
      else {
        szoveg = `${nap(p.t)} ${ido(p.t)}–${ido(p.t + s.lepes)} · átlag ${fmt(p.atlag, d)} ${f.me}` +
          ` (legkisebb ${fmt(p.min, d)}, legnagyobb ${fmt(p.max, d)}; ${p.n} mérés)`;
        if (p.sigma > 0) { const u = egyseg(p.sigma); szoveg += ` · 90%-os sáv ± ${fmt(Math.max(u, Math.ceil((Z90 * p.sigma) / u) * u), tizedes(u))}`; }
      }
    }
    if (!szoveg) return;
    mutato.textContent = szoveg;
    s.mutVonal.setAttribute('x1', s.x(tPont)); s.mutVonal.setAttribute('x2', s.x(tPont));
    s.mutVonal.setAttribute('visibility', 'visible');
  }

  // ── adat ───────────────────────────────────────────────────────────────
  let sorszam = 0;
  async function tolt(uj) {
    const sajat = ++sorszam;
    if (uj) { all.nezet = null; all.allapot = null; all.hiba = null; frissFej(); rajzol(); frissKi(); szovegek(); }
    const t1 = Math.ceil(most() / 60) * 60;
    const px = Math.max(200, Math.min(1400, Math.round(graf.clientWidth || 800)));
    try {
      const [a, n] = await Promise.all([
        kerd('allapot', { tsz: all.tsz, af: all.af }),
        kerd('nezet', { tsz: all.tsz, af: all.af, t0: t1 - all.ablak, t1, px }),
      ]);
      if (sajat !== sorszam) return;
      Object.assign(all, { allapot: a, nezet: n, hiba: null, betoltve: most() });
    } catch (e) {
      if (sajat !== sorszam) return;
      all.hiba = e.status === 404
        ? `Ehhez a mércéhez a motorban ${AF[all.af].nev}-sorozat még nem gyűlt.`
        : 'Az adat most késik; a lap egy perc múlva újra kéri.';
      if (!all.nezet) all.betoltve = 0;
    }
    frissFej(); rajzol(); frissKi(); szovegek();
  }

  function valaszt(tsz, gorget) {
    if (!Number.isInteger(tsz)) return;
    all.tsz = tsz;
    if (all.af === 87 && all.van87.size && !all.van87.has(tsz)) all.af = 68;
    horgony(); tolt(true);
    if (gorget) gyoker.scrollIntoView({ behavior: csendes.matches ? 'auto' : 'smooth', block: 'start' });
  }

  function horgony() {
    try { history.replaceState(null, '', `#merce=${all.tsz}${all.af === 87 ? '&af=87' : ''}${all.ablak !== 86400 ? '&ablak=' + all.ablak : ''}`); } catch (e) { /* nem baj */ }
  }

  const nevTsz = new Map();
  // Pontos találat a listából; beírt szövegnél a legrövidebb név, amely tartalmazza (pl. „mohács” → „Duna Mohács”).
  inp.addEventListener('change', () => {
    const be = inp.value.trim();
    let tsz = nevTsz.get(be);
    if (!tsz && be.length >= 3) {
      const k = be.toLocaleLowerCase('hu');
      const jo = [...nevTsz.keys()].filter((c) => c.toLocaleLowerCase('hu').includes(k)).sort((a, b) => a.length - b.length);
      if (jo.length) tsz = nevTsz.get(jo[0]);
    }
    if (tsz) { valaszt(tsz, false); inp.value = ''; inp.blur(); }
  });

  async function listak() {
    const [l68, l87] = await Promise.allSettled([kerd('allomasok', { af: 68 }), kerd('allomasok', { af: 87 })]);
    if (l68.status === 'fulfilled') all.lista[68] = l68.value.allomasok;
    if (l87.status === 'fulfilled') { all.lista[87] = l87.value.allomasok; all.van87 = new Set(all.lista[87].map((x) => x.tsz)); }
    const frag = document.createDocumentFragment();
    for (const x of all.lista[68] || []) {
      const folyo = x.folyo && x.folyo !== '-' && !x.nev.includes(x.folyo) ? x.folyo : '';
      const c = folyo ? `${x.nev} · ${folyo}` : x.nev;
      nevTsz.set(c, x.tsz); nevTsz.set(x.nev, nevTsz.get(x.nev) || x.tsz);
      const o = el('option'); o.value = c; frag.append(o);
    }
    dl.append(frag);
    if (all.lista[68]) keresU.textContent = `Mérce keresése (${all.lista[68].length} közül)`;
    frissFej();
  }

  // A lapok neve → törzsszám: előbb a bot saját táblája (mercek_tsz.json), aztán a motor mércelistája, ha a név
  // ott egyetlen mércét jelöl.
  async function lapok(listaKesz) {
    let terkep = {};
    try { terkep = await (await fetch('/mercek_tsz.json')).json(); } catch (e) { /* marad a motor listája */ }
    await listaKesz.catch(() => {});
    const egyedi = new Map();
    for (const x of all.lista[68] || []) egyedi.set(x.nev, egyedi.has(x.nev) ? null : x.tsz);
    document.querySelectorAll('#mercesor .merce').forEach((box) => {
      const nevE = box.querySelector('.nev'); const nev = nevE && nevE.textContent.trim();
      const tsz = Number.isInteger(terkep[nev]) ? terkep[nev] : egyedi.get(nev);
      if (!Number.isInteger(tsz)) {
        if (all.lista[68]) box.title += '\nKözeli nézet: ennek a mércének az idősora az OVF nyílt adat-API-jából hiányzik.';
        return;
      }
      box.dataset.tsz = tsz; box.tabIndex = 0;
      box.setAttribute('role', 'button');
      box.setAttribute('aria-label', `${nev}: megnyitás közelről`);
      box.classList.add('valaszthato');
      box.addEventListener('click', () => valaszt(tsz, true));
      box.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); valaszt(tsz, true); } });
    });
    frissFej();
  }

  // ── indulás és ütem ────────────────────────────────────────────────────
  const h = /#merce=(\d+)(?:&af=(68|87))?(?:&ablak=(\d+))?/.exec(location.hash);
  if (h) {
    all.tsz = +h[1]; if (h[2]) all.af = +h[2];
    if (h[3] && ABLAKOK.some((z) => z[0] === +h[3])) all.ablak = +h[3];
  }
  frissFej();
  tolt(true).then(() => { if (h) gyoker.scrollIntoView({ block: 'start' }); });
  const listaKesz = listak();
  listaKesz.catch(() => {});
  lapok(listaKesz);

  // „most”: másodpercenként (csökkentett mozgásnál percenként); a teljes rajz percenként, az adat 5 percenként.
  setInterval(() => { if (!document.hidden) { frissKi(); farokRajz(); } }, csendes.matches ? 60000 : 1000);
  setInterval(() => {
    if (document.hidden) return;
    if (most() - all.betoltve > 300 || all.hiba) tolt(false); else rajzol();
  }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && most() - all.betoltve > 300) tolt(false); });
  let atmeretez = 0, utolsoSzel = graf.clientWidth;
  addEventListener('resize', () => {
    clearTimeout(atmeretez);
    atmeretez = setTimeout(() => {
      const w = graf.clientWidth;
      if (Math.abs(w - utolsoSzel) / Math.max(1, utolsoSzel) > 0.25) { utolsoSzel = w; tolt(false); } else rajzol();
    }, 200);
  });
})();
