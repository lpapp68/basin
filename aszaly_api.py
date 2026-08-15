#!/usr/bin/env python3
"""
aszaly_api.py — az OVF aszálymonitoring hivatalos API-ja.

MIÉRT EZ
Eddig a lap egy visszafejtett letöltő-végpontot használt, tíz állomásra.
Az OVF (Oláh Péter, Adattári Osztály) elküldte a hivatalos API leírását:
regisztráció nélkül, dokumentáltan, mind a 127 állomásra.

  POST https://aszalymonitoring.vizugy.hu/api.php
       view=getvariables | getstations | getmeas

A válasz {"entries": [...]} alakú, HTML-escape-elt JSON.

PARAMÉTEREK (varid)
   1 levegőhőmérséklet          14 relatív páratartalom
   2-7 talajhőmérséklet 10-75cm 15 csapadék (60 perc)
   8-13 TALAJNEDVESSÉG 10-75cm  16 aszályindex (számított)
                                17 vízhiány 35 cm (számított)
                                18 VÍZHIÁNY 80 cm (számított)

A lap ma a 18-ast használja. A 8-13 hatszintű talajnedvesség eddig
egyáltalán nem volt meg — abból valódi gyökérzóna-profil rajzolható.
"""

import datetime as dt
import html
import json
import urllib.parse
import urllib.request

API = "https://aszalymonitoring.vizugy.hu/api.php"
FEJ = {"User-Agent": "equora-basin/2.5 (+https://basin.equora.institute)",
       "Content-Type": "application/x-www-form-urlencoded"}

LEVEGO_HO, PARATARTALOM, CSAPADEK = 1, 14, 15
TALAJ_HO = {10: 2, 20: 3, 30: 4, 45: 5, 60: 6, 75: 7}
TALAJNEDV = {10: 8, 20: 9, 30: 10, 45: 11, 60: 12, 75: 13}
ASZALYINDEX, VIZHIANY_35, VIZHIANY_80 = 16, 17, 18


def _hivas(mezok: dict):
    test = urllib.parse.urlencode(mezok).encode()
    r = urllib.request.Request(API, data=test, headers=FEJ)
    nyers = urllib.request.urlopen(r, timeout=90).read().decode("utf-8", "replace")
    d = json.loads(html.unescape(nyers))
    return d.get("entries", d) if isinstance(d, dict) else d


def parameterek() -> list:
    """A 18 mért és számított mennyiség leírása."""
    return _hivas({"view": "getvariables"})


def allomasok() -> list:
    """127 állomás: statid (GUID), name, eovx, eovy."""
    return _hivas({"view": "getstations"})


def meresek(varid: int, kezdet=None, veg=None, statid: str = None) -> dict:
    """{statid: [(dátum, érték), ...]} — a hiányzó értékek kimaradnak.

    A válasz egy szinttel mélyebb tömbben jön, ezért kicsomagoljuk.
    A dátum "2026-8-13" alakú (nem nullázott), ezért normalizáljuk.
    """
    m = {"view": "getmeas", "varid": varid}
    if kezdet: m["fromdate"] = kezdet.strftime("%Y-%m-%d") if hasattr(kezdet, "strftime") else kezdet
    if veg:    m["todate"]   = veg.strftime("%Y-%m-%d") if hasattr(veg, "strftime") else veg
    if statid: m["statid"] = statid

    nyers = _hivas(m)
    # a getmeas [[{...}]] alakban ad vissza
    lista = nyers[0] if (nyers and isinstance(nyers[0], list)) else nyers

    ki = {}
    for x in lista:
        if not isinstance(x, dict) or x.get("value") is None:
            continue
        sid = x.get("statid") or statid
        try:
            ertek = float(x["value"])
        except (TypeError, ValueError):
            continue
        d = str(x["date"]).split(" ")[0].split(".")[0]
        try:
            ev, ho, nap = (int(z) for z in d.split("-"))
            d = f"{ev:04d}-{ho:02d}-{nap:02d}"
        except ValueError:
            pass
        ki.setdefault(sid, []).append((d, ertek))
    for v in ki.values():
        v.sort()
    return ki


def utolso(varid: int, napok: int = 5) -> dict:
    """A legfrissebb érték állomásonként: {statid: (dátum, érték)}."""
    ma = dt.date.today()
    d = meresek(varid, ma - dt.timedelta(days=napok), ma)
    return {k: v[-1] for k, v in d.items() if v}


if __name__ == "__main__":
    p = parameterek()
    print(f"{len(p)} paraméter, {len(allomasok())} állomás\n")

    a = {x["statid"]: x["name"] for x in allomasok()}
    for varid, cimke in ((VIZHIANY_80, "vízhiány 80 cm (mm)"),
                         (TALAJNEDV[30], "talajnedvesség 30 cm (V/V %)")):
        u = utolso(varid)
        ertekek = sorted(u.items(), key=lambda z: -z[1][1])
        print(f"{cimke} — {len(u)} állomás ad adatot")
        for sid, (d, v) in ertekek[:5]:
            print(f"   {a.get(sid, sid)[:22]:<24} {v:>8.1f}   {d}")
        atl = sum(v for _, (_, v) in u.items()) / len(u)
        print(f"   {'ÁTLAG':<24} {atl:>8.1f}\n")
