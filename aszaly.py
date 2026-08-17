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


def vetites():
    """A terkep.json vetitese: WGS84 -> a terkep 1000 egyseg szeles doboza.

    A kepletet a folyok.py-bol vesszuk at, hogy a pontok pontosan a
    hatarvonalra illeszkedjenek. A korabbi sajat kozelites eltolta oket,
    ezert a feluk a doboz melle esett es nem latszott.
    """
    gj = json.loads(pathlib.Path("hatar.geojson").read_text(encoding="utf-8"))
    hu = next(f for f in gj["features"] if f["properties"].get("ADM0_A3") == "HUN")
    g = hu["geometry"]
    gyuruk = ([g["coordinates"][0]] if g["type"] == "Polygon"
              else [pol[0] for pol in g["coordinates"]])
    fo = max(gyuruk, key=len)
    xs = [pt[0] for pt in fo]; ys = [pt[1] for pt in fo]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    kozep = math.radians((y0 + y1) / 2)
    sx = 1000 / (x1 - x0)
    return lambda lo, la: (round((lo - x0) * sx, 1),
                           round((y1 - la) * sx / math.cos(kozep), 1))


def racsos(pontok, oszlop=5, sor=4):
    """Racsos mintavetel: az orszagot cellakra osztjuk, es minden cellabol a
    LEGNAGYOBB hianyu allomast vesszuk.

    Miert nem legtavolabbi-pont: az a peremet reszesiti elonyben, mert a
    szeleken levo pontok mindig tavolabb esnek egymastol. Emiatt a korabbi
    valasztasban Puski, Bernecebarati es Felsoszentmarton is szerepelt,
    mikozben az Alfold kozepe uresen maradt.
    """
    if not pontok:
        return []
    lat = [q["lat"] for q in pontok]; lon = [q["lon"] for q in pontok]
    la0, la1, lo0, lo1 = min(lat), max(lat), min(lon), max(lon)
    dla = (la1 - la0) / sor or 1
    dlo = (lo1 - lo0) / oszlop or 1
    cellak = {}
    for q in pontok:
        i = min(int((q["lat"] - la0) / dla), sor - 1)
        j = min(int((q["lon"] - lo0) / dlo), oszlop - 1)
        cellak.setdefault((i, j), []).append(q)
    ki = [max(c, key=lambda q: q["hiany_mm"]) for c in cellak.values()]
    ki.sort(key=lambda q: -q["hiany_mm"])
    return ki


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



# Zirc és Budapest referenciapont: a Bakony csapadékos oldala és az ország
# közepe. A hozzájuk legközelebbi mérőhely mindig szerepeljen a térképen, hogy
# a néző két ismert ponthoz tudja viszonyítani a többit.
REFERENCIA = {"Zirc": (47.262, 17.872), "Budapest": (47.497, 19.040)}


def kotelezo_pontok(mind, valasztott, tavolsag=35):
    """A referenciapontokhoz legközelebbi mérőhelyet hozzáadja a listához."""
    import math
    ki = list(valasztott)
    benne = {q["nev"] for q in ki}
    for nev, (la, lo) in REFERENCIA.items():
        legjobb, tav = None, 1e9
        for q in mind:
            d = math.hypot((q["lat"] - la) * 111, (q["lon"] - lo) * 75)
            if d < tav:
                legjobb, tav = q, d
        if not legjobb or tav >= tavolsag:
            continue
        # Ha mar benne van, csak megjeloljuk - igy a lapon latszik,
        # hogy ez a referencia-pont.
        if legjobb["nev"] in benne:
            for q in ki:
                if q["nev"] == legjobb["nev"]:
                    q["referencia"] = nev
        else:
            ki.append(dict(legjobb, referencia=nev))
            benne.add(legjobb["nev"])
    return ki


def main():
    veg = (dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1
           else dt.date.today() - dt.timedelta(days=1))
    kezd = veg - dt.timedelta(days=30)

    vet = vetites()
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
            # A terkep sajat vetulete - a hatarvonalhoz igazytva,
            # hogy a pont pontosan odva keruljon, ahol az allomas van.
            "terkep_xy": list(vet(lon, lat)),
        })

    allomasok.sort(key=lambda a: -a["hiany_mm"])
    atlag = sum(a["hiany_mm"] for a in allomasok) / len(allomasok)
    # A térképre szétszórt mintát választunk; az átlag mindegyikből számol.
    terkepre = kotelezo_pontok(allomasok, racsos(allomasok, 5, 4))

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
