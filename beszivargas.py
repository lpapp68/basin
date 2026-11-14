#!/usr/bin/env python3
"""
beszivargas.py — hová jut a lehullott eső a talajban.

MIT SZÁMOL
Az OVF aszálymonitoring-hálózatának állomásai óránként hat mélységben (10, 20,
30, 45, 60, 75 cm) rögzítik a talajnedvességet, és ugyanott a csapadékot.
Egy esőeseménynél ebből három mennyiség jön ki:

  1. a nedvesedési front — melyik szint mikor reagált, milyen gyorsan halad
  2. a talajba került víz — rétegenként Δθ × rétegvastagság, mm-ben
  3. a zárási arány — a talajba került víz osztva a lehullott esővel

A harmadik egyben a szonda tesztje. A bemenő csapadékkal minden szondának el
kell számolnia. 100% fölött a szonda vagy a csapadékmérő helyi viszonyai
torzítanak (víz a szondacső mentén, helyi mélyedés, széllel alulfogott eső),
nagyon alacsony aránynál a víz a szondát megkerülő utakon jár. Minden eső így
hálózati szintű kalibrációs teszt, külön költség nélkül.

A Duna–Tisza közi hátság állomásainál a legközelebbi talajvízkutak szintje is
mellékerül (OVF nyílt adat-API): az esemény előtti tíz nap trendjéhez mérve
mozdult-e a talajvíz. Ez köti össze a hetes rekeszt (talaj) az évtizedessel
(talajvíz).

ELŐZETES RÖGZÍTÉS
Az elozetes_rogzites.json előre leírt várakozásokat tartalmaz (mi történik a
célidőpontig). A modul minden futáskor ellenőrzi a rögzítés hash-ét, a
célidőpont után pedig kiértékeli az állításokat, és az eredményt az
archiv/beszivargas_rogzites_eredmeny.json fájlba írja — onnan akkor is
olvasható, amikor a tíznapos ablak már továbblépett.

FORRÁS
  OVF Aszálymonitoring hivatalos API (api.php, view=getmeas), órás adatok:
    varid 8–13  talajnedvesség 10–75 cm (V/V %, kalibrált)
    varid 15    csapadék (mm/óra)
  Az időbélyegek helyi idő szerintiek (télen UTC+1, nyáron UTC+2).
  OVF nyílt adat-API (vizapi.py), adatfajta 69: talajvízállás, cm a terepszint alatt.

FUTÁS
  python beszivargas.py          hatóránként dolgozik; közben azonnal kilép
  python beszivargas.py --most   a kapu kihagyásával

  Az állomások télen hatóránként töltenek fel, ezért a hatórás kapu semmit
  nem veszít. Egy futás hét kérés, összesen ~25 MB, ~30 másodperc.

KIMENET
  params.json → "beszivargas"            a lap adatai
  archiv/beszivargas_napi.csv            napi profil állomásonként (hozzáfűzés)
  archiv/beszivargas_esemenyek.json      esemény-összegzések, állomásonként
  archiv/beszivargas_rogzites_eredmeny.json   az előzetes rögzítések eredménye
"""

import datetime as dt
import hashlib
import json
import math
import pathlib
import statistics
import sys
import time

import aszaly_api as API

PARAMS = pathlib.Path("params.json")
ARCHIV = pathlib.Path("archiv")
NAPI_CSV = ARCHIV / "beszivargas_napi.csv"
ESEMENY_JSON = ARCHIV / "beszivargas_esemenyek.json"
ROGZITES = pathlib.Path("elozetes_rogzites.json")
ROGZ_EREDMENY = ARCHIV / "beszivargas_rogzites_eredmeny.json"

SZINTEK = [10, 20, 30, 45, 60, 75]
NEDV_VARID = {10: 8, 20: 9, 30: 10, 45: 11, 60: 12, 75: 13}
CSAPADEK_VARID = 15

# Rétegek a szondák köré osztva: 0–15, 15–25, 25–37,5, 37,5–52,5, 52,5–67,5,
# 67,5–75 cm. Összesen 750 mm, vagyis a 0–75 cm-es szelvény.
VASTAG_MM = {10: 150, 20: 100, 30: 125, 45: 150, 60: 150, 75: 75}

ABLAK_NAP = 10        # ennyi napot kérünk le futásonként
KAPU_ORA = 6          # ennyi óránként dolgozik a modul
ESO_KUSZOB = 0.2      # mm/óra: ettől számít egy óra esősnek (a 0,1 nyomjel)
SZUNET_MAX = 24       # óra: ennél rövidebb szünet egy eseményen belül marad
ESEMENY_MIN = 10.0    # mm: ennél kisebb eső nem esemény
ALAP_ORA = 6          # az eső előtti ennyi óra átlaga az alapállapot
JEL = 0.4             # százalékpont: front-érkezés
JEL_TART = 0.3        # ... és utána ennyi fölött marad
TART_ORA = 4          # ... ennyi órán át
REAGAL = 0.5          # százalékpont: "reagáló szint" az összegzésben
SOROZAT_LEPES = 3     # óra: a lapra kerülő idősor lépésköze
KUT_SUGAR_KM = 10     # ennyi km-en belüli kutakat nézünk
KUT_MAX = 3           # állomásonként legfeljebb ennyit

