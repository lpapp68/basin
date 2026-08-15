#!/usr/bin/env python3
"""
aszaly.py — talaj-vízhiány az OVF aszálymonitoring HIVATALOS API-jából.

VÁLTOZÁS a korábbihoz képest
Eddig a weboldal letöltő-űrlapját utánoztuk, visszafejtett paraméterekkel,
tíz kiválasztott állomásra. Az OVF Adattári Osztálya elküldte a hivatalos
API leírását (api.docx, 2022-09-29): regisztráció nélkül, dokumentáltan,
mind a 127 állomásra egyetlen kéréssel.

  POST https://aszalymonitoring.vizugy.hu/api.php
       view=getmeas&varid=18&fromdate=…&todate=…

MIÉRT JOBB
  - hivatalos forrás a visszafejtett helyett
  - 127 állomás a korábbi 10 helyett: az országos átlag valódi átlag lesz
  - egyetlen kérés napi ~10 helyett
  - a jövőben elérhető: hatszintű talajhőmérséklet, aszályindex, 35 cm-es
    vízhiány — ugyanezzel a modullal

A TÉRKÉPRE továbbra is tíz állomás kerül (legtávolabbi-pont mintavétel),
mert száznál több körlap olvashatatlan volna; az ÁTLAG viszont mind a
127-ből számol.
"""

import datetime as dt
import json
import math
import pathlib
import sys

import aszaly_api as API

PARAMS = pathlib.Path("params.json")
TERKEP = pathlib.Path("terkep.json")
TERKEPRE = 10          # ennyi állomás kerül a térképre


def eov_wgs(x: float, y: float):
    """EOV → WGS84 közelítés. A térképi elhelyezéshez elég pontos."""
    lat = 47.1 + (x - 200000) / 111320.0
    lon = 19.05 + (y - 650000) / (111320.0 * math.cos(math.radians(47.1)))
    return lat, lon


def legtavolabbi(pontok, db):
    """Legtávolabbi-pont mintavétel: a kiválasztottak jól szétszórtak legyenek."""
    if len(pontok) <= db:
        return pontok
    ki = [max(pontok, key=lambda p: p["lat"])]
    while len(ki) < db:
        ki.append(max(
            (p for p in pontok if p not in ki),
            key=lambda p: min((p["lat"]-q["lat"])**2 + (p["lon"]-q["lon"])**2 for q in ki)))
    return ki


def main():
    veg = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else dt.date.today() - dt.timedelta(days=1))
    kezd = veg - dt.timedelta(days=30)

    nevek = {x["statid"]: x["name"].strip() for x in API.allomasok()}
    eov = {x["statid"]: (float(x["eovx"]), float(x["eovy"])) for x in API.allomasok()}

    sorozat = API.meresek(API.VIZHIANY_80, kezd, veg)
    if not sorozat:
        raise SystemExit("Az aszály-API nem adott vízhiány-adatot erre az időszakra.")

    allomasok = []
    for sid, pontok in sorozat.items():
        if not pontok:
            continue
        d, ertek = pontok[-1]
        x, y = eov.get(sid, (0, 0))
        lat, lon = eov_wgs(x, y)
        allomasok.append({
            "nev": nevek.get(sid, sid[:8]),
            "hiany_mm": round(ertek, 1),
            "datum": d,
            "lat": round(lat, 4), "lon": round(lon, 4),
            "sorozat": [round(v, 1) for _, v in pontok[-30:]],
        })

    allomasok.sort(key=lambda a: -a["hiany_mm"])
    atlag = sum(a["hiany_mm"] for a in allomasok) / len(allomasok)
    # A térképre szétszórt mintát választunk; az átlag mindegyikből számol.
    terkepre = legtavolabbi(allomasok, TERKEPRE)

    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    p["talaj_vizhiany"] = {
        "atlag_mm": round(atlag, 1),
        "melyseg": "80 cm",
        "datum": allomasok[0]["datum"],
        "allomas_db": len(allomasok),
        "allomasok": terkepre,
        "provenance": "helyszini",
        "forras": (f"OVF Aszálymonitoring hivatalos API (api.php), {len(allomasok)} állomás "
                   f"számított vízhiánya a 80 cm-es rétegre"),
        "figyelmeztetes": ("Számított mennyiség: a talajnedvesség-mérésből és a szántóföldi "
                           "vízkapacitásból az OVF modellje adja. Az átlag mind a "
                           f"{len(allomasok)} állomásból számol; a térképre tíz, egymástól "
                           "távoli állomás kerül, hogy olvasható maradjon."),
    }
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  állomások: {len(allomasok)} (a térképen {len(terkepre)})")
    print(f"  országos átlag: {atlag:.1f} mm ({allomasok[0]['datum']})")
    print(f"  legszárazabb: " + ", ".join(f"{a['nev']} {a['hiany_mm']:.0f}" for a in allomasok[:4]))
    print(f"  legnedvesebb: " + ", ".join(f"{a['nev']} {a['hiany_mm']:.0f}" for a in allomasok[-3:]))


if __name__ == "__main__":
    main()
