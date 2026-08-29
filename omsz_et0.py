#!/usr/bin/env python3
"""
omsz_et0.py — referencia-parolgas (ET0) foldi meresbol, FAO-56 szerint.

MIERT
A referencia-parolgas eddig muholdas becslesbol jott (LSA SAF METREF). Az OMSZ
269 automata allomasa viszont mind a negy szukseges valtozot meri: homerseklet,
paratartalom, szelsebesseg, globalsugarzas. Ezekbol a FAO-56 Penman-Monteith
keplettel kiszamolhato az ET0 - foldi meresbol, nem becslesbol.

Ugyanaz a logika, mint a csapadeknal: ahol van foldi meres, azt hasznaljuk.

MIT AD ES MIT NEM
Az ET0 azt mondja meg, mennyi viz parologna el egy alacsonyra nyirt, korlatlan
vizellatasu fufelszinrol. A TENYLEGES parolgast ez nem helyettesiti - arra
foldi merohalozat nincs, marad a muholdas LSA SAF.

FAO-56 (Allen et al., 1998), 6. egyenlet:

           0.408 D (Rn - G) + g (900/(T+273)) u2 (es - ea)
  ET0 = ------------------------------------------------------
                    D + g (1 + 0.34 u2)

  Rn  nettó sugárzás (MJ/m²/nap)     G   talajhoáram (napi lépteken ~0)
  D   telítési görbe meredeksége     g   pszichrometrikus állandó
  u2  szélsebesség 2 m-en            es-ea telítési hiány

Futtatás:  python omsz_et0.py 2026-08-18
"""

import concurrent.futures as cf
import csv
import datetime as dt
import io
import json
import math
import pathlib
import statistics
import sys
import urllib.request
import zipfile

ALAP = "https://odp.met.hu/climate/observations_hungary/daily/"
FEJ = {"User-Agent": "equora-basin/2.6 (+https://basin.equora.institute)"}
PARAMS = pathlib.Path("params.json")
HIANYZO = -999
RACS_OSZLOP, RACS_SOR = 8, 6


class ErtekHiany(Exception):
    """A kért napra még nincs elég állomásadat — az OMSZ napi fájljai
    később készülnek el, mint az órásak."""


def _get(url: str, ido: int = 45) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=FEJ), timeout=ido).read()


def allomasok() -> dict:
    """{állomásszám: (lat, lon, magasság)} — a napi hálózat törzsadata."""
    nyers = _get(ALAP + "station_meta_auto.csv").decode("utf-8", "replace")
    olv = csv.reader(io.StringIO(nyers), delimiter=";")
    fejlec = [c.strip() for c in next(olv)]
    ki = {}
    for sor in olv:
        s = dict(zip(fejlec, [c.strip() for c in sor]))
        try:
            ki[s["StationNumber"]] = (float(s["Latitude"]), float(s["Longitude"]),
                                      float(s["Elevation"]))
        except (ValueError, KeyError):
            continue
    return ki


def _szam(c):
    try:
        v = float(c)
    except (TypeError, ValueError):
        return None
    return None if v <= HIANYZO + 1 else v


def et0_fao56(t, tn, tx, u, fs, sg, lat, magassag, nap):
    """FAO-56 Penman-Monteith napi ET0, mm/nap. None, ha hiányos a bemenet."""
    if None in (t, u) or tn is None or tx is None:
        return None
    tn = tn if tn is not None else t
    tx = tx if tx is not None else t
    u2 = (fs if fs is not None else 2.0)

    # A telítési gőznyomás és a görbe meredeksége (FAO-56, 11-13. egyenlet)
    e_t = lambda x: 0.6108 * math.exp(17.27 * x / (x + 237.3))
    es = (e_t(tx) + e_t(tn)) / 2
    ea = es * (u / 100.0)
    D = 4098 * e_t(t) / (t + 237.3) ** 2

    # Pszichrometrikus állandó a magasságból (7-8. egyenlet)
    P = 101.3 * ((293 - 0.0065 * magassag) / 293) ** 5.26
    g = 0.000665 * P

    # A globálsugárzás (sr oszlop) J/cm²-ben érkezik; MJ/m²-re váltjuk.
    # Az oszlopválasztás nem magától értetődő: az sg évszakos ingadozása
    # mindössze 1,1-szeres, tehát nem energiaösszeg. Az sr viszont 6,9-szeres
    # (tél 356, nyár 2471 J/cm²), és a maximuma 32 MJ/m² — ez a helyes.
    # Ahol hiányzik —
    # az állomások többségén —, a napi hőmérséklet-ingásból becsüljük:
    # derült napon nagy az ingás, felhős napon kicsi (FAO-56, 50. egyenlet).
    # A becslés pontatlanabb, de a hálózat egészét használhatóvá teszi.
    becsult_sugarzas = sg is None

    # Csillagászati sugárzás a derült égi maximumhoz (21-24. egyenlet)
    J = nap.timetuple().tm_yday
    dr = 1 + 0.033 * math.cos(2 * math.pi * J / 365)
    d = 0.409 * math.sin(2 * math.pi * J / 365 - 1.39)
    f = math.radians(lat)
    ws = math.acos(max(-1, min(1, -math.tan(f) * math.tan(d))))
    Ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(f) * math.sin(d) + math.cos(f) * math.cos(d) * math.sin(ws))
    Rso = (0.75 + 2e-5 * magassag) * Ra

    # kRs = 0.16 szárazföldi állomásra (FAO-56); a tengerparti 0.19
    Rs = (sg / 100.0) if not becsult_sugarzas else min(
        0.16 * math.sqrt(max(tx - tn, 0)) * Ra, Rso)

    Rns = 0.77 * Rs                                    # rövidhullámú, 0.23 albedó
    s = 4.903e-9                                       # Stefan-Boltzmann
    Rnl = (s * (((tx + 273.16) ** 4 + (tn + 273.16) ** 4) / 2)
           * (0.34 - 0.14 * math.sqrt(max(ea, 0)))
           * (1.35 * min(Rs / Rso, 1.0) - 0.35))
    Rn = Rns - Rnl

    szamlalo = 0.408 * D * Rn + g * (900 / (t + 273)) * u2 * max(es - ea, 0)
    nevezo = D + g * (1 + 0.34 * u2)
    return max(szamlalo / nevezo, 0) if nevezo else None