# A Duna–Tisza közi hátság állomásai. MUNKADEFINÍCIÓ: a hátság és peremei, név
# szerint. A talajtextúrát nem a lista, hanem az adat mutatja meg — a zárási
# arány és a front sebessége állomásonként külön látszik.
HATSAG = [
    "Csólyospálos", "Csengele", "Fülöpháza", "Homokmégy", "Izsák",
    "Jakabszállás", "Kecel", "Kiskunfélegyháza", "Kiskunhalas", "Kisszállás",
    "Kunpeszér", "Lajosmizse", "Mélykút", "Nagykőrös", "Pálmonostora",
    "Ruzsa", "Tázlár", "Városföld",
]
KIEMELT = "Csólyospálos"      # a lap alapértelmezett állomása


# ── idő ──────────────────────────────────────────────────────────────────
def _ora(s) -> str:
    """'2026-11-12 05:00:00.000' vagy '2026-8-3 5:00' → '2026-11-12 05'."""
    d, _, t = str(s).strip().partition(" ")
    ev, ho, nap = (int(z) for z in d.split("-"))
    h = int(t.split(":")[0]) if t else 0
    return f"{ev:04d}-{ho:02d}-{nap:02d} {h:02d}"


def _dt(h: str) -> dt.datetime:
    return dt.datetime.strptime(h, "%Y-%m-%d %H")


def _h(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%d %H")


ORA = dt.timedelta(hours=1)


# ── letöltés ─────────────────────────────────────────────────────────────
def orak(varid: int, kezd: dt.date, veg: dt.date) -> dict:
    """{statid: {'ÉÉÉÉ-HH-NN óó': érték}} — minden állomás egyetlen kéréssel.

    A getmeas órás változóknál állomásonként külön tömböt ad; ha egy állomásnak
    csak üres értékei vannak, a tömb helyett {"0": {...}, "1": {...}} objektum
    jön. Mindkettőt kezeljük. (A napi 18-as változó egyetlen lapos tömböt ad —
    azt az aszaly.py olvassa.)"""
    for probal in range(3):
        try:
            nyers = API._hivas({"view": "getmeas", "varid": varid,
                                "fromdate": kezd.isoformat(), "todate": veg.isoformat()})
            break
        except Exception:
            if probal == 2:
                raise
            time.sleep(5 * (probal + 1))
    ki = {}
    blokkok = nyers if isinstance(nyers, list) else [nyers]
    for blokk in blokkok:
        elemek = blokk.values() if isinstance(blokk, dict) else blokk
        for x in elemek:
            if not isinstance(x, dict) or x.get("value") in (None, ""):
                continue
            try:
                v = float(x["value"])
                h = _ora(x["date"])
            except (TypeError, ValueError, KeyError):
                continue
            ki.setdefault(x.get("statid"), {})[h] = v
    return ki


def letolt(kezd: dt.date, veg: dt.date):
    T = {lv: orak(NEDV_VARID[lv], kezd, veg) for lv in SZINTEK}
    P = orak(CSAPADEK_VARID, kezd, veg)
    return P, T


# ── esemény ──────────────────────────────────────────────────────────────
def esos_szakaszok(P: dict) -> list:
    """Esős szakaszok: ESO_KUSZOB feletti órák, SZUNET_MAX-nál rövidebb
    szünetekkel összefűzve. Csak az ESEMENY_MIN feletti marad meg."""
    orak_ = sorted(h for h, v in P.items() if v >= ESO_KUSZOB)
    szak = []
    for h in orak_:
        t = _dt(h)
        if szak and (t - szak[-1][1]) <= dt.timedelta(hours=SZUNET_MAX):
            szak[-1][1] = t
        else:
            szak.append([t, t])
    ki = []
    for k, v in szak:
        ossz = sum(x for h, x in P.items() if k <= _dt(h) <= v)
        if ossz >= ESEMENY_MIN:
            ki.append((k, v))
    return ki


def ertek_ekkor(sor: dict, t: dt.datetime, vissza: int = 3):
    """A t időpont értéke, vagy a legfeljebb `vissza` órával korábbi."""
    for i in range(vissza + 1):
        v = sor.get(_h(t - i * ORA))
        if v is not None:
            return v
    return None


def alapallapot(sor: dict, kezd: dt.datetime):
    ert = [sor.get(_h(kezd - i * ORA)) for i in range(1, ALAP_ORA + 1)]
    ert = [v for v in ert if v is not None]
    return round(sum(ert) / len(ert), 2) if len(ert) >= 3 else None


def erkezes(sor: dict, alap: float, kezd: dt.datetime, veg: dt.datetime):
    """Az első óra, amikor a szint JEL-lel az alap fölé megy, és utána
    TART_ORA órán át JEL_TART fölött marad (ami ebből rendelkezésre áll)."""
    t = kezd
    while t <= veg:
        v = sor.get(_h(t))
        if v is not None and v - alap >= JEL:
            utana = [sor.get(_h(t + i * ORA)) for i in range(1, TART_ORA + 1)
                     if t + i * ORA <= veg]
            utana = [u for u in utana if u is not None]
            if all(u - alap >= JEL_TART for u in utana):
                return t
        t += ORA
    return None


def tarolt(dth: dict) -> float:
    return sum(dth[lv] / 100 * VASTAG_MM[lv] for lv in SZINTEK if dth.get(lv) is not None)


def osztaly(arany):
    if arany is None:
        return None
    if arany > 1.1:
        return "tobblet"
    if arany < 0.5:
        return "hiany"
    return "zaro"


def allomas_esemenyei(nev, sid, P, T, archiv, sorozat_kell):
    """Az állomás eseményei a letöltött ablakban, mérőszámokkal."""
    if not P:
        return []
    szak = esos_szakaszok(P)
    if not szak:
        return []
    utolso_ido = max((_dt(h) for h in T[10].get(sid, {})), default=None)
    if utolso_ido is None:
        return []
    ki = []
    for i, (kezd, eso_veg) in enumerate(szak):
        kov = szak[i + 1][0] - ORA if i + 1 < len(szak) else None
        veg = min(utolso_ido, kov) if kov else utolso_ido
        if veg < kezd:
            continue
        kulcs = f"{nev}|{_h(kezd)}"
        regi = archiv.get(kulcs, {})

        alap = {}
        for lv in SZINTEK:
            sor = T[lv].get(sid, {})
            a = alapallapot(sor, kezd)
            if a is None:
                a = (regi.get("alap") or {}).get(str(lv))
            alap[lv] = a
        if alap[10] is None:
            continue                     # az ablak az eső előtti órákat már nem fedi

        most, dth, erk = {}, {}, {}
        for lv in SZINTEK:
            sor = T[lv].get(sid, {})
            v = ertek_ekkor(sor, veg)
            most[lv] = v
            dth[lv] = round(v - alap[lv], 2) if (v is not None and alap[lv] is not None) else None
            e = erkezes(sor, alap[lv], kezd, veg) if alap[lv] is not None else None
            if e is None and (regi.get("erkezes") or {}).get(str(lv)):
                e = _dt(regi["erkezes"][str(lv)])
            erk[lv] = e

        p_ossz = round(sum(v for h, v in P.items() if kezd <= _dt(h) <= veg), 1)
        ds = round(tarolt(dth), 1)
        arany = round(ds / p_ossz, 3) if p_ossz >= ESEMENY_MIN else None

        megerk = [lv for lv in SZINTEK if erk[lv]]
        front = max(megerk) if megerk else None
        kovetkezo = next((lv for lv in SZINTEK if front and lv > front and not erk[lv]), None)
        reagalt = [lv for lv in SZINTEK if dth[lv] is not None and dth[lv] >= REAGAL]

        sebesseg = []
        rendezett = [lv for lv in SZINTEK if erk[lv]]
        for a_, b_ in zip(rendezett, rendezett[1:]):
            ora = (erk[b_] - erk[a_]).total_seconds() / 3600
            if ora > 0:
                sebesseg.append({"tol": a_, "ig": b_, "ora": round(ora),
                                 "cm_nap": round((b_ - a_) / ora * 24, 1)})

        e = {
            "nev": nev, "statid": sid,
            "hatsag": nev in HATSAG,
            "kezd": _h(kezd), "eso_veg": _h(eso_veg), "ig": _h(veg),
            "allapot": "folyik" if (utolso_ido - eso_veg) < dt.timedelta(hours=SZUNET_MAX) and not kov else "lezart",
            "P_mm": p_ossz, "dS_mm": ds, "arany": arany, "osztaly": osztaly(arany),
            "alap": {str(k): v for k, v in alap.items()},
            "most": {str(k): v for k, v in most.items()},
            "dtheta": {str(k): v for k, v in dth.items()},
            "reteg_mm": {str(k): (round(dth[k] / 100 * VASTAG_MM[k], 1) if dth[k] is not None else None)
                         for k in SZINTEK},
            "erkezes": {str(k): (_h(v) if v else None) for k, v in erk.items()},
            "front_cm": front, "kovetkezo_cm": kovetkezo,
            "reagalt": reagalt,
            "legmelyebb_reagalo": max(reagalt) if reagalt else None,
            "sebesseg": sebesseg,
        }
        if sorozat_kell:
            e["sorozat"] = sorozat(P, T, sid, alap, kezd, veg)
        ki.append(e)
    return ki


def sorozat(P, T, sid, alap, kezd, veg):
    """Háromórás idősor a laphoz: [címke, kumulált eső, tárolt víz, Δθ10..75]."""
    ki = []
    t = kezd - dt.timedelta(hours=ALAP_ORA)
    kum = 0.0
    utolso = t
    while t <= veg + dt.timedelta(hours=SOROZAT_LEPES - 1):
        tt = min(t, veg)
        kum += sum(v for h, v in P.items() if utolso < _dt(h) <= tt and _dt(h) >= kezd)
        utolso = tt
        d = {}
        for lv in SZINTEK:
            v = ertek_ekkor(T[lv].get(sid, {}), tt)
            d[lv] = round(v - alap[lv], 1) if (v is not None and alap[lv] is not None) else None
        ki.append([_h(tt), round(kum, 1), round(tarolt(d), 1)] + [d[lv] for lv in SZINTEK])
        if tt == veg:
            break
        t += dt.timedelta(hours=SOROZAT_LEPES)
    return ki


# ── talajvíz ─────────────────────────────────────────────────────────────
def _meredekseg(pontok):
    """Theil–Sen-meredekség (a páronkénti meredekségek mediánja), cm/nap.
    Egy-egy kiugró leolvasás nem viszi el, ellentétben a legkisebb négyzetekkel.
    pontok: [(nap, cm)]."""
    if len(pontok) < 4:
        return None
    m = [(y2 - y1) / (x2 - x1) for i, (x1, y1) in enumerate(pontok)
         for x2, y2 in pontok[i + 1:] if x2 != x1]
    return statistics.median(m) if m else None


KUT_UGRAS_CM = 15     # két egymást követő leolvasás közti ennyinél nagyobb ugrás
                      # adatszakadásra utal (új nullpont, csere) — a kutat kihagyjuk


def kutak(esemenyek, allomas_eov):
    """A hátsági állomásokhoz a legközelebbi talajvízkutak szintje.

    A távolságot EOV-koordinátában számoljuk (méter): mind az aszálymonitoring,
    mind az OVF kút-törzsadat EOV-ban adja a helyet, így nincs vetítési hiba.
    Az emelkedés előjele: pozitív = a talajvíz feljebb jött.
    """
    import vizapi
    try:
        lista = [k for k in vizapi.allomasok(12) if k.get("EOVx") and k.get("Uzem")]
    except Exception as e:
        return {}, f"kút-törzsadat: {e}"
    igeny = {}
    for e in esemenyek:
        xy = allomas_eov.get(e["statid"])
        if not xy:
            continue
        kozel = sorted(((math.hypot(k["EOVx"] - xy[0], k["EOVy"] - xy[1]) / 1000, k)
                        for k in lista), key=lambda z: z[0])
        igeny[e["nev"]] = [(round(d, 1), k) for d, k in kozel if d <= KUT_SUGAR_KM][:KUT_MAX + 2]
    tsz = sorted({k["Tsz"] for v in igeny.values() for _, k in v})
    if not tsz:
        return {}, None
    legkor = min(_dt(e["kezd"]) for e in esemenyek) - dt.timedelta(days=12)
    # A kút-API UTC-t ad; az esemény ideje helyi. A különbség egy-két óra,
    # a napi kétszeri kútleolvasásnál ez nem számít.
    try:
        sorok = {}
        for i in range(0, len(tsz), 100):
            sorok.update(vizapi.idosor(tsz[i:i + 100], 69, legkor,
                                       dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                                       + dt.timedelta(hours=2)))
    except Exception as e:
        return {}, f"kút-idősor: {e}"
    ki = {}
    for e in esemenyek:
        kezd = _dt(e["kezd"])
        sor_ki = []
        for tav, k in igeny.get(e["nev"], []):
            pt = [(t.replace(tzinfo=None), float(v)) for t, v in sorok.get(k["Tsz"], [])]
            pt.sort()
            if any(abs(b[1] - a[1]) > KUT_UGRAS_CM for a, b in zip(pt, pt[1:])):
                continue
            elotte = [(t, v) for t, v in pt if kezd - dt.timedelta(days=10) <= t < kezd]
            utana = [(t, v) for t, v in pt if t >= kezd]
            if len(elotte) < 4 or not utana:
                continue
            kozvetlen = [v for t, v in elotte if t >= kezd - dt.timedelta(days=2)]
            alap = statistics.median(kozvetlen) if kozvetlen else elotte[-1][1]
            m = _meredekseg([((t - kezd).total_seconds() / 86400, v) for t, v in elotte])
            t_u, v_u = utana[-1]
            napok = (t_u - kezd).total_seconds() / 86400
            emel = alap - v_u
            trend_emel = -(m or 0) * napok
            sor_ki.append({"nev": k["Nev"].strip(), "tsz": k["Tsz"], "tav_km": tav,
                           "melyseg_m": round(v_u / 100, 2), "utolso": t_u.strftime("%Y-%m-%d %H"),
                           "emelkedes_cm": round(emel, 1),
                           "trend_cm_nap": round(-(m or 0), 2),
                           "trendtol_cm": round(emel - trend_emel, 1)})
            if len(sor_ki) >= KUT_MAX:
                break
        if sor_ki:
            ki[e["nev"]] = sor_ki
    return ki, None


# ── archívum ─────────────────────────────────────────────────────────────
def napi_archiv(P, T, nevek, ma: dt.date):
    """A lezárt napok napi profilja állomásonként, hozzáfűzéssel."""
    fej = "datum,allomas,P_mm," + ",".join(f"t{lv}" for lv in SZINTEK) + ",orak\n"
    meglevo = set()
    if NAPI_CSV.exists():
        for sor in NAPI_CSV.read_text(encoding="utf-8").splitlines()[1:]:
            r = sor.split(",")
            if len(r) > 2:
                meglevo.add((r[0], r[1]))
    uj = []
    for sid, nev in nevek.items():
        napok = {}
        for h in T[10].get(sid, {}):
            napok.setdefault(h[:10], []).append(h)
        for nap, hs in sorted(napok.items()):
            if nap >= ma.isoformat() or (nap, nev) in meglevo or len(hs) < 20:
                continue
            p = sum(v for h, v in P.get(sid, {}).items() if h[:10] == nap)
            atl = []
            for lv in SZINTEK:
                e = [v for h, v in T[lv].get(sid, {}).items() if h[:10] == nap]
                atl.append(f"{sum(e)/len(e):.2f}" if e else "")
            uj.append(f"{nap},{nev},{p:.1f}," + ",".join(atl) + f",{len(hs)}\n")
    if uj:
        uj.sort()
        uj_fajl = not NAPI_CSV.exists()
        with NAPI_CSV.open("a", encoding="utf-8") as f:
            if uj_fajl:
                f.write(fej)
            f.writelines(uj)
    return len(uj)


def esemeny_archiv_olvas():
    try:
        return json.loads(ESEMENY_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def esemeny_archiv_ir(archiv, esemenyek):
    for e in esemenyek:
        archiv[f"{e['nev']}|{e['kezd']}"] = {k: v for k, v in e.items()
                                             if k not in ("sorozat", "most", "reteg_mm", "kutak", "xy")}
    ESEMENY_JSON.write_text(json.dumps(dict(sorted(archiv.items())), ensure_ascii=False,
                                       indent=1), encoding="utf-8")


# ── előzetes rögzítés ────────────────────────────────────────────────────
HASH_KIHAGY = {"hash_sha256", "repoba_rogzitve_utc", "rogziteskor_ismert"}


def rogzites_hash(r: dict) -> str:
    mag = {k: v for k, v in r.items() if k not in HASH_KIHAGY}
    return hashlib.sha256(json.dumps(mag, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _allitas(a, theta_cel, alap, ds, p_uj):
    t = a["tipus"]
    if t in ("reagal", "nem_reagal"):
        lv = a["szint"]
        d = None if theta_cel.get(lv) is None or alap.get(str(lv)) is None \
            else round(theta_cel[lv] - alap[str(lv)], 2)
        ok = None if d is None else (d >= REAGAL if t == "reagal" else d < REAGAL)
        return {**a, "mert_dtheta": d, "teljesult": ok}
    if t == "dS_tartomany":
        ok = None if ds is None else (a["min"] <= ds <= a["max"])
        return {**a, "mert_dS_mm": ds, "teljesult": ok}
    if t == "novekmeny_arany":
        # az új esőből mennyi jelent meg többletként a rögzítéskori állapothoz képest
        ar = None if (ds is None or not p_uj) else round((ds - a["dS_rogzites"]) / p_uj, 3)
        ok = None if ar is None else (a["min"] <= ar <= a["max"])
        return {**a, "mert_arany": ar, "teljesult": ok}
    return {**a, "teljesult": None}


def rogzitesek(P, T, nev2sid):
    if not ROGZITES.exists():
        return []
    try:
        lista = json.loads(ROGZITES.read_text(encoding="utf-8")).get("rogzitesek", [])
    except Exception as e:
        return [{"hiba": f"elozetes_rogzites.json: {e}"}]
    try:
        kesz = json.loads(ROGZ_EREDMENY.read_text(encoding="utf-8"))
    except Exception:
        kesz = {}
    ki = []
    for r in lista:
        azon = r.get("azonosito")
        hash_ok = rogzites_hash(r) == r.get("hash_sha256")
        alap = r.get("alap", {})
        sid = nev2sid.get(r.get("allomas"))
        cel = _dt(r["cel_ido"])
        osszegzes = {"azonosito": azon, "allomas": r.get("allomas"), "cel_ido": r["cel_ido"],
                     "hash_sha256": r.get("hash_sha256"), "hash_egyezik": hash_ok,
                     "megfogalmazva": r.get("megfogalmazva"),
                     "repoba_rogzitve_utc": r.get("repoba_rogzitve_utc"),
                     "rogziteskor_ismert": r.get("rogziteskor_ismert"),
                     "forgatokonyvek": {k: v.get("leiras") for k, v in r.get("forgatokonyvek", {}).items()},
                     "feltevesek": r.get("feltevesek", [])}
        if azon in kesz:
            ki.append({**osszegzes, **kesz[azon], "hash_egyezik": hash_ok})
            continue
        if not sid:
            ki.append({**osszegzes, "allapot": "nincs_adat"})
            continue
        utolso = max((_dt(h) for h in T[10].get(sid, {})), default=None)
        ido = min(cel, utolso) if utolso else None
        theta = {lv: ertek_ekkor(T[lv].get(sid, {}), ido) if ido else None for lv in SZINTEK}
        ds = None
        if all(theta[lv] is not None and alap.get(str(lv)) is not None for lv in SZINTEK):
            ds = round(sum((theta[lv] - alap[str(lv)]) / 100 * VASTAG_MM[lv] for lv in SZINTEK), 1)
        p_tol = _dt(r["forgatokonyv_tol"])
        p = round(sum(v for h, v in P.get(sid, {}).items() if p_tol <= _dt(h) <= (ido or p_tol)), 1)
        forg = "esos" if p >= r.get("forgatokonyv_kuszob_mm", 15) else "szaraz"
        allitasok = [_allitas(a, theta, alap, ds, p)
                     for a in r["forgatokonyvek"].get(forg, {}).get("allitasok", [])]
        if utolso and utolso >= cel:
            ered = [a["teljesult"] for a in allitasok if a["teljesult"] is not None]
            allapot = ("teljesult" if ered and all(ered) else
                       "reszben" if any(ered) else "nem_teljesult")
            eredmeny = {"allapot": allapot, "ertekelve_ekkor": _h(utolso), "eso_mm": p,
                        "forgatokonyv": forg, "allitasok": allitasok, "dS_mm": ds}
            kesz[azon] = eredmeny
            ROGZ_EREDMENY.write_text(json.dumps(kesz, ensure_ascii=False, indent=1), encoding="utf-8")
            ki.append({**osszegzes, **eredmeny})
        else:
            ki.append({**osszegzes, "allapot": "fuggoben", "allas_ekkor": _h(ido) if ido else None,
                       "eso_mm_eddig": p, "forgatokonyv_most": forg,
                       "allitasok_most": allitasok, "dS_mm_most": ds})
    return ki


# ── összegzés ────────────────────────────────────────────────────────────
def vetites_terkepbol(eov, nevek, eov_wgs):
    """A terkep.json vetülete a már elhelyezett állomásokból visszaillesztve.

    Az aszaly.vetites() a hosszúságban és a szélességben külön-külön lineáris
    (x = a·lon + b, y = c·lat + d), ezért néhány ismert pont pontosan
    visszaadja. A terkep.json "allomasok" mezője ilyen pontokat tartalmaz."""
    tk = json.loads(pathlib.Path("terkep.json").read_text(encoding="utf-8"))
    nev2sid = {v: k for k, v in nevek.items()}
    lo_x, la_y = [], []
    for nev, (x, y) in (tk.get("allomasok") or {}).items():
        sid = nev2sid.get(nev)
        if sid in eov:
            la, lo = eov_wgs(*eov[sid])
            lo_x.append((lo, x)); la_y.append((la, y))
    if len(lo_x) < 2:
        raise ValueError("a terkep.json-ben kevés az ismert állomás")

    def illeszt(p):
        mx = sum(a for a, _ in p) / len(p); my = sum(b for _, b in p) / len(p)
        m = sum((a - mx) * (b - my) for a, b in p) / sum((a - mx) ** 2 for a, _ in p)
        return m, my - m * mx
    ax, bx = illeszt(lo_x)
    ay, by = illeszt(la_y)
    return lambda lo, la: (round(ax * lo + bx, 1), round(ay * la + by, 1))


def osszegez(lista):
    if not lista:
        return None
    ar = [e["arany"] for e in lista if e["arany"] is not None]
    fr = {}
    for e in lista:
        fr[str(e["legmelyebb_reagalo"])] = fr.get(str(e["legmelyebb_reagalo"]), 0) + 1
    return {
        "allomas_db": len(lista),
        "P_atlag": round(sum(e["P_mm"] for e in lista) / len(lista), 1),
        "dS_atlag": round(sum(e["dS_mm"] for e in lista) / len(lista), 1),
        "arany_median": round(statistics.median(ar), 3) if ar else None,
        "zaro_db": sum(1 for e in lista if e["osztaly"] == "zaro"),
        "tobblet_db": sum(1 for e in lista if e["osztaly"] == "tobblet"),
        "hiany_db": sum(1 for e in lista if e["osztaly"] == "hiany"),
        "legmelyebb_eloszlas": fr,
    }


def main():
    most = dt.datetime.now(dt.timezone.utc)
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    elozo = p.get("beszivargas") or {}
    if "--most" not in sys.argv and elozo.get("futas_utc"):
        kor = most - dt.datetime.fromisoformat(elozo["futas_utc"])
        if kor < dt.timedelta(hours=KAPU_ORA):
            print(f"  beszivárgás: {kor.total_seconds()/3600:.1f} órája futott, a kapu {KAPU_ORA} óra")
            return

    ma = (most + dt.timedelta(hours=1)).date()        # helyi nap, közelítőleg
    kezd = ma - dt.timedelta(days=ABLAK_NAP)
    allomasok = API.allomasok()
    nevek = {x["statid"]: x["name"].strip() for x in allomasok}
    nev2sid = {v: k for k, v in nevek.items()}
    eov = {x["statid"]: (float(x["eovx"]), float(x["eovy"])) for x in allomasok
           if x.get("eovx") and x.get("eovy")}

    P, T = letolt(kezd, ma)
    ARCHIV.mkdir(exist_ok=True)
    uj_nap = napi_archiv(P, T, nevek, ma)
    archiv = esemeny_archiv_olvas()

    minden = []
    for sid, nev in sorted(nevek.items(), key=lambda z: z[1]):
        minden += allomas_esemenyei(nev, sid, P.get(sid, {}), T, archiv, nev in HATSAG)
    esemeny_archiv_ir(archiv, minden)

    # állomásonként a legutóbbi esemény, ha a kezdete az ablakon belül van
    utolso = {}
    for e in minden:
        if e["nev"] not in utolso or e["kezd"] > utolso[e["nev"]]["kezd"]:
            utolso[e["nev"]] = e
    friss = list(utolso.values())
    hatsag = sorted((e for e in friss if e["hatsag"]), key=lambda e: e["nev"])

    kutak_ki, kut_hiba = ({}, None)
    if hatsag:
        kutak_ki, kut_hiba = kutak(hatsag, eov)
    for e in hatsag:
        e["kutak"] = kutak_ki.get(e["nev"], [])

    utolso_adat = max((h for lv in SZINTEK for s in T[lv].values() for h in s), default=None)
    rogz = rogzitesek(P, T, nev2sid)

    # Térképi hely: ugyanaz a vetület, mint a talaj-panel állomástérképén
    # (aszaly.vetites), hogy a pontok a határvonalra illeszkedjenek. A
    # hatar.geojson nincs a repóban (.gitignore), ezért ahol megvan, ott a pontos
    # helyeket az allomas_xy.json-be is kiírjuk (ez a repóba kerül), a bot pedig
    # onnan olvas. Végső tartalék: a terkep.json elhelyezett állomásaiból
    # visszaillesztett vetület (legfeljebb ~8 egység eltérés az 1000-ből).
    xy = {}
    cache = pathlib.Path("allomas_xy.json")
    try:
        import aszaly
        try:
            vet = aszaly.vetites()
            pontos = True
        except Exception:
            vet = vetites_terkepbol(eov, nevek, aszaly.eov_wgs)
            pontos = False
        tarolt_xy = {}
        if not pontos and cache.exists():
            tarolt_xy = json.loads(cache.read_text(encoding="utf-8"))
        for sid, (ex, ey) in eov.items():
            if nevek[sid] in tarolt_xy:
                xy[nevek[sid]] = tarolt_xy[nevek[sid]]
                continue
            la, lo = aszaly.eov_wgs(ex, ey)
            xy[nevek[sid]] = list(vet(lo, la))
        if pontos:
            uj = json.dumps(dict(sorted(xy.items())), ensure_ascii=False, indent=0)
            if not cache.exists() or cache.read_text(encoding="utf-8") != uj:
                cache.write_text(uj, encoding="utf-8")
    except Exception as e:
        print(f"  (térképi hely nélkül: {e})")

    def _s(v):
        return "" if v is None else (f"{v + 0.0:g}" if isinstance(v, float) else str(v))

    LAPRA = ("nev", "kezd", "eso_veg", "ig", "allapot", "P_mm", "dS_mm", "arany", "osztaly",
             "dtheta", "reteg_mm", "erkezes", "front_cm", "kovetkezo_cm", "legmelyebb_reagalo",
             "sebesseg", "kutak")
    hatsag_lap = []
    for e in hatsag:
        d = {k: e.get(k) for k in LAPRA}
        d["xy"] = xy.get(e["nev"])
        # Tömör sorok: a data.json behúzott formában íródik, egy listaelem egy
        # sort foglalna — szövegként egy idősor-pont egyetlen sor.
        d["sorozat"] = ["|".join(_s(v) for v in r) for r in e.get("sorozat", [])]
        hatsag_lap.append(d)
    orszagos_lista = [
        "|".join(_s(v) for v in (e["nev"], e["kezd"], e["P_mm"], e["dS_mm"], e["arany"],
                                 e["osztaly"], e["legmelyebb_reagalo"], int(e["hatsag"]),
                                 *(xy.get(e["nev"]) or (None, None))))
        for e in sorted(friss, key=lambda z: (z["arany"] is None, -(z["arany"] or 0)))]

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["beszivargas"] = {
        "futas_utc": most.isoformat(timespec="seconds"),
        "adat_eddig": utolso_adat,
        "ablak": [kezd.isoformat(), ma.isoformat()],
        "allomas_db": len(nevek),
        "esemenyes_db": len(friss),
        "kiemelt": KIEMELT,
        "hatsag": hatsag_lap,
        "hatsag_osszeg": osszegez(hatsag),
        "orszagos": osszegez(friss),
        # nev|kezd|P|dS|arany|osztaly|legmelyebb|hatsag(0/1)|x|y
        "orszagos_lista": orszagos_lista,
        "rogzitesek": rogz,
        "kut_hiba": kut_hiba,
        "modszer": {
            "retegek_mm": {str(k): v for k, v in VASTAG_MM.items()},
            "eso_kuszob_mm_ora": ESO_KUSZOB, "szunet_max_ora": SZUNET_MAX,
            "esemeny_min_mm": ESEMENY_MIN, "alap_ora": ALAP_ORA,
            "erkezes_pp": JEL, "tartas_pp": JEL_TART, "tartas_ora": TART_ORA,
            "reagal_pp": REAGAL, "kut_sugar_km": KUT_SUGAR_KM,
        },
        "provenance": "szarmaztatott",
        "forras": ("OVF Aszálymonitoring hivatalos API (api.php), órás talajnedvesség 10–75 cm "
                   "és csapadék; talajvízkutak: OVF nyílt adat-API (adatfajta 69)"),
        "figyelmeztetes": ("A tárolt víz a szondák köré osztott rétegekből számol (0–15, 15–25, "
                           "25–37,5, 37,5–52,5, 52,5–67,5, 67,5–75 cm). Ahol a front két szonda "
                           "között jár, a réteg egésze a szonda értékét kapja, ezért a frissen "
                           "nedvesedő rétegnél a becslés felfelé torzít. A zárási arány a szonda "
                           "és a csapadékmérő helyi viszonyait együtt teszteli."),
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    o = p["beszivargas"]["orszagos"] or {}
    h = p["beszivargas"]["hatsag_osszeg"] or {}
    print(f"  adat eddig: {utolso_adat}; {len(friss)} állomáson esemény az ablakban, "
          f"napi archív +{uj_nap} sor")
    if h:
        print(f"  hátság: {h['allomas_db']} állomás, eső átl. {h['P_atlag']} mm, "
              f"talajban átl. {h['dS_atlag']} mm, zárási medián {h['arany_median']}")
    if o:
        print(f"  országos: medián zárás {o['arany_median']}, záró {o['zaro_db']}, "
              f"többlet {o['tobblet_db']}, hiány {o['hiany_db']}")
    for e in hatsag:
        if e["nev"] == KIEMELT:
            print(f"  {KIEMELT}: {e['P_mm']} mm eső, {e['dS_mm']} mm a talajban, "
                  f"front {e['front_cm']} cm, kutak: {len(e.get('kutak', []))}")
    for r in rogz:
        print(f"  rögzítés {r.get('azonosito')}: {r.get('allapot')}, hash "
              f"{'egyezik' if r.get('hash_egyezik') else 'NEM EGYEZIK'}")
    if kut_hiba:
        print(f"  !! talajvíz: {kut_hiba}")


if __name__ == "__main__":
    main()