def _egy_allomas(szam, nap, hely):
    """Egy állomás napi ET0-ja, vagy None."""
    try:
        nyers = _get(f"{ALAP}recent/HABP_1D_{szam}_akt.zip", 30)
        with zipfile.ZipFile(io.BytesIO(nyers)) as z:
            with z.open(z.namelist()[0]) as f:
                szoveg = io.TextIOWrapper(f, encoding="utf-8", errors="replace").read()
    except Exception:
        return None

    sorok = [s for s in szoveg.split("\n") if s and not s.lstrip().startswith("#")]
    if len(sorok) < 2:
        return None
    fejlec = [c.strip() for c in sorok[0].split(";")]
    if not {"t", "u", "sr", "Time"} <= set(fejlec):
        return None
    idx = {k: fejlec.index(k) for k in fejlec}

    kulcs = nap.strftime("%Y%m%d")
    for s in sorok[1:]:
        c = [x.strip() for x in s.split(";")]
        if len(c) <= max(idx.values()) or not c[idx["Time"]].startswith(kulcs):
            continue
        lat, lon, mag = hely
        return et0_fao56(
            _szam(c[idx["t"]]), _szam(c[idx.get("tn", 0)]), _szam(c[idx.get("tx", 0)]),
            _szam(c[idx["u"]]), _szam(c[idx.get("fs", 0)]), _szam(c[idx["sr"]]),
            lat, mag, nap)
    return None


def napi_et0(nap):
    """(területi átlag mm/nap, állomásszám, cellaszám) — rácsos súlyozással."""
    a = allomasok()
    sys.stdout.write(f"  {len(a)} állomás lekérése…\n"); sys.stdout.flush()

    ertek = {}
    with cf.ThreadPoolExecutor(max_workers=12) as vp:
        jovo = {vp.submit(_egy_allomas, k, nap, v): k for k, v in a.items()}
        for j in cf.as_completed(jovo):
            v = j.result()
            if v is not None and 0 <= v < 20:
                ertek[jovo[j]] = v

    if len(ertek) < 30:
        raise ErtekHiany(f"Túl kevés állomás adott ET0-t ({len(ertek)}).")

    lat = [a[k][0] for k in ertek]; lon = [a[k][1] for k in ertek]
    dla = (max(lat) - min(lat)) / RACS_SOR or 1
    dlo = (max(lon) - min(lon)) / RACS_OSZLOP or 1
    cellak = {}
    for k, v in ertek.items():
        i = min(int((a[k][0] - min(lat)) / dla), RACS_SOR - 1)
        j = min(int((a[k][1] - min(lon)) / dlo), RACS_OSZLOP - 1)
        cellak.setdefault((i, j), []).append(v)
    atlag = statistics.fmean(statistics.fmean(v) for v in cellak.values())
    return atlag, len(ertek), len(cellak)


def main():
    nap = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else dt.date.today() - dt.timedelta(days=1))
    # Ha a kért napra még nincs elég adat, visszalépünk. A napi OMSZ-fájlok
    # később készülnek el, mint az órásak, ezért a csapadék napja már megvan,
    # amikor az ET0-é még nem — enélkül a kettő szétcsúszna.
    for eltol in (0, 1, 2):
        probal = nap - dt.timedelta(days=eltol)
        sys.stdout.write(f"OMSZ referencia-párolgás (FAO-56), {probal}\n")
        try:
            mm, db, cellak = napi_et0(probal)
            nap = probal
            break
        except ErtekHiany as e:
            sys.stdout.write(f"  {e} Visszalépés.\n")
    else:
        raise SystemExit("Három napra sem volt elég állomásadat.")
    sys.stdout.write(f"\n  ET0 = {mm:.2f} mm/nap · {db} állomás, {cellak} rácscella\n")

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["et_ref_omsz_mm_nap"] = {
        "ertek": round(mm, 2), "datum": str(nap), "allomas_db": db,
        "provenance": "helyszini",
        "forras": (f"OMSZ (HungaroMet) nyílt adattár, {db} automata állomás; "
                   "FAO-56 Penman-Monteith referencia-párolgás hőmérsékletből, "
                   "páratartalomból, szélsebességből és globálsugárzásból"),
        "figyelmeztetes": ("Ez a REFERENCIA-párolgás: mennyi víz párologna el egy "
                           "alacsonyra nyírt, korlátlan vízellátású fűfelszínről. "
                           "A tényleges párolgásra földi mérőhálózat nincs — az "
                           "műholdas mérésből (LSA SAF) származik."),
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    muhold = p.get("ontozesigeny") or {}
    if muhold.get("datum") == str(nap) and muhold.get("et_ref_mm"):
        m = muhold["et_ref_mm"]
        sys.stdout.write(f"  LSA SAF METREF (műholdas): {m:.2f} mm/nap\n")
        sys.stdout.write(f"  eltérés: {mm - m:+.2f} mm ({(mm/m - 1)*100:+.0f}%)\n")


if __name__ == "__main__":
    main()
